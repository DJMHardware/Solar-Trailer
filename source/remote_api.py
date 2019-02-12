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
        self.__dict__.update({'output_string': '',
                              'value_string': '',
                              'complete': {},
                              'reply': None,
                              'raw_reply': {},
                              'reply_buffer': {}})

    @classmethod
    def class_init(cls, command_dict, command_callback):
        c = {}
        for k in command_dict.copy():
            if k == 'Default':
                continue
            c[k] = cls(k, command_dict, command_callback)
        return c

    def _build_command_string(self):
        if hasattr(self, 'send_value_format'):
            self._human_to_machine()
        self.output_string = (self.cmd_format.format(self.cmd)
                              + self.value_string)
        if hasattr(self, 'mode'):
            self.output_string = ('{:02X}'.format(int((len(self.output_string)
                                                       / 2) + 1))
                                  + '{:02X}'.format(self.mode)
                                  + self.output_string)
        self.output_string = (self.prefix + self.output_string + self.suffix)

    def _human_to_machine(self):
        if (self.value is None):
            self.value = 0
        if self.value < self.range['min']:
            self.value = self.range['min']
        if self.value > self.range['max']:
            self.value = self.range['max']
        if self.range['scale'] is not 1:
            self.value = int(round(self.value / self.range['scale']))
        self.value_string = self.send_value_format.format(self.value)

    def _machine_to_human(self, values):
        print (values)
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
            if self.range['scale'] is not 1:
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

    def _compute_reply_regex(self):
        r = self.reply_regex
        if hasattr(self, 'payload'):
            p = self.payload
            p['length'] = ((p['encode'] * 2) * p['bytes'])
            self.reply_regex_prefix = (self.reply_prefix
                                       + '{:02X}'.format(int((p['length']
                                                              / 2) + 3))
                                       + '{:02X}'.format(self.mode + 0x40)
                                       + '{:02X}'.format(self.cmd))
            r += ('{' + str(p['length']) + '}')
        else:
            self.reply_regex_prefix = self.reply_prefix + self.cmd
        self.reply_regex_string = ('^' + self.reply_regex_prefix + r)

    def _new_data_check(self, reply):
        if reply != self.reply_buffer:
            reply = self.reply_buffer.copy()
            self.new_data = True
        else:
            self.new_data = False
        return reply

    def _compute_reply(self):
        if hasattr(self, 'single_uart') and self.single_uart:
            for k in self.raw_reply:
                self.reply = self.raw_reply[k]
                self.dev = k
        else:
            self.reply = self.raw_reply

    def _callback(self):
        self.waiting_on_data = False
        self._command_callback(self.command_name, self.reply, self.new_data)

    def set_value(self, value):
        if value is not None:
            if value != self.value:
                self.value = value
                self._build_command_string()

    def extract_values(self, value, dev):
        if not re.match(self.reply_regex_string, value):
            raise Exception('error uart {} returned bad string = {}'
                            .format(dev, value))
        value = re.sub(r'^' + self.reply_regex_prefix, '', value)
        # print ('reply value = ' + str(value))
        reply_regex_mod = ''
        if hasattr(self, 'payload'):
            reply_regex_mod = ('{' + str(self.payload['encode'] * 2) + '}')
        self.reply_buffer[dev] = self._machine_to_human(
            re.findall((self.reply_regex + reply_regex_mod), value))
        self.complete[dev] = True
        self.check_complete()

    def start_commmand(self):
        if self.waiting_on_data:
            raise Exception('{} waiting on data still'.format(
                self.command_name))
        self.complete = {}
        self.reply_buffer = {}
        self.waiting_on_data = True

    def check_complete(self):
        done = None
        for c in self.complete:
            if self.complete[c] is True and (done is True or done is None):
                done = True
            else:
                done = False
        if done is True:
            self.raw_reply = self._new_data_check(self.raw_reply)
            self._compute_reply()
            self._callback()


class RemoteAPI(threading.Thread):
    counter = 0

    @classmethod
    def class_init(cls, config_file, remote_command_data_class):
        cls.counter += 1
        threadID = 'control_' + str(cls.counter)
        handle_control_t = cls(threadID, config_file,
                               remote_command_data_class)
        handle_control_t.daemon = True
        handle_control_t.start()
        return handle_control_t

    def __init__(self, threadID, config_file, remote_command_data_class):
        threading.Thread.__init__(self)
        self.threadLock = threading.Lock()
        self.threadID = threadID
        self.command_queue = queue.Queue()
        self.current_command = None
        config_path = os.path.join((os.path.split
                                    (os.path.split
                                     (sys.argv[0])[0])[0]),
                                   'config')
        with open(os.path.join(config_path, config_file)) as f:
            self.config = toml.load(f, _dict=dict)

        self.c = remote_command_data_class.class_init(self.config['command'],
                                                      self.command_callback)

    def _check_callback_group_command(self, command_name, values, new_data):
        if new_data and hasattr(self.c[command_name], 'parent_command'):
            c = self.c[command_name]
            p = self.c[c.parent_command]
            p.add_data(c.cmd, c.reply, c.span)

    def command_callback(self, command_name, values, new_data):
        self.current_command = None
        if new_data:
            print ('{} = {}'.format(command_name, values))

    def get_command(self, dev):
        c = None
        if (not self.command_queue.empty() and self.current_command is None):
            self.current_command = self.command_queue.get()
        if (self.current_command is not None
                and dev not in self.current_command.complete):
            self.current_command.complete[dev] = False
            c = self.current_command
        if c is not None:
            c.start_commmand()
        return c

    def run_command(self, command_name, value=None):
            self.c[command_name].set_value(value)
            self.command_queue.put(self.c[command_name])

    def run(self):
        while True:
            # value = self.check_command_reply()
            print ('run control ')
            time.sleep(1)
