import remote_api
import uart_driver
import time


class BMS_RemoteCommandData(remote_api.RemoteCommandData):
    def __init__(self, command_name, command_dict, command_callback):
        super().__init__(command_name, command_dict, command_callback)
        if not hasattr(self, 'groupcmd'):
            print ('cmd = 0x{:04X}'.format(self.cmd))
            self._build_command_string()
            self._compute_reply_regex()
        else:
            self.cmd_done = []
            self.reply = []
            self.reply_buffer = []

    @classmethod
    def class_init(cls, command_dict, command_callback):
        for k in command_dict.copy():
            if 'cmds' in command_dict[k]:
                i = 0
                for cmd in command_dict[k]['cmds']:
                    i += 1
                    cmd_str = '0x{:04X}'.format(cmd)
                    command_dict[k + str(i)] = command_dict[k].copy()
                    command_dict[k + str(i)]['cmd'] = cmd
                    command_dict[k + str(i)]['parent_command'] = k
                    command_dict[k + str(i)]['span'] = (command_dict[k]
                                                        ['spans'][cmd_str])
                command_dict[k]['groupcmd'] = True
        return super().class_init(command_dict, command_callback)

    def start_commmand(self):
        super().start_commmand()
        if hasattr(self, 'groupcmd'):
            self.cmd_done = []
            self.reply_buffer = []

    def add_data(self, cmd, data, span):
        if cmd not in self.cmd_done:
            self.cmd_done.append(cmd)
        for i in range(span[1] - len(self.reply_buffer)):
            self.reply_buffer.append(None)
        for i in range(span[1] - span[0] + 1):
            self.reply_buffer[span[0] + i - 1] = data[i]
        done = True
        for cmd in self.cmds:
            done = bool(done and cmd in self.cmd_done)
        if done:
            self.reply = self._new_data_check(self.reply)
            self._command_callback(self.command_name,
                                   self.reply,
                                   self.new_data)


class BMS_API(remote_api.RemoteAPI):
    @classmethod
    def class_init(cls):
        return super().class_init('bmscontrol.toml', BMS_RemoteCommandData)

    def __init__(self, threadID, config_file, remote_command_data_class):
        super().__init__(threadID, config_file, remote_command_data_class)
        self.handle_uart_t = uart_driver.Uart_Driver.class_init(self)

    def _check_callback_group_command(self, command_name, values, new_data):
        if new_data and hasattr(self.c[command_name], 'parent_command'):
            c = self.c[command_name]
            p = self.c[c.parent_command]
            p.add_data(c.cmd, c.reply, c.span)

    def command_callback(self, command_name, values, new_data):
        self._check_callback_group_command(command_name, values, new_data)
        super().command_callback(command_name, values, new_data)

    def run_command(self, command_name, value=None):
        if hasattr(self.c[command_name], 'cmds'):
            self.c[command_name].start_commmand()
            for i in range(len(self.c[command_name].cmds)):
                self.command_queue.put(self.c[command_name + str(i + 1)])
        else:
            super().run_command(command_name, value)


control_bms = BMS_API.class_init()
control_bms.run_command('Relays Status')
control_bms.run_command('Pack Voltage')
control_bms.run_command('Cell Voltages')

while True:
    time.sleep(0.01)
