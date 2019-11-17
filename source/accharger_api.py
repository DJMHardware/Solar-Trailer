import threading
import temperature_api
import remote_api
import uart_driver
import time
import queue


class AC_TemperatureData(temperature_api.TemperatureData):
    def __init__(self, id, value, config_dict):
        super().__init__(id, value, config_dict)


class AC_TemperatureAPI(temperature_api.TemperatureAPI):
    @classmethod
    def class_init(cls,
                   config_file='accharger.toml',
                   temperature_data_class=AC_TemperatureData,
                   threaded=False):
        return super().class_init(config_file, temperature_data_class,
                                  threaded)

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)


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
        self._callback(dev)
        return
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
                   threaded=True):
        return super().class_init(config_file, remote_command_data_class,
                                  threaded)

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.handle_uart_t = uart_driver.Uart_Driver.class_init(self)
        self.started = False

    def set(self, value):
        s = True

    def run(self):
        time.sleep(1)
        while True:
            pending_commands = False
            for key, value in self.command_queue.items():
                # print('{} queue size = {}'.format(key, value.qsize()))
                if value.qsize():
                    pending_commands = True
            if not pending_commands:
                self.run_command('read_actual_current')
                self.run_command('read_actual_voltage')
            time.sleep(1)


class AC_Charger_Control(threading.Thread):
    @classmethod
    def class_init(cls, caller):
        print('init Charger_Control')
        handle_control_t = cls('control', caller)
        handle_control_t.daemon = True
        handle_control_t.start()
        return handle_control_t

    def __init__(self, threadID, caller):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.caller = caller
        self.config = caller.config

    def run(self):
        while True:
            pending_commands = False
            for key, value in self.caller.command_queue.items():
                # print('{} queue size = {}'.format(key, value.qsize()))
                if value.qsize():
                    pending_commands = True
            if not pending_commands:
                self.caller.run_command('read_actual_current')
                self.caller.run_command('read_actual_voltage')
            time.sleep(1)


control_test = AC_Charger_API.class_init()
temperature_api = AC_TemperatureAPI.class_init()
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
control_test.run_command('set_output', 0, 'uart0')
time.sleep(1)
control_test.run_command('read_actual_voltage')
# control_test.startr()

while True:
    time.sleep(1)
    # control_test.run_command('read_actual_current')
    # control_test.run_command('read_actual_working_time')
