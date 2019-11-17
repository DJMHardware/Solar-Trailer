import threading
import queue
import sys
import time
import toml
import os.path
import re


class RemoteCommandData(object):

    def __init__(self, command_name, command_dict, command_callback):
        self.command_name = command_name
        self.value = 0
        self._command_callback = command_callback
        self.waiting_on_data = False
        self.__dict__.update(command_dict['Default'].copy())
        self.__dict__.update(command_dict[command_name].copy())
        self.__dict__.update({'output_string': {},
                              'value_string': {},
                              'command_string': {},
                              'waiting_on_data': {},
                              'reply': None})

    @classmethod
    def class_init(cls, command_dict, command_callback):
        c = {}
        for k in command_dict.copy():
            if k == 'Default':
                continue
            c[k] = cls(k, command_dict, command_callback)
        return c

    def _build_command_string(self, value, dev):
        if hasattr(self, 'send_value_format'):
            self.value_string[dev] = self._human_to_machine(value)
        else:
            self.value_string[dev] = ''
        self.command_string[dev] = (self.cmd_format.format(self.cmd)
                                    + self.value_string[dev])
        self.output_string[dev] = (self.prefix + self.command_string[dev]
                                   + self.suffix)
        # print('output string {}'.format(self.output_string))

    def _human_to_machine(self, value):
        if (value is None):
            value = 0
        if value < self.range['min']:
            value = self.range['min']
        if value > self.range['max']:
            value = self.range['max']
        if self.range['scale'] != 1:
            value = int(round(self.value / self.range['scale']))
        return self.send_value_format.format(value)

    def _machine_to_human(self, values):
        if values[0] == 'ok':
            return values[0]
        if hasattr(self, 'Lookup_Table'):
            value = int(values[0], self.encoding_base)
            values = {}
            for i in self.Lookup_Table:
                if 'mask' in i:
                    values[i['name']] = bool(value & i['mask'])
                if 'key' in i:
                    values[i['name']] = bool(value == i['key'])
            return values
        for i, value in enumerate(values):
            value = int(value, self.encoding_base)
            if self.range['scale'] != 1:
                value = (float(value)
                         * self.range['scale'])
                self.reply_value_format = (
                    '{:.' + str(self._num_after_point(self.range['scale']))
                    + 'f}')
            else:
                self.reply_value_format = ('{:d}')
            if value < self.range['min']:
                value = self.range['min']
            if value > self.range['max']:
                value = self.range['max']
            values[i] = self.reply_value_format.format(value)
        if len(values) > 1:
            return values
        else:
            return values[0]

    @staticmethod
    def _num_after_point(x):
        s = str(x)
        if '.' not in s:
            return 0
        return len(s) - s.index('.') - 1

    def extract_values(self, value, dev):
        if not re.match(self.reply_regex_string, value):
            raise Exception('error uart {} returned bad string = {}'
                            .format(dev, value))
        value = re.sub(r'^' + self.reply_regex_prefix, '', value)
        return self._machine_to_human(re.findall(self.reply_regex, value))

    def _compute_reply_regex(self):
        self.reply_regex_prefix = self.reply_prefix + self.cmd
        self.reply_regex_string = ('^' + self.reply_regex_prefix
                                   + self.reply_regex)

    def _compute_reply(self):
        self.reply = self._new_data_check(self.reply_buffer)

    def _new_data_check(self, reply):
        if reply != self.reply:
            self.new_data = True
        else:
            self.new_data = False
        return reply

    def _callback(self, dev):
        # print('_callback {}'.format(dev))
        self._compute_reply()
        self.waiting_on_data[dev] = False
        self._command_callback(self.command_name, dev,
                               self.reply, self.new_data)

    def set_value(self, value, dev):
        self.value = value
        self._build_command_string(value, dev)

    def return_values(self, value, dev):
        self.reply_buffer = self.extract_values(value, dev)
        self._callback(dev)

    def start_commmand(self, dev=None):
        print('********{} = {}'.format(self.command_name, self.complete))
        if hasattr(self.waiting_on_data, dev) and self.waiting_on_data[dev]:
            raise Exception('{} {} waiting on data still'
                            .format(dev, self.command_name))
        self.complete = False
        self.waiting_on_data[dev] = True


class RemoteAPI(threading.Thread):
    counter = 0

    @classmethod
    def class_init(cls, config_file, remote_command_data_class, threaded=True):
        cls.counter += 1
        threadID = 'control_' + str(cls.counter)
        handle_control_t = cls(threadID, config_file,
                               remote_command_data_class, threaded)
        if threaded:
            print('init RemoteAPI class threaded')
            handle_control_t.daemon = True
            handle_control_t.start()
        return handle_control_t

    def __init__(self, threadID, config_file,
                 remote_command_data_class, threaded):
        if threaded:
            print('init RemoteAPI thread')
            threading.Thread.__init__(self)
            self.threadLock = threading.Lock()
            self.threadID = threadID
        config_path = os.path.join((os.path.split
                                    (os.path.split
                                     (sys.argv[0])[0])[0]),
                                   'config')
        with open(os.path.join(config_path, config_file)) as f:
            self.config = toml.load(f, _dict=dict)
        self.command_queue = {}
        self.current_command = {}
        for uart in self.config['uarts']:
            self.current_command[self.config['uarts'][uart]['dev']] = None
            self.command_queue[self.config['uarts']
                               [uart]['dev']] = queue.Queue()

        self.c = remote_command_data_class.class_init(self.config['command'],
                                                      self.command_callback)

    def command_callback(self, command_name, dev, values, new_data):
        self.command_queue[dev].task_done()
        # print('done {} {}'.format(self.command_queue[dev].qsize(), dev))
        self.current_command[dev] = None
        # if new_data:
        #     print('{} = {}'.format(command_name, values))

    def get_command(self, dev):
        if (not self.command_queue[dev].empty() and self.current_command[dev] is None):
            temp = self.command_queue[dev].get()
            # print('get {} {} {}'.format(
            #     self.command_queue[dev].qsize(), temp['command_name'], dev))
            self.current_command[dev] = temp['c'][temp['command_name']]
            self.current_command[dev].set_value(temp['value'], dev)
        return self.current_command[dev]

    def run_command(self, command_name, value=None, dev=None):
        if dev is not None:
            dev = self.config['uarts'][dev]['dev']
            self.queue_command(command_name, value, dev)
        else:
            for uart in self.config['uarts']:
                self.queue_command(command_name, value, self.config['uarts']
                                   [uart]['dev'])
        # print('command = {} dev = {}'.format(command_name, dev))

    def queue_command(self, command_name, value=None, dev=None):
        self.command_queue[dev].put({'c': self.c,
                                     'command_name': command_name,
                                     'value': value,
                                     'dev': dev})
        # print('put {} {} {}'.format(self.command_queue[dev].qsize(),
        #                             command_name, dev))

    def run(self):
        while True:
            # value = self.check_command_reply()
            print('run control ')
            time.sleep(1)
