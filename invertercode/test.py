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


class Register(object):

    def __init__(self, command_name, command_dict, command_callback):
        self.command_name = command_name
        self.value = 0
        self._command_callback = command_callback
        self.waiting_on_data = False
        self.__dict__.update(command_dict['Default'].copy())
        self.__dict__.update(command_dict[command_name].copy())
        print (command_dict[command_name])
        self.__dict__.update({'output_string': '',
                              'value_string': '',
                              'complete': {},
                              'reply': None,
                              'raw_reply': {},
                              'reply_buffer': {}})
        if ('groupcmd' not in self.__dict__):
            print ('cmd = 0x{:04X}'.format(self.cmd))
            self._build_command_string()
            self._compute_reply_regex()
        else:
            self.cmd_done = []
            self.reply = []
            self.reply_buffer = []

    @classmethod
    def class_init(cls, command_dict, command_callback):
        c = {}
        for k in command_dict.copy():
            if k == 'Default':
                continue
            if 'cmds' in command_dict[k]:
                i = 0
                for cmd in command_dict[k]['cmds']:
                    i += 1
                    cmd_str = '0x{:04X}'.format(cmd)
                    command_dict_c = command_dict.copy()
                    command_dict_c[k + str(i)] = command_dict[k].copy()
                    command_dict_c[k + str(i)]['cmd'] = cmd
                    command_dict_c[k + str(i)]['parent_command'] = k
                    command_dict_c[k + str(i)]['span'] = (command_dict[k]
                                                          ['spans'][cmd_str])
                    c[k + str(i)] = cls(k + str(i), command_dict_c,
                                        command_callback)
                command_dict[k]['groupcmd'] = True
            c[k] = cls(k, command_dict, command_callback)
        return c

    def _build_command_string(self):
        if 'send_value_format' in self.__dict__:
            self._human_to_machine()
        self.output_string = (self.cmd_format.format(self.cmd)
                              + self.value_string)
        if 'mode' in self.__dict__:
            self.output_string = ('{:02X}'.format(int((len(self.output_string)
                                                       / 2) + 1))
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
        if 'Lookup_Table' in self.__dict__:
            value = int(values[0], self.encoding_base)
            values = {}
            for i in self.Lookup_Table:
                if 'mask' in i:
                    values[i['name']] = bool(value & i['mask'])
                if 'key' in i:
                    values[i['name']] = bool(value == i['key'])
            return values
        for i, value in enumerate(values):
            value = int(value, self.encoding_base)
            if self.range['scale'] is not 1:
                value = (float(value)
                         * self.range['scale'])
                self.reply_value_format = (
                    '{:.' + str(self._num_after_point(self.range['scale']))
                    + 'f}')
            else:
                self.reply_value_format = ('{:d}')
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
        if 'payload' in self.__dict__:
            p = self.payload
            p['length'] = ((p['encode'] * 2) * p['bytes'])
            self.reply_regex_prefix = (self.reply_prefix
                                       + '{:02X}'.format(int((p['length']
                                                              / 2) + 3))
                                       + '{:02X}'.format(self.mode + 0x40)
                                       + '{:02X}'.format(self.cmd))
            r += ('{' + str(p['length']) + '}')
        else:
            self.reply_regex_prefix = self.reply_prefix + self.cmd
        self.reply_regex_string = ('^' + self.reply_regex_prefix + r)

    def set_value(self, value):
        if value is not None:
            if value != self.value:
                self.value = value
                self._build_command_string()

    def extract_values(self, value, dev):
        if not re.match(self.reply_regex_string, value):
            raise Exception('error uart {} returned bad string = {}'
                            .format(dev, value))
        value = re.sub(r'^' + self.reply_regex_prefix, '', value)
        print ('reply value = ' + str(value))
        reply_regex_mod = ''
        if 'payload' in self.__dict__:
            reply_regex_mod = ('{' + str(self.payload['encode'] * 2) + '}')
        self.reply_buffer[dev] = self._machine_to_human(
            re.findall((self.reply_regex + reply_regex_mod), value))
        self.complete[dev] = True
        self.check_complete()

    def start_commmand(self):
        if self.waiting_on_data:
            raise Exception('{} waiting on data still'.format(
                self.command_name))
        self.complete = {}
        self.reply_buffer = {}
        if 'groupcmd' in self.__dict__:
            self.cmd_done = []
            self.reply_buffer = []
        self.waiting_on_data = True

    def check_complete(self):
        done = None
        for c in self.complete:
            if self.complete[c] is True and (done is True or done is None):
                done = True
            else:
                done = False
        if done is True:
            self.raw_reply = self._new_data_check(self.raw_reply)
            self._compute_reply()
            self._callback()

    def _new_data_check(self, reply):
        if reply != self.reply_buffer:
            reply = self.reply_buffer.copy()
            self.new_data = True
        else:
            self.new_data = False
        return reply

    def _compute_reply(self):
        if 'single_uart' in self.__dict__ and self.single_uart:
            for k in self.raw_reply:
                self.reply = self.raw_reply[k]
                self.dev = k
        else:
            self.reply = self.raw_reply

    def _callback(self):
        self.waiting_on_data = False
        self._command_callback(self.command_name, self.reply, self.new_data)

    def add_data(self, cmd, data, span):
        if cmd not in self.cmd_done:
            self.cmd_done.append(cmd)
        for i in range(span[1] - len(self.reply_buffer)):
            self.reply_buffer.append(None)
        for i in range(span[1] - span[0] + 1):
            self.reply_buffer[span[0] + i - 1] = data[i]
        done = True
        for cmd in self.cmds:
            done = bool(done and cmd in self.cmd_done)
        if done:
            self.reply = self._new_data_check(self.reply)
            self._command_callback(self.command_name,
                                   self.reply,
                                   self.new_data)


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

        self.client = mqtt.Client(self.config['mqtt']['client'])
        self.client.connect(self.config['mqtt']['host'])
        self.client.loop_start()
        self.c = Register.class_init(self.config['command'],
                                     self.command_callback)
        self.handle_uart_t = Handle_uart.class_init(self)

    def _check_callback_group_command(self, command_name, values, new_data):
        if new_data and 'parent_command' in self.c[command_name].__dict__:
            c = self.c[command_name]
            p = self.c[c.parent_command]
            p.add_data(c.cmd, c.reply, c.span)

    def command_callback(self, command_name, values, new_data):
        self._check_callback_group_command(command_name, values, new_data)
        self.current_command = None
        if new_data:
            print ('new data = {}'.format(values))

    def get_command(self, dev):
        c = None
        if (not self.command_queue.empty() and self.current_command is None):
            self.current_command = self.command_queue.get()
        if (self.current_command is not None
                and dev not in self.current_command.complete):
            self.current_command.complete[dev] = False
            c = self.current_command
        if c is not None:
            c.start_commmand()
        return c

    def run_command(self, command_name, value=None):
        if 'cmds' in self.c[command_name].__dict__:
            self.c[command_name].start_commmand()
            for i in range(len(self.c[command_name].cmds)):
                self.command_queue.put(self.c[command_name + str(i + 1)])
        else:
            self.c[command_name].set_value(value)
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
                    c.extract_values(self.uart_IO(
                        c.output_string, c.suffix), self.dev)
                    time.sleep(0.01)
                except Exception as e:
                    i += 1
                    if i > 10:
                        raise Exception(repr(e))
                    time.sleep(.01)
                    continue
                break

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


# control_test = Control.class_init('test.toml')
# control_test.run_command('set_voltage', 12)
# control_test.run_command('set_output', 1)
# control_test.run_command('read_actual_voltage')
# control_test.run_command('read_actual_working_time')
control_bms = Control.class_init('bmscontrol.toml')
control_bms.run_command('Relays Status')
control_bms.run_command('Pack Voltage')
control_bms.run_command('Cell Voltages')

while True:
    time.sleep(0.01)
