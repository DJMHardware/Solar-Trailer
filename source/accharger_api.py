import remote_api
import uart_driver
import time
import queue


class AC_Charger_RemoteCommandData(remote_api.RemoteCommandData):
    def __init__(self, command_name, command_dict, command_callback):
        super().__init__(command_name, command_dict, command_callback)
        # self._build_command_string()
        self._compute_reply_regex()
        self.raw_reply = {}
        self.reply_buffer = {}
        self.complete = {}

    def start_commmand(self, dev):
        print('*****{} = {}'.format(self.command_name, self.complete))
        if hasattr(self.waiting_on_data, dev) and self.waiting_on_data[dev]:
            raise Exception('{} {} waiting on data still'.format(
                dev, self.command_name))
        self.waiting_on_data[dev] = True
        #self.raw_reply = {}
        #self.reply_buffer = {}

    def _new_data_check(self, reply):
        super()._new_data_check(reply)
        return reply.copy()

    def return_values(self, value, dev):
        self.reply_buffer[dev] = self.extract_values(value, dev)
        self.complete[dev] = True
        done = None
        for k in self.complete:
            if (self.complete[k] is True
                    and (done is True or done is None)):
                done = True
            else:
                done = False
        if done:
            self._callback(dev)


class AC_Charger_API(remote_api.RemoteAPI):
    @classmethod
    def class_init(cls,
                   config_file='accharger.toml',
                   remote_command_data_class=AC_Charger_RemoteCommandData,
                   threaded=False):
        return super().class_init(config_file, remote_command_data_class,
                                  threaded)

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.handle_uart_t = uart_driver.Uart_Driver.class_init(self)

    def old_get_command(self, dev):
        c = None
        if (not self.command_queue.empty() and self.current_command is None):
            temp = self.command_queue.get()
            print('{} = {}'.format(temp['dev'], dev))
            if ((temp['dev'] is not None) and (temp['dev'] != dev)):
                return c
            self.current_command = temp['c'][temp['command_name']]
            self.current_command.set_value(temp['value'])
            print('get {}'.format(self.command_queue.qsize()))
            print(self.current_command)
        if (self.current_command is not None
                and dev not in self.current_command.complete):
            self.current_command.complete[dev] = False
            print('complete = {}'.format(self.current_command.complete))
            c = self.current_command
            new = False
            for complete in self.current_command.complete:
                if not complete:
                    new = True
        if c is not None and new:
            print('start_commmand')
            c.start_commmand()
        return c


control_test = AC_Charger_API.class_init()
print(control_test.config["uarts"])
control_test.run_command('set_voltage', 56)
control_test.run_command('set_current', 2)
control_test.run_command('set_output', 1)
control_test.run_command('set_auto_output', 1)
control_test.run_command('read_actual_current')
control_test.run_command('read_actual_working_time')
control_test.run_command('read_actual_voltage')
time.sleep(1)
control_test.run_command('set_voltage', 57, 'uart0')
time.sleep(1)
control_test.run_command('read_actual_voltage')

while True:
    time.sleep(1)
    # control_test.run_command('read_actual_current')
    # control_test.run_command('read_actual_working_time')
