#!/usr/bin/python

import threading
import paho.mqtt.client as mqtt
import time
import serial
import re
import json


bms_dict = {
    0xF004: {'Name': 'Relays Status',
             'Bytes': 2, 'Encode': 1, 'Signed': False, 'Priority': 3,
             'Scale': 1,
             'Lookup_Table': {
                                    0x01: {'Name': 'Discharge Enable'},
                                    0x02: {'Name': 'Charge Enable'},
                                    0x04: {'Name': 'Charger Safety'},
                                    0x08: {'Name': 'Errors Present'},
                                    0x10: {'Name': 'Multi-purpose Input'},
                                    0x20: {'Name': 'AM Power'},
                                    0x40: {'Name': 'Ready Power'},
                                    0x80: {'Name': 'Charge Power'}}},
    0xF007: {'Name': 'Populated Cell Count',
             'Bytes': 1, 'Encode': 1, 'Signed': False, 'Priority': 4,
             'Scale': 1},
    0xF00A: {'Name': 'Pack Charge Current Limit',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 3,
             'Scale': 1},
    0xF00B: {'Name': 'Pack Disharge Current Limit',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 3,
             'Scale': 1},
    0xF00C: {'Name': 'Signed Pack Current',
             'Bytes': 1, 'Encode': 2, 'Signed': True, 'Priority': 1,
             'Scale': 0.1},
    0xF00D: {'Name': 'Pack Voltage',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 1,
             'Scale': 0.1, 'Max': 6535.5, 'Min': 0},
    0xF00E: {'Name': 'Pack Open Voltage',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 3,
             'Scale': 0.1, 'Max': 6535.5, 'Min': 0},
    0xF00F: {'Name': 'Pack State of Charge',
             'Bytes': 1, 'Encode': 1, 'Signed': False, 'Priority': 3,
             'Scale': 0.5, 'Max': 100, 'Min': 0},
    0xF010: {'Name': 'Pack Amphours',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 3,
             'Scale': 0.1, 'Max': 6535.5, 'Min': 0},
    0xF011: {'Name': 'Pack Resistance',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 3,
             'Scale': 0.01, 'Max': 653.55, 'Min': 0},
    0xF012: {'Name': 'Pack Depth of Discharge',
             'Bytes': 1, 'Encode': 1, 'Signed': False, 'Priority': 3,
             'Scale': 0.5, 'Max': 100, 'Min': 0},
    0xF013: {'Name': 'Pack Health',
             'Bytes': 1, 'Encode': 1, 'Signed': False, 'Priority': 3,
             'Scale': 1, 'Max': 100, 'Min': 0},
    0xF014: {'Name': 'Pack Summed Voltage',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 1,
             'Scale': 0.01, 'Max': 653.55, 'Min': 0},
    0xF015: {'Name': 'Total Pack Cycles',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 4,
             'Scale': 1, 'Max': 65355, 'Min': 0},
    0xF032: {'Name': 'Lowest Cell Voltage',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 2,
             'Scale': 0.0001, 'Max': 5, 'Min': 0},
    0xF033: {'Name': 'Highest Cell Voltage',
             'Bytes': 1, 'Encode': 2, 'Signed': False, 'Priority': 2,
             'Scale': 0.0001, 'Max': 5, 'Min': 0},
    0xF0FF: {'Name': 'Raw Temperature',
             'Bytes': 3, 'Encode': 1, 'Signed': True, 'Priority': 3,
             'Scale': 1, 'Max': 65355, 'Min': 0},
    0xF100: {'Name': 'Cell Voltages',
             'Bytes': 12, 'Encode': 2, 'Span': [1, 12], 'Priority': 2,
             'Scale': 0.0001, 'Signed': False, 'Max': 5, 'Min': 0},
    0xF101: {'Name': 'Cell Voltages',
             'Bytes': 12, 'Encode': 2, 'Span': [13, 24], 'Priority': 2,
             'Scale': 0.0001, 'Signed': False, 'Max': 5, 'Min': 0},
    0xF200: {'Name': 'Internal Resistances',
             'Bytes': 12, 'Encode': 2, 'Span': [1, 12], 'Priority': 2,
             'Scale': 0.0001, 'Signed': False, 'Max': 5, 'Min': 0},
    0xF201: {'Name': 'Internal Resistances',
             'Bytes': 12, 'Encode': 2, 'Span': [13, 24], 'Priority': 2,
             'Scale': 0.0001, 'Signed': False, 'Max': 5, 'Min': 0},
    0xF300: {'Name': 'Open Cell Voltages',
             'Bytes': 12, 'Encode': 2, 'Span': [1, 12], 'Priority': 2,
             'Scale': 0.0001, 'Signed': False, 'Max': 5, 'Min': 0},
    0xF301: {'Name': 'Open Cell Voltages',
             'Bytes': 12, 'Encode': 2, 'Span': [13, 24], 'Priority': 2,
             'Scale': 0.0001, 'Signed': False, 'Max': 5, 'Min': 0},
    }


