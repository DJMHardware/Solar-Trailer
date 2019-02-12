import remote_api
import uart_driver
import time


class AC_Charger_RemoteCommandData(remote_api.RemoteCommandData):
    def __init__(self, command_name, command_dict, command_callback):
        super().__init__(command_name, command_dict, command_callback)
        self._build_command_string()
        self._compute_reply_regex()


class AC_Charger_API(remote_api.RemoteAPI):
    @classmethod
    def class_init(cls):
        return super().class_init('accharger.toml',
                                  AC_Charger_RemoteCommandData)

    def __init__(self, threadID, config_file, remote_command_data_class):
        super().__init__(threadID, config_file, remote_command_data_class)
        self.handle_uart_t = uart_driver.Uart_Driver.class_init(self)


control_test = AC_Charger_API.class_init()
control_test.run_command('set_voltage', 12)
control_test.run_command('set_output', 1)
control_test.run_command('read_actual_voltage')
control_test.run_command('read_actual_working_time')

while True:
    time.sleep(0.01)