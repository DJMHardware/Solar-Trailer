import threading
import sys
import paho.mqtt.client as mqtt
import time
import serial
import toml
import json
import os.path
import re


class Control():
    counter = 0

    def __init__(self, config_file):
        self.__class__.counter += 1
        config_path = os.path.join((os.path.split
                                    (os.path.split
                                     (sys.argv[0])[0])[0]),
                                   'config')
        with open(os.path.join(config_path, config_file)) as f:
            self.config = toml.load(f, _dict=dict)

        print self.config['uart']

        self.client = mqtt.Client(self.config['mqtt']['client'])
        self.client.connect(self.config['mqtt']['host'])
        self.client.loop_start()

        self.threadLock = threading.Lock()
        thread_name = 'control_' + str(self.counter)
        self.handle_control_t = handle_control(thread_name, self)
        self.handle_control_t.daemon = True
        self.handle_control_t.start()

    def command(self, command_name, value=None):
        self.handle_control_t.command(command_name, value)


class handle_control(threading.Thread):
    def __init__(self, threadID, caller):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.config = caller.config
        self.client = caller.client
        self.command_list = []
        self.phy_list = {}
        self.client.subscribe([((self.config['mqtt']['topic']
                                 + '/+/send'), 0)])
        self.client.on_message = self.mqtt_on_message
        self.init_handle_uart()

    def init_handle_uart(self):
        print ('init control')
        self.handle_uart_t = {}
        for key, value in self.config['uarts'].items():
            if value['phy'] not in self.phy_list:
                self.phy_list[value['phy']] = True
            handle_uart_t = handle_uart(self, key, value)
            self.handle_uart_t[key] = handle_uart_t
            self.handle_uart_t[key].daemon = True
            self.handle_uart_t[key].start()

    def command(self, command_name, value=None):
        c = self.config['command'][command_name]
        c.update({'command': command_name,
                  'value': value})
        c.update(self.config['command']['Default'])
        if 'cmds' in c:
            for cmd in c['cmds']:
                c['cmd'] = cmd
                c['span'] = c['spans']['0x{:04X}'.format(cmd)]
                self.command_list.append(self.build_command(c))
        else:
            self.command_list.append(self.build_command(c))

    def build_command(self, c):
        c = c.copy()
        c.update({'output_string': '',
                  'value_string': '',
                  'complete': {},
                  'reply': {}})
        if 'send_value_format' in c:
            c['value_string'] = self.human_to_machine(c, c['value'])
        c['output_string'] = (c['cmd_format'].format(c['cmd'])
                              + c['value_string'])
        if 'mode' in c:
            c['output_string'] = ('{:02X}'.format
                                  ((len(c['output_string']) / 2) + 1)
                                  + '{:02X}'.format(c['mode'])
                                  + c['output_string'])
        c['output_string'] = (c['prefix'] + c['output_string'] + c['suffix'])
        return self.compute_reply_regex(c)

    def extract_values(self, c, value):
        print ('raw value = ' + value)
        value = re.sub(r'^' + c['reply_regex_prefix'], '', value.encode())
        print ('reply_regex_prefix = ' + c['reply_regex_prefix'])
        print ('stripped value = ' + value)
        if 'payload' in c:
            reply_regex_mod = ('{' + str(c['payload']['encode'] * 2) + '}')
        print ('reply_regex = ' + c['reply_regex'])
        values = re.findall((c['reply_regex'] + reply_regex_mod), value)
        return self.machine_to_human(c, values)

    def compute_reply_regex(self, c):
        r = c['reply_regex']
        if 'payload' in c:
            p = c['payload']
            p['length'] = ((p['encode'] * 2) * p['bytes'])
            c['reply_regex_prefix'] = (c['reply_prefix'] + '{:02X}'.format((
                p['length'] / 2) + 3) + '{:02X}'.format(
                    c['mode'] + 0x40) + '{:02X}'.format(c['cmd']))
            r += ('{' + str(p['length']) + '}')
        else:
            c['reply_regex_prefix'] = c['reply_prefix'] + c['cmd']
        c['reply_regex_string'] = ('^' + c['reply_regex_prefix'] + r)
        return c

    def human_to_machine(self, c, value):
        if (value is not None):
            if value < c['range']['min']:
                value = c['range']['min']
            if value > c['range']['max']:
                value = c['range']['max']
            if c['range']['scale'] is not 1:
                value = int(round(value / c['range']['scale']))
            return c['send_value_format'].format(value)
        else:
            return ''

    def machine_to_human(self, c, values):
        if values[0] == 'ok':
            return values[0]
        if 'Lookup_Table' in c:
            value = int(values[0], c['encoding_base'])
            values = {}
            for i in c['Lookup_Table']:
                values[i['name']] = bool(value & i['mask'])
            return values
        for i in range(len(values)):
            value = values[i]
            if c['range']['scale'] is not 1:
                value = (float(int(value, c['encoding_base']))
                         * c['range']['scale'])
                c['reply_value_format'] = (
                    '{:.' + str(self.num_after_point(c['range']['scale']))
                    + 'f}')
            else:
                c['reply_value_format'] = ('{:f}')
            if value < c['range']['min']:
                value = c['range']['min']
            if value > c['range']['max']:
                value = c['range']['max']
            values[i] = c['reply_value_format'].format(value)
        if len(values) > 1:
            return values
        else:
            return values[0]

    def num_after_point(self, x):
        s = str(x)
        if '.' not in s:
            return 0
        return len(s) - s.index('.') - 1

    def check_command_reply(self):
        done = None
        for v in reversed(self.command_list):
            for c in v['complete']:
                if v['complete'][c] is True and (done is True or done is None):
                    done = True
                else:
                    done = False
            if done is True:
                if v['reply_regex'] != 'ok':
                    self.publish_to_mqtt(v)
                else:
                    print ('command ' + v['command'] + '\nreturned ok')
                print ('complete ' + str(v['complete']))
                print ('remove ' + str(v['cmd']))
                self.command_list.remove(v)

    def publish_to_mqtt(self, v):
        reply = []
        for vv in v['reply']:
            reply.append(v['reply'][vv])
        print ('test' + str(reply))
        self.client.publish(self.config['mqtt']['topic'] + '/'
                            + str(v['command']), json.dumps(reply),
                            retain=True)

    def mqtt_on_message(self, client, userdata, message):
        topic = message.topic.split('/')
        print ('topic = ' + str(topic[1]))
        print ('message received = ' + message.payload)
        if topic[1] in self.config['command']:
            c = self.config['command'][topic[1]]
            if c['format'] is False:
                self.command(topic[1])
            else:
                if c['scale'] == 1:
                    print (int(message.payload))
                    self.command(topic[1], int(message.payload))
                else:
                    self.command(topic[1], float(message.payload))

    def run(self):
        print (self.phy_list)
        while True:
            value = self.check_command_reply()
            print ('run control ' + str(value))
            time.sleep(1)


class handle_uart(threading.Thread):
    def __init__(self, control, threadID, value):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.control = control
        self.config = control.config
        self.dev = value['dev']
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
        print 'here'
        while True:
            self.check_command_queue()
            time.sleep(1)
            if i > 100:
                print (self.control.command_list)
                i = 0

    def check_command_queue(self):
        for i in range(len(self.control.command_list)):
            print ('start ' + str(i) + ' = ' + str(
                self.control.command_list[i]['cmd']) + ' = '),
            print (self.control.command_list[i]['complete'])
        for v in self.control.command_list:
            if self.dev not in v['complete']:
                v['complete'][self.dev] = False
                i = 0
                while True:
                    if i == 0:
                        print (self.dev + ' run command = '
                               + str(v['command']) + ', '
                               + str(v['value']))
                    else:
                        print (self.dev + ' retry command = '
                               + str(v['command']) + ', '
                               + str(v['value']))
                    try:
                        value = (self.send_command(v))
                        v['reply'][self.dev] = self.control.extract_values(
                            v, value)
                        for i in range(len(self.control.command_list)):
                            print ('mid' + str(i) + ' = ' + str(
                                self.control.command_list[i]['cmd']) + ' = '),
                            print (self.control.command_list[i]['complete'])
                    except Exception as e:
                        i += 1
                        if i > 10:
                            raise Exception(str(e))
                        time.sleep(.01)
                        continue
                    break
                for i in range(len(self.control.command_list)):
                    print ('end 1 ' + str(i) + ' = ' + str(
                        self.control.command_list[i]['cmd']) + ' = '),
                    print (self.control.command_list[i]['complete'])
                v['complete'][self.dev] = True
                for i in range(len(self.control.command_list)):
                    print ('end 2 ' + str(i) + ' = ' + str(
                        self.control.command_list[i]['cmd']) + ' = '),
                    print (self.control.command_list[i]['complete'])

    def send_command(self, c):
        reply = self.uart_IO(c['output_string'], c['suffix'])
        regex = c['reply_regex_string']
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
                reply += r
                if re.match('\n', r):
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


# control_test = Control('test.toml')
# control_test.command('set_voltage', 12)
# control_test.command('set_output', 1)
# control_test.command('read_actual_voltage')
# control_test.command('read_actual_working_time')
control_bms = Control('bmscontrol.toml')
control_bms.command('Relays Status')
control_bms.command('Cell Voltages')

while True:
    time.sleep(1)
