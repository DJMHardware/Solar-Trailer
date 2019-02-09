import threading
import queue
import sys
import paho.mqtt.client as mqtt
import time
import serial
import toml
import json
import os.path
import re


class Register():
    initialized = False

    def __init__(self, command_name, command, new_data_callback=None):
        self.command_name = command_name
        self.value = 0
        self._new_data_callback = new_data_callback
        self.waiting_on_data = False
        self.__dict__.update(command['Default'].copy())
        self.__dict__.update(command[command_name])
        self.__dict__.update({'output_string': '',
                              'value_string': '',
                              'complete': {},
                              'reply': {},
                              'reply_buffer': {}})
        self._build_command_string()
        self._compute_reply_regex()

    @classmethod
    def class_init(cls, command, new_data_callback=None):
        c = {}
        for k in command.keys():
            if k == 'Default':
                continue
            c[k] = cls(k, command, new_data_callback)
            print (k + ' = ' + c[k].output_string),
        return c

    def _build_command_string(self):
        if getattr(self, 'send_value_format', None):
            self._human_to_machine()
        self.output_string = (self.cmd_format.format(self.cmd)
                              + self.value_string)
        if getattr(self, 'mode', None):
            self.output_string = ('{:02X}'.format
                                  ((len(self.output_string) / 2) + 1)
                                  + '{:02X}'.format(self.mode)
                                  + self.output_string)
        self.output_string = (self.prefix + self.output_string + self.suffix)

    def _human_to_machine(self):
        if (self.value is None):
            self.value = 0
        if self.value < self.range['min']:
            self.value = self.range['min']
        if self.value > self.range['max']:
            self.value = self.range['max']
        if self.range['scale'] is not 1:
            self.value = int(round(self.value / self.range['scale']))
        self.value_string = self.send_value_format.format(self.value)

    def _machine_to_human(self, values):
        if values[0] == 'ok':
            return values[0]
        if getattr(self, 'Lookup_Table', None):
            value = int(values[0], self.encoding_base)
            values = {}
            for i in self.Lookup_Table:
                values[i['name']] = bool(value & i['mask'])
            return values
        for i in range(len(values)):
            value = values[i]
            if self.range['scale'] is not 1:
                value = (float(int(value, self.encoding_base))
                         * self.range['scale'])
                self.reply_value_format = (
                    '{:.' + str(self._num_after_point(self.range['scale']))
                    + 'f}')
            else:
                self.reply_value_format = ('{:f}')
            if value < self.range['min']:
                value = self.range['min']
            if value > self.range['max']:
                value = self.range['max']
            values[i] = self.reply_value_format.format(value)
        if len(values) > 1:
            return values
        else:
            return values[0]

    @staticmethod
    def _num_after_point(x):
        s = str(x)
        if '.' not in s:
            return 0
        return len(s) - s.index('.') - 1

    def _compute_reply_regex(self):
        r = self.reply_regex
        if getattr(self, 'payload', None):
            p = self.payload
            p['length'] = ((p['encode'] * 2) * p['bytes'])
            self.reply_regex_prefix = (self.reply_prefix + '{:02X}'.format((
                p['length'] / 2) + 3) + '{:02X}'.format(
                    self.mode + 0x40) + '{:02X}'.format(self.cmd))
            r += ('{' + str(p['length']) + '}')
        else:
            self.reply_regex_prefix = self.reply_prefix + self.cmd
        self.reply_regex_string = ('^' + self.reply_regex_prefix + r)

    def set_value(self, value):
        if value != self.value:
            self.value = value
            self._build_command_string()

    def extract_values(self, value, dev):
        value = re.sub(r'^' + self.reply_regex_prefix, '', value)
        reply_regex_mod = ''
        if getattr(self, 'payload', None):
            reply_regex_mod = ('{' + str(self.payload['encode'] * 2) + '}')
        self.reply_buffer[dev] = self._machine_to_human(
            re.findall((self.reply_regex + reply_regex_mod), value))
        self.complete[dev] = True
        self.check_complete()

    def start_commmand(self, value=None):
        if value is not None:
            self.set_value(value)
        if self.waiting_on_data:
            raise Exception('{} waiting on data still'.format(
                self.command_name))
        self.complete = {}
        self.reply_buffer = {}
        self.waiting_on_data = True

    def new_data_callback(self, new_data_callback):
        self._new_data_callback = new_data_callback

    def check_complete(self):
        done = None
        for c in self.complete:
            if self.complete[c] is True and (done is True or done is None):
                done = True
            else:
                done = False
        if done is True:
            if self.reply != self.reply_buffer:
                self.reply = self.reply_buffer.copy()
                new_data = True
            else:
                new_data = False
            self.waiting_on_data = False
            if self._new_data_callback is not None and new_data:
                self._new_data_callback(self.command_name, self.reply)
        return  # not self.waiting_on_data


