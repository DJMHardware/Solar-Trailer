import threading
# import paho.mqtt.client as mqtt
import sys
# sys.path.append(r'/home/pi/pysrc')
# sys.setrecursionlimit(200000)
# import pydevd
# pydevd.settrace('192.168.1.145')
import time
import serial
from __builtin__ import str
import toml
import os.path
import re

config_path = os.path.join((os.path.split(os.path.split(sys.argv[0])[0])[0]),
                           'config/48vcharger.toml')
with open(config_path) as f:
    config = toml.load(f, _dict=dict)
print config_path
print config['uarts']
for key, value in config['uarts'].items():
    print key + ' = ' + value['dev']


class handle_control(threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.init_handle_uart()

    def init_handle_uart(self):
        print 'init control'
        self.handle_uart_t = {}
        for key, value in config['uarts'].items():
            handle_uart_t = handle_uart(key, value)
            self.handle_uart_t[key] = handle_uart_t
            self.handle_uart_t[key].daemon = True
            self.handle_uart_t[key].start()

    def run(self):
        while True:
            print 'run control'
            time.sleep(1)


class handle_uart(handle_control):
    def __init__(self, threadID, value):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.dev = value['dev']
        self.address = config['address']['control']
        print 'init ' + self.dev
        self.ser = serial.Serial(self.dev, baudrate=4800, bytesize=8,
                                 parity='N', stopbits=1, timeout=0)

    def run(self):
        while True:
            print 'read ' + self.dev
            self.send_command(config['control_read']['read_actual_voltage'])
            time.sleep(1)

    def send_command(self, command):
        while (self.ser.out_waiting > 0 and self.ser.in_waiting > 0
               and self.busy):
            time.sleep(0.01)
        self.busy = True
        self.ser.write((self.address + command['cmd'] + '\r\n').encode())
        print 'sent'
        if command['return'] is True:
            self.read_reply(command)
        self.busy = False

    def read_reply(self, command):
        endofline = False
        returned_value = ''
        while not endofline:
            if self.ser.in_waiting > 0:
                value = self.ser.read()
                test = int(value[0].encode("hex"), 16)
                if test is 0x0d or test is 0x0a:
                    if test is 0x0a:
                        endofline = True
                else:
                    returned_value += value
        time.sleep(0.01)
        print 'return = ' + returned_value
        regex = "^#" + command['cmd'] + command['regex']
        print 'regex = ' + regex
        if re.match(regex, returned_value):
            value = re.findall(command['regex'], returned_value)
            print 'value = ' + str(value)


threadLock = threading.Lock()
handle_control_t = handle_control('control')
handle_control_t.daemon = True
handle_control_t.start()

while True:
    time.sleep(1)
