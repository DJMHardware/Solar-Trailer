#!/usr/bin/python

import threading
import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
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


# Create a formated stucture for the the byte stream from inverter
inverter_format = ('>2B 2H 2B 2? 8B H B')

# create a namedtuple structure for the decoded stream from inverter

inverter_test_data = (
    0x40, 0x00, 480, 10, 120, 119, 1, 1, 10,
    30, 32, 35, 0x6F, 0, 2, 4, 600, 0, 0)

# remote data
inverter_dict = {
    0x00: {'Inverter_Status': {'Lookup_Table': {
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
                                        }}},
    0x01: {'Inverter_Fault': {'Lookup_Table': {
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
                                }}},
    0x02: {'DC_volts': {'Min': 0, 'Max': 1000, 'Scale': 0.1}},
    0x04: {'DC_amps': {'Min': 0, 'Max': 500, 'Scale': 1}},
    0x06: {'AC_volts_out': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x07: {'AC_Volts_in': {'Min': 0, 'Max': 255, 'Scale': 1}},
    0x08: {'Inverter_LED': {True: 'True', False: 'False'}},
    0x09: {'Charger_LED': {True: 'True', False: 'False'}},
    0x0a: {'Inverter_rev': {'Min': 0, 'Max': 255, 'Scale': 0.1}},
    0x0b: {'Battery_temp': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x0c: {'Transformer_temp': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x0d: {'FET_temp': {'Min': 0, 'Max': 150, 'Scale': 1}},
    0x0e: {'Inverter_Model': {'Lookup_Table': {
                                0x06: {'Model': 'MM612', 'Voltage': 12},
                                0x07: {'Model': 'MM612-AE', 'Voltage': 12},
                                0x08: {'Model': 'MM1212', 'Voltage': 12},
                                0x09: {'Model': 'MMS1012', 'Voltage': 12},
                                0x0A: {'Model': 'MM1012E', 'Voltage': 12},
                                0x0B: {'Model': 'MM1512', 'Voltage': 12},
                                0x0F: {'Model': 'ME1512', 'Voltage': 12},
                                0x14: {'Model': 'ME2012', 'Voltage': 12},
                                0x19: {'Model': 'ME2512', 'Voltage': 12},
                                0x1E: {'Model': 'ME3112', 'Voltage': 12},
                                0x23: {'Model': 'MS2012', 'Voltage': 12},
                                0x28: {'Model': 'MS2012E', 'Voltage': 12},
                                0x2D: {'Model': 'MS2812', 'Voltage': 12},
                                0x2F: {'Model': 'MS2712E', 'Voltage': 12},
                                0x35: {'Model': 'MM1324E', 'Voltage': 24},
                                0x36: {'Model': 'MM1524', 'Voltage': 24},
                                0x37: {'Model': 'RD1824', 'Voltage': 24},
                                0x3B: {'Model': 'RD2624E', 'Voltage': 24},
                                0x3F: {'Model': 'RD2824', 'Voltage': 24},
                                0x45: {'Model': 'RD4024E', 'Voltage': 24},
                                0x4A: {'Model': 'RD3924', 'Voltage': 24},
                                0x5A: {'Model': 'MS4124E', 'Voltage': 24},
                                0x5B: {'Model': 'MS2024', 'Voltage': 24},
                                0x69: {'Model': 'MS4024', 'Voltage': 24},
                                0x6A: {'Model': 'MS4024AE', 'Voltage': 24},
                                0x6B: {'Model': 'MS4024PAE', 'Voltage': 24},
                                0x6F: {'Model': 'MS4448AE', 'Voltage': 48},
                                0x70: {'Model': 'MS3748AEJ', 'Voltage': 48},
                                0x73: {'Model': 'MS4448PAE', 'Voltage': 48},
                                0x74: {'Model': 'MS3748PAEJ', 'Voltage': 48},
                                        }}},
    0x10: {'Stack_Mode': {'Lookup_Table': {
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
                            'Scale': 1, 'Steps': 1,
                            'Lookup_Table': {'Disable': 0x00}}},
    0x02: {'Battery_size': {'Default': 20, 'Min': 20,
                            'Max': 120, 'Scale': 10, 'Steps': 10}},
    0x03: {'Battery_Type': {'Default': 148, 'Min': 100, 'Max': 255,
                            'Scale': {12: 0.1, 24: 0.2, 48: 0.4},
                            'Lookup_Table': {'Gel': 0x02,
                                             'Flooded': 0x04,
                                             'AGM': 0x08,
                                             'AGM2': 0x0a,
                                             'Custom_Absorb': {'Default': 148},
                                             }}},
    0x04: {'Charger_Amps': {'Default': 10, 'Min': 0, 'Max': 100,
                            'Scale': 1, 'Steps': 10}},
    0x05: {'AC_shore_amps': {'Default': 15, 'Scale': 1, 'Steps': 1,
                             'Min': 5, 'Max': 60}},
    0x06: {'Remote_revision': {'Default': 36}},
    0x07: {'Parallel_threshold_Force_Charge': {'Default': 0x06,
                                               'Lookup_Table':
                                               {'Disable Refloat': 0x10,
                                                'Force Silent': 0x20,
                                                'Force Float': 0x40,
                                                'Force Bulk': 0x80,
                                                }}},
    0x08: {'Auto_Genstart': {'Default': 0, 'Lookup_Table': {
                                            'Off': 0x00,
                                            'Enable': 0x01,
                                            'Test': 0x02,
                                            'Enable_with_Quiet_Time': 0x04,
                                            'On': 0x05,
                                            }}},
    0x09: {'Low_Battery_Cut_Out': {'Default': 200,
                                   'Min': {12: 90, 24: 190, 48: 190},
                                   'Max': {12: 160, 24: 255, 48: 255},
                                   'Scale': {12: 0.1, 24: 0.1, 48: 0.2}}},
    0x0a: {'VAC_cut_out_voltage': {'Default': 155, 'Scale': 1,
                                   'Lookup_Table': {
                                       '60VAC': 110,
                                       '65VAC': 122,
                                       '70VAC': 135,
                                       '75VAC': 145,
                                       '80VAC': 155,
                                       '85VAC': 165,
                                       '90VAC': 175,
                                       '95VAC': 182,
                                       '100VAC': 190,
                                       'EMS_over_ride_open_relay': 255}}},
    0x0b: {'Float_Volts': {'Default': 137, 'Min': 100, 'Max': 255,
                           'Scale': {12: 0.1, 24: 0.2, 48: 0.4}}},
    0x0c: {'EQ_Volts': {'Default': 0, 'Min': 0, 'Max': 20,
                        'Scale': {12: 0.1, 24: 0.2, 48: 0.4}}},
    0x0d: {'Absorb_Time': {'Default': 20, 'Min': 0, 'Max': 255,
                           'Scale': 0.1, 'Steps': 1}},
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

inverter_ctrl_dict = {
    'Inverter_State': {'Current': False,
                       'True': ['INVERTMODE', 'SEARCHMODE']},
    'Search_State': {'Current': False,
                     'True': ['FLOATMODE', 'ABSORBMODE', 'BULKMODE',
                              'BATSAVERMODE', 'EQMODE', 'CHARGEMODE',
                              'ChargerStandby', 'SEARCHMODE', 'INVERTMODE']},
    'Charger_State': {'Current': True,
                      'True': ['FLOATMODE', 'ABSORBMODE', 'BULKMODE',
                               'BATSAVERMODE', 'EQMODE', 'CHARGEMODE']},
    'Disable_Refloat': {'Current': False},
    'Disable_AC_In': {'Current': False},
    'Force_Silent': {'Current': False},
    'Force_Float': {'Current': False},
    'Force_Bulk': {'Current': False},
}


class handle_485(threading.Thread):
    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.OUT)
        GPIO.output(17, GPIO.LOW)
        self.ser = serial.Serial("/dev/ttyUSB0", 19200, timeout=0.1)
        self.inverter_bytestream = ''
        self.inverter_bytestream_flag = False
        self.remote_bytestream = ''
        self.remote_bytestream_flag = False
        self.inverter_voltage = False

    def run(self):
        x_string = ''
        while True:
            t_old = time.time()
            x_string_start_t = time.time()
            read_loop = True
            while read_loop:
                x = self.ser.read(1)
                t = time.time()
                t_change = t - t_old
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
            GPIO.output(17, GPIO.HIGH)
            time.sleep(0.01)
            if self.remote_bytestream_flag:
                threadLock.acquire()
                # print ('start remote write'+str(time.time()-x_string_start_t))
                self.ser.write(self.remote_bytestream)
                x = self.ser.read(len(self.remote_bytestream))
                # print (str(self.ser.out_waiting))
                self.remote_bytestream_flag = False
                # print (binascii.hexlify(self.remote_bytestream))
                # print ('end remote write'+str(time.time()-x_string_start_t))
                threadLock.release()
            time.sleep(0.01)
            GPIO.output(17, GPIO.LOW)

                # self.ser.flush()

# convert inverter bytestream to structured list to namedtuple
#  then finally to a named dict so can be decoded and scaled


class handle_485_inverter_data(threading.Thread):
    def __init__(self, threadID, handle_485_t):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.handle_485_t = handle_485_t
        self.inv_data_s = struct.Struct(inverter_format)
        inverter_names = []
        self.inverter_dict = {}
        self.inverter_dict_old = {}
        for key, value in inverter_dict.items():
            inverter_names.append(value.keys()[0])
            self.inverter_dict[value.keys()[0]] = value[value.keys()[0]]
            self.inverter_dict_old[value.keys()[0]] = None
        # print (inverter_names)
        # print (self.inverter_dict)
        self.inv_data_named_s = namedtuple('inv_data_named_s', inverter_names)

    def run(self):
        self.publish_inverter_iomap()
        while True:
            if self.handle_485_t.inverter_bytestream_flag:
                try:
                    self.decode_bytestream()
                    self.publish_inverter_data()
                except:
                    print 'bad data'
                self.handle_485_t.inverter_bytestream_flag = False
            time.sleep(0.1)
        #    print (str((len(x_string)-1)) + ' ' + binascii.hexlify(x) + ' '
        # + str(t_change)  )

    def decode_bytestream(self):
        inv_data_named_dict = self.inv_data_named_s._make(
            list(self.inv_data_s.unpack(
                self.handle_485_t.inverter_bytestream)))._asdict()
        for key, value in self.inverter_dict.items():
            value['Current'] = inv_data_named_dict[key]
            if key == 'Inverter_Model':
                value['Human'] = value['Lookup_Table'][
                    value['Current']]['Model']
                self.handle_485_t.inverter_voltage = value['Lookup_Table'][
                    value['Current']]['Voltage']
            elif key == 'Inverter_Status':
                value['Human'] = value['Lookup_Table'][value['Current']]
            elif key == 'Inverter_Fault':
                value['Human'] = value['Lookup_Table'][value['Current']]
            elif key == 'Inverter_LED' or key == 'Charger_LED':
                value['Human'] = value[value['Current']]
            elif 'Scale' in value:
                value['Human'] = value['Current'] * value['Scale']

    def publish_inverter_data(self):
        for key, value in self.inverter_dict.items():
            if self.inverter_dict_old[key] is None or self.inverter_dict_old[
                    key] != value['Current']:
                client.publish(
                    'Inverter/' + key, str(value['Current']),
                    retain=True)
                print (key + '=' + str(value['Current']))
                if 'Human' in value:
                    client.publish(
                        'Inverter/' + key + '/Human', str(value['Human']),
                        retain=True)
                    print (key + ' Human =' + str(value['Human']))
            self.inverter_dict_old[key] = value['Current']

    def publish_inverter_iomap(self):
        for key, value in inverter_dict.items():
            # print value[value.keys()[0]]
            client.publish('Inverter/' + str(value.keys()[0]) + '/IOMap',
                           json.dumps(value[value.keys()[0]]), retain=True)


class handle_485_remote_data(threading.Thread):
    def __init__(self, threadID, handle_485_t):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.handle_485_t = handle_485_t
        self.remote_data_list = []
        self.remote_data_names_dict = []
        self.Inverter_State_flag = False
        self.remote_dict = {}
        for key, value in remote_dict.items():
            self.remote_dict[value.keys()[0]] = value[value.keys()[0]]
        for key, value in self.remote_dict.items():
            value['Current'] = value['Default']
            value['Lock'] = False
            self.remote_data_list.append(value['Current'])

    def run(self):
        while not self.handle_485_t.inverter_voltage:
            time.sleep(0.1)
        self.scale_remote_dict()
        self.publish_remote_iomap()
        client.subscribe([("Remote/+", 0), ("Remote/+/Human", 0),
                          ("Remote/+/Default", 0)])
        client.on_message = self.mqtt_on_message
        while True:
            if self.handle_485_t.remote_bytestream_flag is False:
                self.build_bytestream()
            time.sleep(.08)

    def scale_remote_dict(self):
        print 'scaling'
        for key, value in self.remote_dict.items():
            if 'Scale' in value:
                if isinstance(value['Scale'], dict):
                    value['Scale'] = value[
                        'Scale'][self.handle_485_t.inverter_voltage]
                    value['Steps'] = value['Scale']
                    print (str(key) + ' Scale = '
                           + str(value['Scale']))
            if 'Min' in value:
                if isinstance(value['Min'], dict):
                    value['Min'] = value[
                        'Min'][self.handle_485_t.inverter_voltage]
                    print (str(key) + ' Min = '
                           + str(value['Min']))
            if 'Max' in value:
                if isinstance(value['Max'], dict):
                    value['Max'] = value[
                        'Max'][self.handle_485_t.inverter_voltage]
                    print (str(key) + ' Max = '
                           + str(value['Max']))

    def mqtt_on_message(self, client, userdata, message):
        topic = message.topic.split('/')
        print ('topic = ' + str(topic[1]))
        print ('message received = ' + message.payload)
        for key, value in self.remote_dict.items():
            if key == topic[1]:
                if len(topic) > 2:
                    print (topic[2])
                    if topic[2] == 'Human':
                        value['Current'] = int(
                            float(message.payload) / (float(value['Scale'])))
                        client.publish('Remote/' + str(key)
                                       + '/Current',
                                       str(value['Current']),
                                       retain=True)
                        print ('Remote/' + str(key) + '/Current ='
                               + str(value['Current']))
                    if topic[2] == 'Default':
                        value['Default'] = int(
                            float(message.payload) / (float(value['Scale'])))
                        client.publish('Remote/' + str(key)
                                       + '/IOMap',
                                       json.dumps(value),
                                       retain=True)
                        print ('Remote/' + str(key) + '/Default ='
                               + str(value['Default']))
                        if value['Lock'] is False:
                            value['Current'] = value['Default']
                else:
                    value['Current'] = int(message.payload)
                print ('Current = ' + str(value['Current']))

    def publish_remote_iomap(self):
        for key, value in self.remote_dict.items():
            # print value
            client.publish('Remote/' + str(key) + '/IOMap',
                           json.dumps(value), retain=True)

    def build_bytestream(self):
        self.remote_data_list = []
        for key, value in remote_dict.items():
            key = value.keys()[0]
            value = value[value.keys()[0]]
            if key == 'Hours' and value['Current'] != int(time.strftime("%H")):
                value['Current'] = int(time.strftime("%H"))
                client.publish('Remote/Hours', value
                               ['Current'], retain=True)
            if key == 'Minutes' and value['Current'] != int(
                    time.strftime("%M")):
                value['Current'] = int(time.strftime("%M"))
                client.publish('Remote/Minutes', value
                               ['Current'], retain=True)
            # Inverter State btye has to be returned to zero after single xfer
            if key == 'Inverter_State' and value['Current']:
                if self.Inverter_State_flag:
                    value['Current'] = 0
                    self.Inverter_State_flag = False
                    client.publish('Remote/Inverter_State', 0,
                                   retain=True)
                    print ('Inverter_State=' + str(value['Current']))
                else:
                    self.Inverter_State_flag = True
                    print ('Inverter_State=' + str(value['Current']))
            self.remote_data_list.append(value['Current'])
        self.handle_485_t.remote_bytestream = remote_data_s.pack(
            *self.remote_data_list)
        self.handle_485_t.remote_bytestream_flag = True


class handle_inverter_ctrl(threading.Thread):
    def __init__(self, threadID, inverter_data_t, remote_data_t):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.inverter_dict = inverter_data_t.inverter_dict
        self.remote_dict = remote_data_t.remote_dict
        for state, data in inverter_ctrl_dict.items():
            data['Retry_Count'] = 0
            data['Set'] = data['Current']
            data['State_old'] = data['Current']

    def run(self):
        time.sleep(1)
        ctrlclient.subscribe([("InverterCtrl/+/Set", 0)])
        ctrlclient.on_message = self.mqtt_on_message
        while True:
            for state, data in inverter_ctrl_dict.items():
                self.update_state(state, data)
            time.sleep(.1)

    def update_state(self, state, data):
        data['State_old'] = data['Current']
        if (data['Set'] != data['Current']):
            data['Retry_Count'] += 1
            if (data['Retry_Count'] >= 10):
                self.set_state(state, data)
        self.check_state(state, data)
        if data['Current'] != data['State_old']:
            print 'publish = ' + str(data
                                     ['Current'])
            ctrlclient.publish('InverterCtrl/' + state, str(
                data['Current']), retain=True)

    def set_state(self, state, data):
        print 'State is = ' + state
        if state is 'Inverter_State':
            self.remote_dict[state]['Current'] |= self.remote_dict[
                state]['Lookup_Table']['Inverter_ON_OFF']
            data['Retry_Count'] = 0
        if state is 'Charger_State':
            if not(data['Set'] and ((
                    self.remote_dict['VAC_cut_out_voltage']['Current'] is
                    self.remote_dict['VAC_cut_out_voltage']['Lookup_Table'][
                        'EMS_over_ride_open_relay'])
                    or (self.inverter_dict['AC_Volts_in']['Current']
                        <= (self.remote_dict['VAC_cut_out_voltage'
                                             ]['Current'] - 35)))
                   ):
                self.remote_dict['Inverter_State'][
                    'Current'] |= self.remote_dict[
                    'Inverter_State']['Lookup_Table']['Charger_ON_OFF']
            data['Retry_Count'] = 0
        if state is 'Search_State':
            data['Retry_Count'] = 0
            print 'Search State'
            if (data['Set'] is False):
                print str(self.remote_dict['Search_watts']['Current'])
                if self.remote_dict['Search_watts']['Current'] is not 0:
                    self.remote_dict['Search_watts'][
                        'Default'] = self.remote_dict['Search_watts'][
                            'Current']
                    self.remote_dict['Search_watts']['Current'] = 0
                    self.remote_dict['Search_watts']['Lock'] = True
            else:
                self.remote_dict['Search_watts'][
                    'Current'] = self.remote_dict['Search_watts'][
                        'Default']
                self.remote_dict['Search_watts']['Lock'] = False
        if state is 'Disable_AC_In':
            data['Retry_Count'] = 0
            if data['Set'] is True:
                self.remote_dict['VAC_cut_out_voltage']['Lock'] = True
                self.remote_dict['VAC_cut_out_voltage'][
                    'Default'] = self.remote_dict[
                    'VAC_cut_out_voltage']['Current']
                self.remote_dict['VAC_cut_out_voltage'][
                    'Current'] = self.remote_dict['VAC_cut_out_voltage'][
                        'Lookup_Table']['EMS_over_ride_open_relay']
            else:
                self.remote_dict['VAC_cut_out_voltage']['Lock'] = False
                self.remote_dict['VAC_cut_out_voltage'][
                    'Current'] = self.remote_dict[
                    'VAC_cut_out_voltage']['Default']

    def check_state(self, state, data):
        if state is 'Inverter_State':
            if (self.inverter_dict['Inverter_LED']
                    ['Current'] is True) or (
                        self.inverter_dict['Inverter_Status'][
                            'Human'] in data['True']):
                data['Current'] = True
            else:
                data['Current'] = False
        if state is 'Charger_State':
            if (self.inverter_dict['Inverter_Status']
                    ['Human'] in data['True']):
                data['Current'] = True
            else:
                data['Current'] = False
        if state is 'Search_State':
            if ((self.inverter_dict['Inverter_Status'][
                    'Human'] in data['True']) and (data['Set'])):
                data['Current'] = True
            else:
                data['Current'] = False
        if state is 'Disable_AC_In':
            if (self.remote_dict['VAC_cut_out_voltage'][
                    'Current'] is self.remote_dict['VAC_cut_out_voltage'][
                        'Lookup_Table']['EMS_over_ride_open_relay']):
                data['Current'] = True
            else:
                data['Current'] = False

    def mqtt_on_message(self, client, userdata, message):
        topic = message.topic.split('/')
        print ('topic = ' + str(topic[1]))
        print ('message received = ' + message.payload)
        if str(topic[1]) in inverter_ctrl_dict:
            if len(topic) > 2:
                self.decode(message, topic)
        else:
            print 'Unknown Mqtt topic'

    def decode(self, message, topic):
        if topic[2] == 'Set':
            print 'setting ' + str(topic[1]) + ' = ' + (message.payload)
            inverter_ctrl_dict[topic[1]]['Retry_Count'] = 9
            if message.payload == 'True':
                print 'state True'
                inverter_ctrl_dict[topic[1]]['Set'] = True
            else:
                print 'state False'
                inverter_ctrl_dict[topic[1]]['Set'] = False
            inverter_ctrl_dict[topic[1]]['Retry_Count'] = 10
            self.update_state(topic[1], inverter_ctrl_dict[topic[1]])


client = mqtt.Client('Inverter_py')
client.connect('localhost')
client.loop_start()
ctrlclient = mqtt.Client('InverterCtrl_py')
ctrlclient.connect('localhost')
ctrlclient.loop_start()

threadLock = threading.Lock()
handle_485_t = handle_485(1)
handle_485_t.daemon = True
handle_485_t.start()
handle_485_inverter_data_t = handle_485_inverter_data(2, handle_485_t)
handle_485_inverter_data_t.daemon = True
handle_485_inverter_data_t.start()
handle_485_remote_data_t = handle_485_remote_data(3, handle_485_t)
handle_485_remote_data_t.daemon = True
handle_485_remote_data_t.start()
handle_inverter_ctrl_t = handle_inverter_ctrl(4, handle_485_inverter_data_t,
                                              handle_485_remote_data_t)
handle_inverter_ctrl_t.daemon = True
handle_inverter_ctrl_t.start()

while True:
    time.sleep(1)
