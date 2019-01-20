import threading
import paho.mqtt.client as mqtt
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
        print 'init ' + self.dev
    # self.ser = serial.Serial("/dev/ttyUSB1", baudrate=9600, bytesize=8,
    #                             parity='E', stopbits=1, timeout=0.1)

    def run(self):
        while True:
            print 'read ' + self.dev
            time.sleep(1)


threadLock = threading.Lock()
handle_control_t = handle_control('control')
handle_control_t.daemon = True
handle_control_t.start()

while True:
    time.sleep(1)
