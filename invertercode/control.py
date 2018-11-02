#!/usr/bin/python

import threading
import paho.mqtt.client as mqtt
# import sys
# sys.path.append(r'/home/pi/pysrc')
# sys.setrecursionlimit(200000)
# import pydevd
# pydevd.settrace('192.168.1.145')
import time
import serial
import struct
import binascii
import json
from collections import namedtuple
from __builtin__ import str


client = mqtt.Client('Inverter_py')
client.connect('localhost')
client.loop_start()

# Create a formated stucture for the the byte stream from inverter
inverter_format = ('>2B 2H 2B 2? 8B H B')
inv_data_s = struct.Struct(inverter_format)

# create a namedtuple structure for the decoded stream from inverter
inverter_names = (
    'Inverter_Status', 'Inverter_Fault',
    'DC_volts', 'DC_amps',
    'AC_volts_out', 'AC_Volts_in',
    'Inverter_LED', 'Charger_LED',
    'Inverter_rev', 'Battery_temp',
    'Transformer_temp', 'FET_temp',
    'Inverter_Model', 'Stack_Mode',
    'AC_amps_in',  'AC_amps_out',
    'AC_Hz',  'Not_used')
inv_data_named_s = namedtuple('inv_data_named_s', inverter_names)

# a couple look up tables to decode indivual bytes
inverter_status_lookup = {
    0x00: 'ChargerStandby',
    0x01: 'EQMODE',
    0x02: 'FLOATMODE',
    0x04: 'ABSORBMODE',
    0x08: 'BULKMODE',
    0x09: 'BATSAVERMODE',
    0x10: 'CHARGEMODE',
    0x20: 'Off',
    0x40: 'INVERTMODE',
    0x50: 'Inverter Standby',
    0x80: 'SEARCHMODE',
    }

inverter_fault_lookup = {
    0x00: 'No_ERROR',
    0x01: 'STUCKRELAY',
    0x02: 'DC_OVERLOAD',
    0x03: 'AC_OVERLOAD',
    0x04: 'DEAD BAT',
    0x05: 'BACKFEED',
    0x08: 'LOWBAT',
    0x09: 'HIGHBAT',
    0x0A: 'HIGHACVOLTS',
    0x10: 'BAD_BRIDGE',
    0x12: 'NTC_FAULT',
    0x13: 'FET_OVERLOAD',
    0x14: 'INTERNAL_FAULT4',
    0x16: 'STACKER_MODE_FAULT',
    0x17: 'STACKER_NO_CLK_FAULT',
    0x18: 'STACKER_CLK_PH_FAULT',
    0x19: 'STACKER_PH_LOSS_FAULT',
    0x20: 'OVERTEMP',
    0x21: 'RELAY_FAULT',
    0x80: 'CHARGER_FAULT',
    0x81: 'HIBATEMP',
    0x90: 'OPEN_SELCO_TCO',
    0x91: 'CB3_OPEN_FAULT',
    }

inverter_model_lookup = {
    0x06: 'MM612',
    0x07: 'MM612-AE',
    0x08: 'MM1212',
    0x09: 'MMS1012',
    0x0A: 'MM1012E',
    0x0B: 'MM1512',
    0x0F: 'ME1512',
    0x14: 'ME2012',
    0x19: 'ME2512',
    0x1E: 'ME3112',
    0x23: 'MS2012',
    0x28: 'MS2012E',
    0x2D: 'MS2812',
    0x2F: 'MS2712E',
    0x35: 'MM1324E',
    0x36: 'MM1524',
    0x37: 'RD1824',
    0x3B: 'RD2624E',
    0x3F: 'RD2824',
    0x45: 'RD4024E',
    0x4A: 'RD3924',
    0x5A: 'MS4124E',
    0x5B: 'MS2024',
    0x69: 'MS4024',
    0x6A: 'MS4024AE',
    0x6B: 'MS4024PAE',
    0x6F: 'MS4448AE',
    0x70: 'MS3748AEJ',
    0x73: 'MS4448PAE',
    0x74: 'MS3748PAEJ',
    }
inverter_test_data = (
    0x40, 0x00, 480, 10, 120, 119, 1, 1, 10,
    30, 32, 35,  0x6F, 0, 2, 4, 600, 0, 0)

