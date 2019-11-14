import threading
import queue
import sys
import time
import toml
import os.path
import re


class Temperature_Driver(threading.Thread):
    @classmethod
    def class_init(cls, caller):
        print ('init Temperature_Driver')
        handle_temp_t = {}
        for key, value in caller.config['temperature_devices'].items():
            handle_temp_t[key] = cls(key, value, caller)
            handle_temp_t[key].daemon = True
            handle_temp_t[key].start()
        return handle_temp_t

    def __init__(self, threadID, value, caller):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.caller = caller
        self.config = caller.config
        self.dev = value['dev']
        self.phy = value['phy']
        self.id = value['id']
        self.file = (self.config['temperature']['base_path']
                     + '/' + self.dev
                     + self.config['temperature']['sub_path'] + '/'
                     + self.config['temperature']['temp_file'])
        print('init {}'.format(self.dev))
        print('file = {}'.format(self.file))
        self.busy = False

    def run(self):
        i = 0
        while True:
            # self.check_command_queue()
            time.sleep(0.01)
            with open(self.file) as f:
                self.read_data = f.read()
            print('{} = {}'.format(self.dev, self.read_data))
            if i > 100:
                # print (self.control.command_list)
                i = 0


class TemperatureData(object):

    def __init__(self, command_name, command_dict, command_callback):
        self.command_name = command_name
        self.value = 0
        self._command_callback = command_callback
        self.waiting_on_data = False
        self.__dict__.update(command_dict.copy())

    @classmethod
    def class_init(cls, command_dict, command_callback):
        c = {}
        for k in command_dict.copy():
            c[k] = cls(k, command_dict, command_callback)
        return c


class TemperatureAPI(threading.Thread):
    counter = 0

    @classmethod
    def class_init(cls, config_file, temperature_data_class, threaded=True):
        cls.counter += 1
        threadID = 'control_' + str(cls.counter)
        handle_control_t = cls(threadID, config_file,
                               temperature_data_class, threaded)
        if threaded:
            handle_control_t.daemon = True
            handle_control_t.start()
        return handle_control_t

    def __init__(self, threadID, config_file,
                 temperature_data_class, threaded):
        if threaded:
            threading.Thread.__init__(self)
            self.threadLock = threading.Lock()
            self.threadID = threadID
        config_path = os.path.join((os.path.split
                                    (os.path.split
                                     (sys.argv[0])[0])[0]),
                                   'config')
        with open(os.path.join(config_path, config_file)) as f:
            self.config = toml.load(f, _dict=dict)

        self.c = temperature_data_class.class_init(self.config[
            'temperature_devices'], self.command_callback)
        self.handle_temp_t = Temperature_Driver.class_init(self)

    def command_callback(self):
        time.sleep(0.01)