class Control(threading.Thread):
    counter = 0

    @classmethod
    def class_init(cls, config_file):
        cls.counter += 1
        threadID = 'control_' + str(cls.counter)
        handle_control_t = cls(threadID, config_file)
        handle_control_t.daemon = True
        handle_control_t.start()
        return handle_control_t

    def __init__(self, threadID, config_file):
        threading.Thread.__init__(self)

        self.threadLock = threading.Lock()
        self.threadID = threadID
        self.command_queue = queue.Queue()
        self.current_command = None
        config_path = os.path.join((os.path.split
                                    (os.path.split
                                     (sys.argv[0])[0])[0]),
                                   'config')
        with open(os.path.join(config_path, config_file)) as f:
            self.config = toml.load(f, _dict=dict)

        print (self.config['uart'])

        self.client = mqtt.Client(self.config['mqtt']['client'])
        self.client.connect(self.config['mqtt']['host'])
        self.client.loop_start()
        self.c = Register.class_init(self.config['command'],
                                     self.new_data_callback)
        self.handle_uart_t = Handle_uart.class_init(self)

    def new_data_callback(self, command_name, values):
        self.current_command = None
        self.command_queue.taskdone()
        print ('new data = {}'.format(values))

    def get_command(self, dev):
        c = None
        if (not self.command_queue.empty() and c is None):
            c = self.command_queue.get()
            self.current_command = c
        if (c is not None
                or dev not in self.current_command.complete):
            self.current_command.complete[dev] = False
        return c

    def run_command(self, command_name, value=None):
        self.c[command_name].start_commmand(value)
        self.command_queue.put(self.c[command_name])

    def run(self):
        while True:
            # value = self.check_command_reply()
            print ('run control ')
            time.sleep(1)


class Handle_uart(threading.Thread):
    @classmethod
    def class_init(cls, caller):
        print ('init uarts')
        handle_uart_t = {}
        for key, value in caller.config['uarts'].items():
            handle_uart_t[key] = cls(key, value, caller)
            handle_uart_t[key].daemon = True
            handle_uart_t[key].start()
        return handle_uart_t

    def __init__(self, threadID, value, caller):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.caller = caller
        self.config = caller.config
        self.dev = value['dev']
        self.phy = value['phy']
        print ('init ' + self.dev)
        self.ser = serial.Serial(self.dev,
                                 baudrate=self.config['uart']['baudrate'],
                                 bytesize=self.config['uart']['bytesize'],
                                 parity=self.config['uart']['parity'],
                                 stopbits=self.config['uart']['stopbits'],
                                 timeout=self.config['uart']['timeout'])
        self.busy = False

    def run(self):
        i = 0
        while True:
            self.check_command_queue()
            time.sleep(0.01)
            if i > 100:
                # print (self.control.command_list)
                i = 0

    def check_command_queue(self):
        c = self.caller.get_command(self.dev)
        if c is not None:
            i = 0
            while True:
                if i == 0:
                    print (self.dev + ' run command = '
                           + str(c.command_name) + ', '
                           + str(c.value))
                else:
                    print (self.dev + ' retry command = '
                           + str(c.command_name) + ', '
                           + str(c.value))
                try:
                    c.extract_values(self.send_command(c), self.dev)
                    time.sleep(0.01)
                except Exception as e:
                    i += 1
                    if i > 10:
                        raise Exception(str(e))
                    time.sleep(.01)
                    continue
                break

    def send_command(self, c):
        reply = self.uart_IO(c.output_string, c.suffix)
        regex = c.reply_regex_string
        if re.match(regex, reply):
            return(reply)
        else:
            raise Exception('error uart returned bad string = ' + str(reply))

    def uart_IO(self, output, EOL_string):
        timeout = 0
        while (self.ser.out_waiting > 0 and self.ser.in_waiting > 0
               and self.busy):
            timeout += 1
            if timeout > 20 and not self.busy:
                self.ser.reset_output_buffer()
                self.ser.reset_input_buffer()
                timeout = 0
                raise Exception('serial write timeout ' + str(self.dev))
            time.sleep(0.01)
        self.busy = True
        self.ser.write(output.encode())
        print (self.dev + ' sent = ' + str(re.sub(EOL_string, '', output)))
        endofline = False
        timeout = 0
        reply = ''
        while not endofline:
            if self.ser.in_waiting > 0:
                r = self.ser.read()
                reply += str(r, 'utf-8')
                if re.search(EOL_string, reply):
                    reply = re.sub(EOL_string, '', reply)
                    endofline = True
            else:
                timeout += 1
                if timeout > 20:
                    endofline = True
                    raise Exception('serial read timeout ' + str(self.dev))
                time.sleep(0.01)
        self.busy = False
        return(reply)


control_bms = Control.class_init('test.toml')
control_bms.run_command('set_voltage', 13)
while True:
    time.sleep(0.01)
