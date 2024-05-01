# -*- coding: utf-8; fill-column: 88 -*-

import os
import re

from .misc import run_cmd


class DBus:
    def __init__(self):
        self.p_node = re.compile(
            r"^  <node name="
            r'"([0-9a-f]{8}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{4}_[0-9a-f]{12})"/>$'
        )

    def get_node_list(self):
        # a different command flavor
        # dbus-send --session --type=method_call --print-reply --dest=org.gnome.Terminal
        # /org/gnome/Terminal/screen/295b6208_4798_466e_92b8_89d152b14c72
        # org.freedesktop.DBus.Introspectable.Introspect
        cmd = (
            "dbus-send --session --type=method_call --print-reply "
            "--dest=org.gnome.Terminal /org/gnome/Terminal/screen "
            "org.freedesktop.DBus.Introspectable.Introspect"
        )
        output = run_cmd(cmd)
        out_list = output.split("\n")
        node_list = []
        for line in out_list:
            m = self.p_node.match(line)
            if m:
                node_list.append(m.group(1))
                # print(m.group(1))
        return node_list


class GnomeTerm:
    def __init__(self):
        self.dbus_gt = DBus()

    def get_environ(self):
        environ = os.environ
        node_list = self.dbus_gt.get_node_list()
        environ["GNOME_TERMINAL_SCREEN"] = f"/org/gnome/Terminal/screen/{node_list[0]}"
        return environ

    def create_tmux_window(self, geom, name):
        cmd = f'gnome-terminal --window -t "{name}" --geometry={geom} -e tmux'
        run_cmd(cmd, env=self.get_environ())

    def get_create_tmux_tab_command(self, name):
        # 2> /dev/null gets rid of the -e deprecation warning
        return f'gnome-terminal --tab -t "{name}" -e tmux 2> /dev/null'
