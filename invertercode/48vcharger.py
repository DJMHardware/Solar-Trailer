import threading
import sys
import paho.mqtt.client as mqtt
import time
import serial
import toml
import json
import os.path
import re


class handle_control(threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.command_list = []
        self.phy_list = {}
        client.subscribe([((config['mqtt']['topic'] + '/+/send'), 0)])
        client.on_message = self.mqtt_on_message
        self.init_handle_uart()

    def init_handle_uart(self):
        print ('init control')
        self.handle_uart_t = {}
        for key, value in config['uarts'].items():
            if value['phy'] not in self.phy_list:
                self.phy_list[value['phy']] = True
            handle_uart_t = handle_uart(self, key, value)
            self.handle_uart_t[key] = handle_uart_t
            self.handle_uart_t[key].daemon = True
            self.handle_uart_t[key].start()

    def command(self, command_name, value=None):
        command = {'command': command_name,
                   'value': value,
                   'complete': {},
                   'reply': {}}
        self.command_list.append(command)

    def check_command_reply(self):
        done = None
        for v in reversed(self.command_list):
            for c in v['complete']:
                if v['complete'][c] is True and (done is True or done is None):
                    done = True
                else:
                    done = False
            if done is True:
                if config['command'][v['command']]['regex'] != 'ok':
                    self.publish_to_mqtt(v)
                else:
                    print ('command ' + v['command'] + '\nreturned ok')
                self.command_list.remove(v)

    @staticmethod
    def publish_to_mqtt(v):
        reply = []
        for vv in v['reply']:
            reply.append(v['reply'][vv])
        print ('test' + str(reply))
        client.publish(config['mqtt']['topic'] + '/' + str(v['command']),
                       json.dumps(reply),
                       retain=True)

    def mqtt_on_message(self, client, userdata, message):
        topic = message.topic.split('/')
        print ('topic = ' + str(topic[1]))
        print ('message received = ' + message.payload)
        if topic[1] in config['command']:
            command = config['command'][topic[1]]
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


class handle_uart(threading.Thread):
    def __init__(self, control, threadID, value):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.control = control
        self.dev = value['dev']
        self.address = config['address']['control']
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
        command = config['command'][command_name]
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


config_path = os.path.join((os.path.split(os.path.split(sys.argv[0])[0])[0]),
                           'config/48vcharger.toml')
with open(config_path) as f:
    config = toml.load(f, _dict=dict)
print (config_path)
for key, value in config['uarts'].items():
    print (key + ' = ' + value['dev'])

client = mqtt.Client(config['mqtt']['client'])
client.connect(config['mqtt']['host'])
client.loop_start()


threadLock = threading.Lock()
handle_control_t = handle_control('control')
handle_control_t.daemon = True
handle_control_t.start()

while True:
    time.sleep(1)
