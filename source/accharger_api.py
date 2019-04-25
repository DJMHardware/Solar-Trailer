import remote_api
import uart_driver
import time


class AC_Charger_RemoteCommandData(remote_api.RemoteCommandData):
    def __init__(self, command_name, command_dict, command_callback):
        super().__init__(command_name, command_dict, command_callback)
        self._build_command_string()
        self._compute_reply_regex()
        self.raw_reply = {}
        self.reply_buffer = {}
        self.complete = {}

    def start_commmand(self):
        super().start_commmand()
        self.complete = {}
        self.reply_buffer = {}

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
            self._callback()


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

    def get_command(self, dev):
        c = None
        if (not self.command_queue.empty() and self.current_command is None):
            self.current_command = self.command_queue.get()
        if (self.current_command is not None
                and dev not in self.current_command.complete):
            self.current_command.complete[dev] = False
            c = self.current_command
        if c is not None and not len(c.complete):
            c.start_commmand()
        return c


control_test = AC_Charger_API.class_init()
control_test.run_command('set_voltage', 56)
control_test.run_command('set_current', 2)
control_test.run_command('set_output', 1)
control_test.run_command('set_auto_output', 1)
control_test.run_command('read_actual_voltage')
control_test.run_command('read_actual_current')
control_test.run_command('read_actual_working_time')

while True:
    control_test.run_command('read_actual_voltage')
    control_test.run_command('read_actual_current')
    time.sleep(1)
