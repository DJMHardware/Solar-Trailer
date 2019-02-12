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
        self.complete_list = {}

    def start_commmand(self):
        super().start_commmand()
        self.complete_list = {}
        self.reply_buffer = {}

    def check_complete(self, dev):
        self.complete_list[dev] = True
        self.complete = None
        for k in self.complete_list:
            if (self.complete_list[k] is True
                    and (self.complete is True or self.complete is None)):
                self.complete = True
            else:
                self.complete = False
        super().check_complete(dev)

    def _machine_to_human(self, value, dev):
        reply = super()._machine_to_human(value, dev)
        return {dev: reply}


class AC_Charger_API(remote_api.RemoteAPI):
    @classmethod
    def class_init(cls):
        return super().class_init('accharger.toml',
                                  AC_Charger_RemoteCommandData)

    def __init__(self, threadID, config_file, remote_command_data_class):
        super().__init__(threadID, config_file, remote_command_data_class)
        self.handle_uart_t = uart_driver.Uart_Driver.class_init(self)

    def get_command(self, dev):
        c = None
        if (not self.command_queue.empty() and self.current_command is None):
            self.current_command = self.command_queue.get()
        if (self.current_command is not None
                and dev not in self.current_command.complete_list):
            self.current_command.complete_list[dev] = False
            c = self.current_command
        if c is not None and not len(c.complete_list):
            c.start_commmand()
        return c


control_test = AC_Charger_API.class_init()
control_test.run_command('set_voltage', 12)
control_test.run_command('set_output', 1)
control_test.run_command('read_actual_voltage')
control_test.run_command('read_actual_working_time')

while True:
    time.sleep(0.01)
