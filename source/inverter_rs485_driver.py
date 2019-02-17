import threading
import serial
import time
import re


class Uart_Driver(threading.Thread):
    @classmethod
    def class_init(cls, caller):
        print ('init uarts')
        key, value in caller.config['uarts']
        handle_uart_t = cls(key, value, caller)
        handle_uart_t.daemon = True
        handle_uart_t.start()
        return handle_uart_t

    def __init__(self, threadID, value, caller):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.caller = caller
        self.config = caller.config
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
        while True:
