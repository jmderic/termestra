# -*- coding: utf-8; fill-column: 88 -*-

import datetime
import logging
import subprocess

logger = logging.getLogger(__name__)


def get_ts_fm_dt(dt):
    return dt.strftime("%Y%m%d_%H%M%S")


def get_us_fm_dt(dt):
    return dt.strftime("%Y%m%d_%H%M%S.%f")


def get_timestamp():
    dt_now = datetime.datetime.now()
    return get_ts_fm_dt(dt_now)


def get_timestamp_us():
    dt_now = datetime.datetime.now()
    return get_us_fm_dt(dt_now)


class file_write_functor:
    def __init__(self, filename):
        self.f = open(filename, "w")

    def __call__(self, string):
        self.f.write(string + "\n")

    def __del__(self):
        self.f.close()


class log_functor(file_write_functor):
    def __init__(self, filename):
        file_write_functor.__init__(self, filename)

    def __call__(self, string):
        file_write_functor.__call__(self, f"{get_timestamp_us()} {string}")

    def __del__(self):
        file_write_functor.__del__(self)


class OutputFunctorGenerator:
    """ """

    def __init__(self, output_base_):
        self.output_base = output_base_

    def __call__(self, extension, *, log=False):
        if log:
            return log_functor(self.output_base + extension)
        return file_write_functor(self.output_base + extension)


def get_cmd_results(c, rc, out, err):
    status = "succeeds" if rc == 0 else "fails"
    return f'run_cmd "{c}" {status}:\nstdout:\n{out.strip()}\nstderr:\n{err.strip()}'


class TermestratorError(RuntimeError):
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


def run_cmd(c, *, input=None, env=None):
    input_pipe = subprocess.PIPE if input else None
    use_shell_expansion = isinstance(c, str)
    p = subprocess.Popen(
        c,
        stdin=input_pipe,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=use_shell_expansion,
        text=True,
        env=env,
    )
    (out, err) = p.communicate(input)
    rc = p.returncode

    logger.debug(get_cmd_results(c, rc, out, err))

    if rc != 0:
        raise TermestratorError(f"'{c}' failed with the message:\n{err.strip()}")
    return out


class UsecFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        if not datefmt:
            return super().formatTime(record, datefmt=datefmt)

        # fmt: off
        # the page where i got the hint to do this
        # https://stackoverflow.com/questions/75035056/microsecond-do-not-work-in-python-logger-format
        # suggested this return:
        # return datetime.fromtimestamp(record.created).astimezone().strftime(datefmt)
        # fmt: on
        return datetime.datetime.fromtimestamp(record.created).strftime(datefmt)