class handle_rs232(threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ser = serial.Serial("/dev/ttyUSB_P2", baudrate=9600, bytesize=8,
                                 parity='E', stopbits=1, timeout=0.1)
        self.key = 0xF007
        self.reply_new = False
        self.serial_io()

    def run(self):
        while True:
            self.get_data()

    def get_data(self):
        for self.key, self.value in bms_dict.items():
            if self.value['Priority'] == 4:
                self.serial_io()
                for self.key, self.value in bms_dict.items():
                    if self.value['Priority'] == 3:
                        self.serial_io()
                        print hex(self.key)
                        for self.key, self.value in bms_dict.items():
                            if self.value['Priority'] == 2:
                                self.serial_io()
                                for self.key, self.value in bms_dict.items():
                                    if self.value['Priority'] == 1:
                                        self.serial_io()

    def serial_io(self):
        command = ':0322' + str.format('{:04X}', self.key) + '\n'
        self.ser.write(command)
        self.reply = self.ser.read_until()
        self.reply_new = True


class handle_decode_publish(threading.Thread):
    def __init__(self, threadID, handle_rs232_t):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.handle_rs232_t = handle_rs232_t
        self.data = {}
        self.key = 0xF007
        self.value = bms_dict[self.key]
        self.data.update({self.value['Name']: {'Current': 0, 'New': False}})

    def run(self):
        while not self.handle_rs232_t.reply_new:
            print 'here'
            time.sleep(0.01)
        self.handle_rs232_t.reply_new = False
        self.reply = self.handle_rs232_t.reply
        self.decode()
        self.publish()
        print self.data['Populated Cell Count']['Current']
        for self.key, self.value in bms_dict.items():
            if self.value['Name'] not in self.data:
                print self.value['Name']
                self.data.update({self.value['Name']: {'New': False}})
                if self.value['Bytes'] > 1:
                    self.data[self.value['Name']].update({'Current': []})
                    if 'Span' in self.value:
                        print self.value['Name']
                        for i in range(0, self.data['Populated Cell Count']
                                       ['Current']):
                            print i
                            self.data[self.value['Name']]['Current'].append(0)
                else:
                    self.data[self.value['Name']].update({'Current': 0})
        print self.data

        while True:
            time.sleep(0.01)
            if self.handle_rs232_t.reply_new:
                self.reply = self.handle_rs232_t.reply
                self.handle_rs232_t.reply_new = False
                self.decode()
                self.publish()

    def decode(self):
        self.reply_data = []
        if re.match(r'^:[A-F0-9]+', self.reply):
            self.reply_len = int(self.reply[1] + self.reply[2], 16) - 3
            self.key = int(self.reply[5] + self.reply[6]
                           + self.reply[7] + self.reply[8], 16)
            if self.key in bms_dict:
                self.value = bms_dict[self.key]
                if ((self.value['Bytes'] * self.value['Encode']
                     ) == self.reply_len):
                    self.valid_data = True
                    for x in range(0, self.reply_len*2, self.value['Encode']*2):
                        if self.value['Encode'] == 1:
                            self.reply_data.append(int(self.reply[x+9]
                                                       + self.reply[x+10], 16))
                        else:
                            self.reply_data.append(int(self.reply[x+9]
                                                       + self.reply[x+10]
                                                       + self.reply[x+11]
                                                       + self.reply[x+12], 16))
                    self.Scale()
                else:
                    print 'bad value'
                    self.valid_data = False
            else:
                print 'bad value'
                self.valid_data = False
        else:
            print 'bad value'
            self.valid_data = False

    def Scale(self):
        if self.value['Signed'] is True:
            if self.value['Encode'] == 1:
                mask = 0x7F
                subtract = 0x100
            else:
                mask = 0x7FFF
                subtract = 0x10000
        else:
            mask = 0x10000
            subtract = 0x00
        for i, value in enumerate(self.reply_data):
            if value > mask:
                value -= subtract
            if self.value['Scale'] != 1:
                value = float(value) * self.value['Scale']
                self.reply_data[i] = round(value, len(str(
                    self.value['Scale'])))
        #print (str(self.value['Name']) + ' = ' + str(self.reply_data))
        if 'Span' in self.value and 'Populated Cell Count' in self.data:
            if self.value['Span'][1] >= (self.data['Populated Cell Count']
                                         ['Current']):
                for i in range(self.value['Span'][0]-1,
                               self.data['Populated Cell Count']['Current']):
                    if (self.data[self.value['Name']]['Current'][i] != (
                        self.reply_data[i-(self.value['Span'][0]-1)])):
                        self.data[self.value['Name']]['New'] = True
                        self.data[self.value['Name']]['Current'][i] = (
                            self.reply_data[i-(self.value['Span'][0]-1)])
            else:
                for i in range(self.value['Span'][0]-1,
                               self.value['Span'][1]):
                    if self.data[self.value['Name']]['Current'][i] != (
                        self.reply_data[i]):
                        self.data[self.value['Name']]['New'] = True
                        self.data[self.value['Name']]['Current'][i] = (
                            self.reply_data[i])
        elif self.value['Bytes'] > 1:
            if self.data[self.value['Name']]['Current'] != self.reply_data:
                self.data[self.value['Name']]['New'] = True
                self.data[self.value['Name']]['Current'] = self.reply_data
        else:
            if self.data[self.value['Name']]['Current'] != self.reply_data[0]:
                self.data[self.value['Name']]['New'] = True
                self.data[self.value['Name']]['Current'] = self.reply_data[0]

    def publish(self):
        for key, value in self.data.items():
            if 'New' in value:
                if value['New']:
                    value['New'] = False
                    if key == 'Relays Status':
                        for k, v in bms_dict[0xF004]['Lookup_Table'].items():
                            if k & value['Current'][1]:
                                output = True
                            else:
                                output = False
                            print ('BMS/'+str(v['Name']) + ' = ' + str(output))
                            client.publish('BMS/'+str(v['Name']),
                                           str(output), retain=True)
                    if isinstance(value['Current'], list):
                        print ('BMS/'+str(key) + ' = ' + str(value['Current']))
                        client.publish('BMS/'+str(key),
                                       json.dumps(value['Current']),
                                       retain=True)
                    else:
                        print ('BMS/'+str(key) + ' = ' + str(value['Current']))
                        client.publish('BMS/'+str(key),
                                       str(value['Current']), retain=True)
        #print 'publish'


client = mqtt.Client('BMS_py')
client.connect('localhost')
client.loop_start()

threadLock = threading.Lock()
handle_rs232_t = handle_rs232(1)
handle_rs232_t.daemon = True
handle_rs232_t.start()
handle_decode_publish_t = handle_decode_publish(2, handle_rs232_t)
handle_decode_publish_t.daemon = True
handle_decode_publish_t.start()
# handle_485_inverter_data_t = handle_485_inverter_data(2, handle_485_t)
# handle_485_inverter_data_t.daemon = True
# handle_485_inverter_data_t.start()
# handle_485_remote_data_t = handle_485_remote_data(2, handle_485_t)
# handle_485_remote_data_t.daemon = True
# handle_485_remote_data_t.start()

while True:
    time.sleep(1)
