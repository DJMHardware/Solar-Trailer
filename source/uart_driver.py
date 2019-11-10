import threading
import serial
import time
import re


class Uart_Driver(threading.Thread):
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
                    c.return_values(self.uart_IO(
                        c.output_string[self.dev], c.suffix), self.dev)
                    time.sleep(0.01)
                except Exception as e:
                    print(repr(e))
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
