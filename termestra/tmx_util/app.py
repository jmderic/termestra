# -*- coding: utf-8; fill-column: 88 -*-

import asyncio
import logging
import os
from functools import partial
from signal import SIGINT, SIGTERM, Signals
from time import time

from . import tmux
from .misc import run_cmd

logger = logging.getLogger(__name__)


class AppBase:
    def __init__(self, geom, tab_name_list, wrk_stub, loglevel):
        self.tmux_mgr = tmux.TmuxMgr(geom, tab_name_list)
        self.loglevel = loglevel
        self.loop = None
        self.timer_interval = 5
        self.sigs = (SIGINT, SIGTERM)
        self.halt = False  # stop requested
        self.done = False  # stop procedures complete

        # data_received line buffering support
        self.b_siz = 4096

        for sess_name in tab_name_list:
            self.tmux_mgr.add_session(sess_name)
            tms = self.tmux_mgr.tmux_session_map[sess_name]
            sess_num = tms.sess.id[1:]
            # add pipe's filesystem path to the TmuxSession object
            tms.pipe = f"{wrk_stub}-pipe-{sess_num}"
            # create fifo
            os.mkfifo(tms.pipe)
            # command in bash: tmux pipep -t \$0:@0 'cat > /tmp/termestra-pipe'
            pipe_pane_cmd = [
                "tmux",
                "pipep",
                "-t",
                f"${sess_num}:0",
                f"cat > {tms.pipe}",
            ]
            logger.debug(f"pipe_pane_cmd: {pipe_pane_cmd}")
            run_cmd(pipe_pane_cmd)
            # add disconnected status and pipe's transport to the TmuxSession object
            tms.disconnected = None
            tms.transport = None
            # add data_received line buffering support to the TmuxSession object
            tms.line_start_time = None
            # revisit memoryview buffering
            tms.line_buffer = memoryview(bytearray(self.b_siz))
            tms.b_start = 0

    async def _connect_pipe(self, sess_name, pipe):
        tp = await self.loop.connect_read_pipe(
            lambda: AppBasePipeReadProto(self, sess_name), pipe  # noqa: B023
        )
        return tp

    def connection_made(self, sess_name, transport):
        tms = self.tmux_mgr.tmux_session_map[sess_name]
        tms.disconnected = False
        logger.info(f"connection_made: '{sess_name}' with transport {transport!r}")

    def connection_lost(self, sess_name, exc):
        tms = self.tmux_mgr.tmux_session_map[sess_name]
        tms.disconnected = True
        logger.info(f"connection_lost: '{sess_name}'")
        if exc is not None:
            raise exc

    def data_received(self, sess_name, data):
        d_siz = len(data)
        tms = self.tmux_mgr.tmux_session_map[sess_name]
        logger.debug(f"data_received '{sess_name}'")
        now = time()
        if tms.line_start_time is None:
            tms.line_start_time = now

        get_start = 0
        b_room = None
        while True:
            # choke on the number of copies we make FIXME
            if get_start:
                d_siz -= b_room
            b_room = self.b_siz - tms.b_start
            end = tms.b_start + (b_room if d_siz > b_room else d_siz)
            logger.debug(
                f"recv_loop get_start: {get_start}; d_siz: {d_siz}; "
                f"b_start: {tms.b_start}; b_room: {b_room}; end: {end}"
            )
            if d_siz > b_room:
                tms.line_buffer[tms.b_start :] = data[get_start : get_start + b_room]
                get_start += b_room
                data_fits = False
            else:
                tms.line_buffer[tms.b_start : end] = data[get_start:]
                data_fits = True

            snippet = bytes(tms.line_buffer[:end])
            # lines is a copy out
            lines = snippet.split(b"\r\n")
            line_count = len(lines)
            if line_count > 1:
                # there are some complete lines
                residual = lines[line_count - 1]
                residual_siz = len(residual)
                if residual_siz > 0:
                    tms.line_buffer[:residual_siz] = residual
                    lines[line_count - 1] = b""
                    tms.b_start = residual_siz
                else:
                    tms.b_start = 0
                self.data_to_app(sess_name, lines)
                if data_fits:
                    break
            else:  # only one line, no \r\n
                if data_fits:
                    tms.b_start += d_siz
                    break
                else:
                    tms.b_start = 0
                    self.data_to_app(sess_name, lines)

    def data_to_app(self, sess_name, lines):
        logger.debug(f"data_to_app '{sess_name}' -- lines: {lines}")

    def housekeeping(self):
        if self.halt:
            logger.debug("housekeeping called to halt")
            for sess_name in self.tmux_mgr.tmux_session_map:
                tms = self.tmux_mgr.tmux_session_map[sess_name]
                if not tms.transport.is_closing():
                    tms.transport.close()
            for sig in self.sigs:
                self.loop.remove_signal_handler(sig)
            self.done = True
            return

        self.next_time += self.timer_interval
        self.loop.call_at(self.next_time, self.housekeeping)

    def handle_sig(self, sig):
        logger.info(f"handle_sig: {Signals(sig).name}")
        self.halt = True

    async def run(self):
        logger.info("run")
        self.loop = asyncio.get_event_loop()
        self.loop.set_debug(True if self.loglevel == "DEBUG" else False)
        for sess_name in self.tmux_mgr.tmux_session_map:
            tms = self.tmux_mgr.tmux_session_map[sess_name]
            pipe = open(tms.pipe)
            tp = await self._connect_pipe(sess_name, pipe)
            tms.transport = tp[0]
        for sig in self.sigs:
            self.loop.add_signal_handler(sig, partial(self.handle_sig, sig))
        self.next_time = self.loop.time() + self.timer_interval
        self.loop.call_at(self.next_time, self.housekeeping)
        while not self.done:
            await asyncio.sleep(2)

        return 0

    def __repr__(self):
        return f"<{self.__class__.__name__}>"


class AppBasePipeReadProto(asyncio.protocols.Protocol):
    def __init__(self, app, sess_name):
        self.app = app
        self.sess_name = sess_name

    def connection_made(self, transport):
        self.app.connection_made(self.sess_name, transport)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} app={self.app!r} sess_name={self.sess_name}>"
        )

    def connection_lost(self, exc):
        self.app.connection_lost(self.sess_name, exc)

    def data_received(self, data):
        self.app.data_received(self.sess_name, data)

    def eof_received(self):
        return False
