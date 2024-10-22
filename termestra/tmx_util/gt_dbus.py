# -*- coding: utf-8; fill-column: 88 -*-

import copy
import logging
import os
import re

from .misc import run_cmd

logger = logging.getLogger(__name__)


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
        # self.gts[0] will be the suffix to "/org/gnome/Terminal/screen/"
        self.gts = None

    def create_tmux_window(self, geom, name):
        environ = copy.deepcopy(os.environ)
        environ["GNOME_TERMINAL_SCREEN"] = ""
        cmd = f'gnome-terminal --window -t "{name}" --geometry={geom} -e tmux'
        dbus_gt = DBus()
        before = dbus_gt.get_node_list()
        run_cmd(cmd, env=environ)
        after = dbus_gt.get_node_list()
        self.gts = frozenset(after) - frozenset(before)
        logger.debug(f"The new GNOME_TERMINAL_SCREEN uid is in the set {self.gts}")

    def get_create_tmux_tab_command(self, name):
        # 2> /dev/null gets rid of the -e deprecation warning
        return f'gnome-terminal --tab -t "{name}" -e tmux 2> /dev/null'
