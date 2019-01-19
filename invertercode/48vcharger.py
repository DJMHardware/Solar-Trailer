import threading
import paho.mqtt.client as mqtt
# import sys
# sys.path.append(r'/home/pi/pysrc')
# sys.setrecursionlimit(200000)
# import pydevd
# pydevd.settrace('192.168.1.145')
import time
import serial
from __builtin__ import str


class handle_control(threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.init_handle_uart()

    def run(self):
        while True:
            self.get_data()


class handle_uart(threading.Thread, handle_control):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ser = serial.Serial("/dev/ttyUSB1", baudrate=9600, bytesize=8,
                                 parity='E', stopbits=1, timeout=0.1)
        self.key = 0xF007
        self.reply_new = False
        self.serial_io()

    def run(self):
        while True:
            self.get_data()
