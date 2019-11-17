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
            handle_temp_t[value['id']] = cls(value['id'], value, caller)
            handle_temp_t[value['id']].daemon = True
            handle_temp_t[value['id']].start()
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
            while True:
                if i > 0:
                    # print(self.dev + ' run command = '
                    #      + str(self.dev))
                    # else:
                    print(self.dev + ' retry command = '
                          + str(self.dev))
                try:
                    with open(self.file) as f:
                        self.caller.c[self.id].extract_values(
                            f.read().splitlines())
                    time.sleep(0.01)
                except Exception as e:
                    print(repr(e))
                    i += 1
                    if i > 10:
                        raise Exception(repr(e))
                    time.sleep(.01)
                    continue
                break
            # self.check_command_queue()
            time.sleep(0.01)

            if i > 100:
                # print (self.control.command_list)
                i = 0


class TemperatureData(object):

    def __init__(self, id, value, config_dict):
        self.value = 0
        self.id = value['id']
        self.phy = value['phy']
        self.dev = value['dev']
        self.regex = {}
        self.regex['line0'] = re.compile(r'^' + config_dict
                                         ['temperature_regex']['line0'])
        self.regex['line1'] = re.compile(r'^' + config_dict
                                         ['temperature_regex']['line1'])
        self.regex['prefix'] = re.compile(r'^' + config_dict
                                          ['temperature_regex']['prefix'])
        self.waiting_on_data = False

    @classmethod
    def class_init(cls, config):
        c = {}
        for key, value in config['temperature_devices'].copy().items():
            c[value['id']] = cls(value['id'], value, config)
        return c

    def extract_values(self, value):
        if not (self.regex['line0'].match(value[0])
                and self.regex['line1'].match(value[1])):
            raise Exception('error {} returned bad string = {}'
                            .format(self.dev, value))
        self.value = (float(self.regex['prefix'].sub('', value[1]))) / 1000

        print('{} = {}'.format(self.dev, self.value))


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

        self.c = temperature_data_class.class_init(self.config)
        self.handle_temp_t = Temperature_Driver.class_init(self)

    def command_callback(self, value):
        time.sleep(0.01)
