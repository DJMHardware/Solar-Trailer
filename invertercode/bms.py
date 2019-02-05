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
        self.client.subscribe([((self.config['mqtt']['topic'] + '/+/send'), 0)])
        self.client.on_message = self.mqtt_on_message
        # self.init_handle_uart()

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
        command = self.config['command'][command_name]
        command.update(self.config['command']['Default'])
        command.update({'command': command_name,
                        'value': value,
                        'output_string': '',
                        'value_string': '',
                        'complete': {},
                        'reply': {}})
        if 'cmds' in command:
            for cmd in command['cmds']:
                command['cmd'] = cmd
                command['span'] = command['spans']['0x{:04X}'.format(cmd)]
                print (self.build_command(command))
        else:
            print (self.build_command(command))
        # self.command_list.append(command)

    def build_command(self, command):
        if 'send_value_format' in command:
            command['value_string'] = self.human_to_machine(command,
                                                            command['value'])
        command['output_string'] = (command['cmd_format']
                                    .format(command['cmd'])
                                    + command['value_string'])
        if 'mode' in command:
            command['output_string'] = ('{:02X}'.format
                                        ((len(command['output_string'])
                                          / 2) + 1)
                                        + '{:02X}'.format(command['mode'])
                                        + command['output_string'])
        command['output_string'] = (command['prefix']
                                    + command['output_string']
                                    + command['suffix'])
        return self.compute_reply_regex(command)

    def compute_reply_regex(self, command):
        if 'payload' in command:
            payload = command['payload']
            command['payload']['length'] = ((payload['encode'] * 2)
                                            * payload['bytes'])
            command['reply_regex_prefix'] = (command['prefix']
                                             + '{:02X}'.format(
                                                 (command['payload']['length']
                                                  / 2) + 3)
                                             + '{:02X}'.format(command['mode']
                                                               + 0x40)
                                             + '{:02X}'.format(command['cmd']))
            command['reply_regex'] = ('[0-9A-F]{'
                                      + str(command['payload']['length'])
                                      + '}')
        else:
            command['reply_regex_prefix'] = command['prefix'] + command['cmd']
        command['reply_regex_string'] = ('^' + command['reply_regex_prefix']
                                         + command['reply_regex'])
        return command

    def human_to_machine(self, command, value):
        if (value is not None):
            if value < command['range']['min']:
                value = command['range']['min']
            if value > command['range']['max']:
                value = command['range']['max']
            if command['range']['scale'] is not 1:
                value = int(round(value / command['range']['scale']))
            return command['send_value_format'].format(value)
        else:
            return ''

    def machine_to_human(self, command):
        pass

    def check_command_reply(self):
        done = None
        for v in reversed(self.command_list):
            for c in v['complete']:
                if v['complete'][c] is True and (done is True or done is None):
                    done = True
                else:
                    done = False
            if done is True:
                if self.config['command'][v['command']]['regex'] != 'ok':
                    self.publish_to_mqtt(v)
                else:
                    print ('command ' + v['command'] + '\nreturned ok')
                self.command_list.remove(v)

    @classmethod
    def publish_to_mqtt(cls, v):
        reply = []
        for vv in v['reply']:
            reply.append(v['reply'][vv])
        print ('test' + str(reply))
        cls.client.publish(cls.config['mqtt']['topic'] + '/'
                           + str(v['command']), json.dumps(reply), retain=True)

    def mqtt_on_message(self, client, userdata, message):
        topic = message.topic.split('/')
        print ('topic = ' + str(topic[1]))
        print ('message received = ' + message.payload)
        if topic[1] in self.config['command']:
            command = self.config['command'][topic[1]]
            if command['format'] is False:
                self.command(topic[1])
            else:
                if command['scale'] == 1:
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


class handle_uart(threading.Thread, Control):
    def __init__(self, control, threadID, value):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.control = control
        self.dev = value['dev']
        self.address = self.config['address']['control']
        print ('init ' + self.dev)
        self.ser = serial.Serial(self.dev, baudrate=4800, bytesize=8,
                                 parity='N', stopbits=1, timeout=0)
        self.busy = False

    def run(self):
        while True:
            self.check_command_queue()
            time.sleep(.01)

    def check_command_queue(self):
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
                            v['reply'][self.dev] = (
                                self.send_command(v['command'], v['value']))
                        except Exception as e:
                            i += 1
                            if i > 10:
                                raise Exception(str(e))
                            time.sleep(.01)
                            continue
                        break
                    v['complete'][self.dev] = True

    def send_command(self, command_name, value=None):
        command = self.config['command'][command_name]
        formatedvalue = ''
        if command['format'] is not False:
            if command['scale'] is not 1:
                value = int(round(value * command['scale']))
            if value < command['min']:
                value = command['min']
            if value > command['max']:
                value = command['max']
            formatedvalue = command['format'].format(value)
        reply = self.uart_IO(self.address + command['cmd']
                             + formatedvalue + '\r\n')
        regex = "^#" + command['cmd'] + command['regex']
        if re.match(regex, reply):
            value = re.findall(command['regex'], reply)
            if command['regex'] != value[0]:
                value = int(value[0])
                if command['scale'] is not 1:
                    value = float(value) / command['scale']
            else:
                value = str(value[0])
            print (self.dev + ' value = ' + str(value))
            return(value)
        else:
            raise Exception('error uart returned bad string = ' + str(reply))

    def uart_IO(self, output):
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
        print (self.dev + ' sent = ' + str(re.sub('\n|\r', '', output)))
        endofline = False
        timeout = 0
        reply = ''
        while not endofline:
            if self.ser.in_waiting > 0:
                reply_stream = self.ser.read()
                reply += re.sub('\n|\r', '', reply_stream)
                if re.match('\n', reply_stream):
                    endofline = True
            else:
                timeout += 1
                if timeout > 20:
                    endofline = True
                    raise Exception('serial read timeout ' + str(self.dev))
                time.sleep(0.01)
        self.busy = False
        return(reply)


control_bms = Control('bmscontrol.toml')
control_test = Control('test.toml')
control_test.command('set_voltage', 12)
control_bms.command('Relays Status')
control_bms.command('Cell Voltages')

while True:
    time.sleep(1)
