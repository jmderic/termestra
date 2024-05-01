# -*- coding: utf-8; fill-column: 88 -*-

import logging
import time

import libtmux

from .gt_dbus import GnomeTerm
from .misc import TermestratorError

logger = logging.getLogger(__name__)


class TmuxSession:
    def __init__(self, name, session):
        self.name = name
        self.sess = session
        self.pane = self.sess.active_pane

    def send_cmd(self, cmd):
        self.pane.send_keys(cmd)


class TmuxMgr:
    def __init__(self, geom, session_names):
        self.svr = libtmux.Server()
        self.gt = GnomeTerm()
        self.geom = geom
        self.last_session = None
        self.tmux_session_map = {}
        for session_name in session_names:
            if session_name in self.tmux_session_map:
                raise TermestratorError(f"Duplicate session name: {session_name}")
            self.tmux_session_map[session_name] = None

    def get_new_session(self, start_sessions):
        """! Gets the newly created session and insures it is ready to be used.

        There are two external completion events that occur after the completion of the
        python command.  They are as follow:

        1) Session information is available from the tmux server; and
        2) the bash prompt is available in the tmux pane

        This function checks that both of those events have occurred before returning.
        """
        start_count = len(start_sessions)

        now_sessions = self.svr.sessions
        new_count = len(now_sessions) - start_count
        logger.debug(f"Creating session {start_count + 1}; new_count {new_count}")
        while new_count < 1:
            time.sleep(0.1)
            now_sessions = self.svr.sessions
            new_count = len(now_sessions) - start_count
            logger.debug(f"Creating session {start_count + 1}; new_count {new_count}")

        new_sessions = []
        for session in now_sessions:
            if session not in start_sessions:
                new_sessions.append(session)

        if len(new_sessions) != 1:
            raise TermestratorError(
                "More than one new tmux session "
                f"while creating session {start_count + 1}"
            )

        pane_size = len(new_sessions[0].active_pane.capture_pane())
        logger.debug(f"Creating session {start_count + 1}; pane_size {pane_size}")
        while pane_size == 0:
            time.sleep(0.1)
            pane_size = len(new_sessions[0].active_pane.capture_pane())
            logger.debug(f"Creating session {start_count + 1}; pane_size {pane_size}")

        return new_sessions[0]

    def add_session(self, name):
        if name not in self.tmux_session_map:
            raise TermestratorError(f"Can not add unknown session: {name}")
        start_sessions = self.svr.sessions
        if self.last_session is None:
            self.gt.create_tmux_window(self.geom, name)
        else:
            cmd = self.gt.get_create_tmux_tab_command(name)
            self.last_session.send_cmd(cmd)
        new_session = self.get_new_session(start_sessions)
        self.last_session = TmuxSession(name, new_session)
        self.tmux_session_map[name] = self.last_session
        logger.info(f'TmuxMgr.add_session() adds {new_session} named "{name}"')
