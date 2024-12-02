# -*- coding: utf-8; fill-column: 88 -*-

import asyncio
import logging
import os
from functools import partial
from io import BytesIO
from signal import SIGINT, SIGTERM, Signals

from . import tmux
from .misc import run_cmd

logger = logging.getLogger(__name__)


class AppBase:
    # the model is that AppBase only accesses tms members that AppBase has attached;
    # AppBase obtain any other tms info by calling self.tmux_mgr.get_<what_we_need>();
    # so tms is an opaque container
    def __init__(
        self, geom, tab_name_list, wrk_stub, loglevel, housekeeping_interval=1, app=None
    ):
        self.tmux_mgr = tmux.TmuxMgr(geom, tab_name_list)
        self.loglevel = loglevel
        self.loop = None
        self.housekeeping_interval = housekeeping_interval
        self.housekeeping_counter = 0
        self.sigs = (SIGINT, SIGTERM)
        self.halt = False  # stop requested
        self.done = False  # stop procedures complete
        self.app = app

        # data_received line buffering support
        self.b_siz = 4096

        for sess_name in tab_name_list:
            # the model is that AppBase only accesses tms members that AppBase has
            # attached; AppBase obtains any other tms info by calling a self.tmux_mgr
            # get_<what_we_need>(sess_name) function; here, tms is an opaque container
            tms = self.tmux_mgr.add_session(sess_name)
            sess_num = self.tmux_mgr.get_num(sess_name)
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
            logger.debug(f"TMTR: {pipe_pane_cmd=}")
            run_cmd(pipe_pane_cmd)
            # add pipe's transport to the TmuxSession object
            tms.transport = None
            # add data_received handling support to the TmuxSession object
            tms.line_buffer = BytesIO()
            tms.next_line_pos = 0
            tms.anti_chatter = 0
            tms.stub = b""

    async def _connect_pipe(self, sess_name, pipe):
        tp = await self.loop.connect_read_pipe(
            lambda: AppBasePipeReadProto(self, sess_name), pipe  # noqa: B023
        )
        return tp

    def connection_made(self, sess_name, transport):
        logger.info(f"TMTR: connection_made: {sess_name=} with {transport=!r}")
        if self.app:
            self.app.conn_made(sess_name)

    def connection_lost(self, sess_name, exc):
        logger.info(f"TMTR: connection_lost: {sess_name=}")
        if self.app:
            self.app.conn_lost(sess_name, exc)

    def data_received(self, sess_name, data):
        logger.debug(f"TMTR: data_received {sess_name=}; {data=}")
        tms = self.tmux_mgr.get_session(sess_name)

        tms.line_buffer.write(data)

        tms.line_buffer.seek(tms.next_line_pos)
        stub = tms.line_buffer.read()
        lines = []
        last_crlf = stub.rfind(b"\r\n")
        if last_crlf != -1:
            tms.next_line_pos += last_crlf + 2
            lines = stub[:last_crlf].split(b"\r\n")
            stub = stub[last_crlf + 2 :]
            self.data_to_app(sess_name, lines, stub)
        else:
            tms.stub = stub
        logger.debug(
            f"TMTR: data_received {sess_name=}; {tms.next_line_pos=}; "
            f"{tms.line_buffer.tell()=}"
        )

    def data_to_app(self, sess_name, lines, stub):
        logger.debug(f"TMTR: data_to_app {sess_name=}; {lines=}; {stub=}")
        tms = self.tmux_mgr.get_session(sess_name)
        tms.anti_chatter = self.housekeeping_counter
        tms.stub = b""
        if self.app:
            self.app.data_recv(sess_name, lines, stub)

    def send_cmd(self, sess_name, cmd):
        logger.debug(f"TMTR: send_cmd {sess_name=}; {cmd=}")
        self.tmux_mgr.send_cmd(sess_name, cmd)

    def housekeeping(self):
        if self.app:
            self.app.housekeeping()  # return value to control behaviors below?
        if self.halt:
            logger.debug("TMTR: housekeeping called to halt")
            for sess_name in self.tmux_mgr.tmux_session_map:
                tms = self.tmux_mgr.get_session(sess_name)
                if not tms.transport.is_closing():
                    tms.transport.close()
                os.remove(tms.pipe)
            for sig in self.sigs:
                self.loop.remove_signal_handler(sig)
            self.done = True
            return
        for sess_name in self.tmux_mgr.tmux_session_map:
            tms = self.tmux_mgr.get_session(sess_name)
            if tms.stub and tms.anti_chatter != self.housekeeping_counter:
                logger.debug(f"TMTR: housekeeping pushes stub to {sess_name=}")
                self.data_to_app(sess_name, [], tms.stub)
        self.housekeeping_counter += 1

        self.next_time += self.housekeeping_interval
        self.loop.call_at(self.next_time, self.housekeeping)

    def handle_sig(self, sig):
        logger.info(f"TMTR: handle_sig: {Signals(sig).name=}")
        self.halt = True

    async def run(self):
        logger.info("TMTR: AppBase run")
        self.loop = asyncio.get_event_loop()
        self.loop.set_debug(True if self.loglevel == "DEBUG" else False)
        for sess_name in self.tmux_mgr.tmux_session_map:
            tms = self.tmux_mgr.get_session(sess_name)
            pipe = open(tms.pipe)
            tp = await self._connect_pipe(sess_name, pipe)
            tms.transport = tp[0]
        for sig in self.sigs:
            self.loop.add_signal_handler(sig, partial(self.handle_sig, sig))
        self.next_time = self.loop.time() + self.housekeeping_interval
        self.loop.call_at(self.next_time, self.housekeeping)
        while not self.done:
            await asyncio.sleep(2)

        return 0

    def __repr__(self):
        return f"<{self.__class__.__name__}>"


class AppBasePipeReadProto(asyncio.protocols.Protocol):
    def __init__(self, base, sess_name):
        self.base = base
        self.sess_name = sess_name

    def connection_made(self, transport):
        self.base.connection_made(self.sess_name, transport)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} base={self.base!r} sess_name={self.sess_name}>"
        )

    def connection_lost(self, exc):
        self.base.connection_lost(self.sess_name, exc)

    def data_received(self, data):
        self.base.data_received(self.sess_name, data)

    def eof_received(self):
        return False