# remote data
inverter_dict = {
    0x00: {'Inverter_Status': {'Lookup_Table': {
                                'ChargerStandby': 0x00,
                                'EQMODE': 0x01,
                                'FLOATMODE': 0x02,
                                'ABSORBMODE': 0x04,
                                'BULKMODE': 0x08,
                                'BATSAVERMODE': 0x09,
                                'CHARGEMODE': 0x10,
                                'Off': 0x20,
                                'INVERTMODE': 0x40,
                                'Inverter_Standby': 0x50,
                                'SEARCHMODE': 0x80,
                                }}},
    0x01: {'Inverter_Fault': {'Lookup_Table': {
                                'No_ERROR': 0x00,
                                'STUCKRELAY': 0x01,
                                'DC_OVERLOAD': 0x02,
                                'AC_OVERLOAD': 0x03,
                                'DEAD_BAT': 0x04,
                                'BACKFEED': 0x05,
                                'LOWBAT': 0x08,
                                'HIGHBAT': 0x09,
                                'HIGHACVOLTS': 0x0A,
                                'BAD_BRIDGE': 0x10,
                                'NTC_FAULT': 0x12,
                                'FET_OVERLOAD': 0x13,
                                'INTERNAL_FAULT4': 0x14,
                                'STACKER_MODE_FAULT': 0x16,
                                'STACKER_NO_CLK_FAULT': 0x17,
                                'STACKER_CLK_PH_FAULT': 0x18,
                                'STACKER_PH_LOSS_FAULT': 0x19,
                                'OVERTEMP': 0x20,
                                'RELAY_FAULT': 0x21,
                                'CHARGER_FAULT': 0x80,
                                'HIBATEMP': 0x81,
                                'OPEN_SELCO_TCO': 0x90,
                                'CB3_OPEN_FAULT': 0x91,
                                }}},
    0x02: {'DC_volts': {'Min': 0, 'Max': 1000, 'Scale': 0.1}},
    0x04: {'DC_amps': {'Min': 0, 'Max': 500, 'Scale': 1}},
    0x06: {'AC_volts_out': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x07: {'AC_Volts_in': {'Min': 0, 'Max': 255, 'Scale': 1}},
    0x08: {'Inverter_LED': {'True': True, 'False': False}},
    0x09: {'Charger_LED': {'True': True, 'False': False}},
    0x0a: {'Inverter_rev': {'Min': 0, 'Max': 255, 'Scale': 1}},
    0x0b: {'Battery_temp': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x0c: {'Transformer_temp': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x0d: {'FET_temp': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x0e: {'Inverter_Model': {'Default': 0x00, 'Lookup_Table': {
                                        'MM612': 0x06,
                                        'MM612-AE': 0x07,
                                        'MM1212': 0x08,
                                        'MMS1012': 0x09,
                                        'MM1012E': 0x0A,
                                        'MM1512': 0x0B,
                                        'ME1512': 0x0F,
                                        'ME2012': 0x14,
                                        'ME2512': 0x19,
                                        'ME3112': 0x1E,
                                        'MS2012': 0x23,
                                        'MS2012E': 0x28,
                                        'MS2812': 0x2D,
                                        'MS2712E': 0x2F,
                                        'MM1324E': 0x35,
                                        'MM1524': 0x36,
                                        'RD1824': 0x37,
                                        'RD2624E': 0x3B,
                                        'RD2824': 0x3F,
                                        'RD4024E': 0x45,
                                        'RD3924': 0x4A,
                                        'MS4124E': 0x5A,
                                        'MS2024': 0x5B,
                                        'MS4024': 0x69,
                                        'MS4024AE': 0x6A,
                                        'MS4024PAE': 0x6B,
                                        'MS4448AE': 0x6F,
                                        'MS3748AEJ': 0x70,
                                        'MS4448PAE': 0x73,
                                        'MS3748PAEJ': 0x74,
                                        }}},
    0x10: {'Stack_Mode': {'Default': 0x00, 'Lookup_Table': {
                                            'Standalone unit': 0x00,
                                            'Parallel stack - master': 0x01,
                                            'Parallel stack - slave': 0x02,
                                            'Series stack - master': 0x04,
                                            'Series stack - slave': 0x08,
                                            }}},
    0x12: {'AC_amps_in': {'Min': 0, 'Max': 255, 'Scale': 1}},
    0x13: {'AC_amps_out': {'Min': 0, 'Max': 255, 'Scale': 1}},
    0x14: {'AC_Hz': {'Min': 400, 'Max': 800, 'Scale': 0.1}},
    0x16: {'Not_used': {'Min': 0, 'Max': 255, 'Scale': 1}},

}
remote_dict = {
    0x00: {'Inverter_State': {'Default': 0x00, 'Lookup_Table': {
                                            'Inverter_ON_OFF': 0x01,
                                            'Charger_ON_OFF': 0x02,
                                            'EQ_Mode': 0x0a
                                            }}},
    0x01: {'Search_watts': {'Default': 0x00, 'Min': 5, 'Max': 50,
                            'Lookup_Table': {'Disable': 0x00}}},
    0x02: {'Battery_size': {'Default': 40, 'Min': 20,
                            'Max': 120, 'Scale': 10}},
    0x03: {'Battery_Type': {'Default': 0x04, 'Min': 100, 'Lookup_Table': {
                                            'Gel': 0x02,
                                            'Flooded': 0x04,
                                            'AGM': 0x8,
                                            'AGM2': 0x0a,
                                            'Custom_Absorb': '100+',
                                            }}},
    0x04: {'Charger_Amps': {'Default': 80, 'Min': 0, 'Max': 100, 'Steps': 10}},
    0x05: {'AC_shore_amps': {'Default': 30, 'Min': 5, 'Max': 60}},
    0x06: {'Remote_revision': {'Default': 36}},
    0x07: {'Parallel_threshold_Force_Charge': {'Default': 0x06}},
    0x08: {'Auto_Genstart': {'Default': 0, 'Lookup_Table': {
                                            'Off': 0x00,
                                            'Enable': 0x01,
                                            'Test': 0x02,
                                            'Enable_with_Quiet_Time': 0x04,
                                            'On': 0x05,
                                            }}},
    0x09: {'Low_Battery_Cut_Out': {'Default': 200, 'Min': 190,
                                   'Max': 255, 'Scale': 0.2}},
    0x0a: {'VAC_cut_out_voltage': {'Default': 155, 'Lookup_Table': {
                                            '60VAC': 110,
                                            '65VAC': 122,
                                            '70VAC': 135,
                                            '75VAC': 145,
                                            '80VAC': 155,
                                            '85VAC': 165,
                                            '90VAC': 175,
                                            '95VAC': 182,
                                            '100VAC': 190,
                                            'EMS_over_ride_open_relay': 255,
                                           }}},
    0x0b: {'Float_Volts': {'Default': 132, 'Scale': 0.4}},
    0x0c: {'EQ_Volts': {'Default': 12, 'Min': 190, 'Max': 255, 'Scale': 0.4}},
    0x0d: {'Absorb_Time': {'Default': 20, 'Min': 0, 'Max': 255, 'Scale': 0.1}},
    0x0e: {'Hours': {'Default': 12}},
    0x0f: {'Minutes': {'Default': 00}}
  }

remote_AGS_0xA0_dict = {
    0x00: {'Gen_run_time': {'Default': 20, 'Min': 0,
                            'Max': 255, 'Scale': 0.1}},
    0x01: {'Start_Temp': {'Default': 0, 'Min': 33, 'Max': 104,
                          'Scale': 0.1, 'Lookup_Table': {'Off': 0x00}}},
    0x02: {'Start_VDC': {'Default': 110, 'Min': 0, 'Max': 255,
                         'Scale': 0.1, 'Lookup_Table': {'Off': 0x00}}},
    0x03: {'Quiet_time_hours': {'Default': 0x00, 'Lookup_Table': {
                                            'Off': 0x00,
                                            '9pm to 7am': 0x01,
                                            '9pm to 8am': 0x02,
                                            '9pm to 9am': 0x03,
                                            '10pm to 8am': 0x04,
                                            '11pm to 8am': 0x05,
                                            }}},
    0x04: {'Footer': {'Default': 0xA0}},
    }
remote_data_format = ('>16B')
remote_data_s = struct.Struct(remote_data_format)


class handle_485(threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ser = serial.Serial("/dev/ttyUSB0", 19200, timeout=0.1)
        self.inverter_bytestream = ''
        self.inverter_bytestream_flag = False
        self.remote_bytestream = ''
        self.remote_bytestream_flag = False

    def run(self):
        x_string = ''
        while True:
            t_old = time.time()
            x_string_start_t = time.time()
            read_loop = True
            while read_loop:
                x = self.ser.read(1)
                t = time.time()
                t_change = t-t_old
                if x != '':
                    t_old = t
                    # print str(t_change) + ' : '+ binascii.hexlify(x)
                if t_change > 0.03:
                    x_string = ''
                    x_string_start_t = t
                if len(x_string) == 21:
                    threadLock.acquire()
                    if x_string != self.inverter_bytestream:
                        self.inverter_bytestream = x_string
                        self.inverter_bytestream_flag = True
                    read_loop = False
                    # print (binascii.hexlify(self.inverter_bytestream))
                    # print ('end of inverter read time'
                    #       + str(time.time()-x_string_start_t))
                    threadLock.release()
                    # print (str(t_change))
                x_string = x_string + x
            time.sleep(0.01)
            if self.remote_bytestream_flag:
                threadLock.acquire()
                # print ('start remote write'+str(time.time()-x_string_start_t))
                self.ser.write(self.remote_bytestream)
                self.remote_bytestream_flag = False
                # print (binascii.hexlify(self.remote_bytestream))
                # print ('end remote write'+str(time.time()-x_string_start_t))
                threadLock.release()
                # self.ser.flush()

# convert inverter bytestream to structured list to namedtuple
#  then finally to a named dict so can be decoded and scaled


class handle_485_inverter_data(threading.Thread):
    def __init__(self, threadID, handle_485_t):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.handle_485_t = handle_485_t

    def run(self):
        inv_data_named_dict_old = None
        while True:
            if self.handle_485_t.inverter_bytestream_flag:
                try:
                    inv_data_list = list(inv_data_s.unpack(
                        self.handle_485_t.inverter_bytestream))
                    inv_data_named_tuple = inv_data_named_s._make(
                        inv_data_list)
                    inv_data_named_dict = inv_data_named_tuple._asdict()
                    inv_data_named_dict['Inverter_Status'] = inverter_status_lookup[inv_data_named_dict['Inverter_Status']]
                    inv_data_named_dict['Inverter_Fault'] = inverter_fault_lookup[inv_data_named_dict['Inverter_Fault']]
                    inv_data_named_dict['Inverter_Model'] = inverter_model_lookup[inv_data_named_dict['Inverter_Model']]
                    inv_data_named_dict['DC_volts'] = float(
                        inv_data_named_dict['DC_volts'])/10
                    inv_data_named_dict['AC_Hz'] = float(
                        inv_data_named_dict['AC_Hz'])/10
                    for id in inv_data_named_dict:
                        if inv_data_named_dict_old is None or inv_data_named_dict_old[id] != inv_data_named_dict[id]:
                            client.publish(
                                'Inverter/'+id, str(inv_data_named_dict[id]),
                                retain=True)
                            print (id + '=' + str(inv_data_named_dict[id]))
                    inv_data_named_dict_old = inv_data_named_dict
                except:
                    print 'bad data'
                self.handle_485_t.inverter_bytestream_flag = False
            time.sleep(0.1)
        #    print (str((len(x_string)-1)) + ' ' + binascii.hexlify(x) + ' ' + str(t_change)  )

    def decode_bytestream(self):
        i = 0
        inv_data_list = list(inv_data_s.unpack(
                        self.handle_485_t.inverter_bytestream))
        for key, value in remote_dict.items():
            value[value.keys()[0]]['Current'] = inv_data_list[i]
            i += 1


class handle_485_remote_data(threading.Thread):
    def __init__(self, threadID, handle_485_t):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.handle_485_t = handle_485_t
        self.remote_data_list = []
        self.remote_data_names_dict = []
        self.Inverter_State_flag = False
        for key, value in remote_dict.items():
            value[value.keys()[0]]['Current'] = value[
                value.keys()[0]]['Default']
            self.remote_data_list.append(value[value.keys()[0]]['Current'])

    def run(self):
        self.publish_remote_iomap()
        client.subscribe("Remote/+/")
        client.on_message = self.mqtt_on_message
        while True:
            if self.handle_485_t.remote_bytestream_flag is False:
                self.build_bytestream()
            time.sleep(.08)

    def mqtt_on_message(self, client, userdata, message):
        topic = message.topic.split('/')
        print ('topic = ' + str(topic[1]))
        print ('message received = ' + message.payload)
        for key, value in remote_dict.items():
            if value.keys()[0] == topic[1]:
                value[value.keys()[0]]['Current'] = int(message.payload)

    def publish_remote_iomap(self):
        for key, value in remote_dict.items():
            print value[value.keys()[0]]
            client.publish('Remote/'+str(value.keys()[0]) + '/IOMap/',
                           json.dumps(value[value.keys()[0]]), retain=True)

    def build_bytestream(self):
        self.remote_data_list = []
        for key, value in remote_dict.items():
            # Inverter State btye has to be returned to zero after single xfer
            if value.keys()[0] == 'Inverter_State' and value[
                                            value.keys()[0]]['Current']:
                if self.Inverter_State_flag:
                    value[value.keys()[0]]['Current'] = 0
                    self.Inverter_State_flag = False
                    client.publish('Remote/Inverter_State/Current/', 0,
                                   retain=True)
                else:
                    self.Inverter_State_flag = True
            self.remote_data_list.append(value[value.keys()[0]]['Current'])
        self.handle_485_t.remote_bytestream = remote_data_s.pack(
            *self.remote_data_list)
        self.handle_485_t.remote_bytestream_flag = True


threadLock = threading.Lock()
handle_485_t = handle_485(1)
handle_485_t.daemon = True
handle_485_t.start()
handle_485_inverter_data_t = handle_485_inverter_data(2, handle_485_t)
handle_485_inverter_data_t.daemon = True
handle_485_inverter_data_t.start()
handle_485_remote_data_t = handle_485_remote_data(2, handle_485_t)
handle_485_remote_data_t.daemon = True
handle_485_remote_data_t.start()

while True:
    time.sleep(1)
