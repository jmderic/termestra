#!/usr/bin/env python3
# -*- coding: utf-8; fill-column: 88 -*-

import asyncio
import logging
import sys
from functools import wraps

import click
from tmx_util.app import AppBase
from tmx_util.misc import UsecFormatter, get_timestamp
from tmx_util.tmux import TmuxMgr


@click.group()
def cli():
    pass


def setup_logging(loglevel, wrkfn_prefix):
    formatter = UsecFormatter(
        "%(asctime)s %(levelname)s: %(message)s", datefmt="%Y%m%d_%H%M%S.%f"
    )
    fh = logging.FileHandler(f"{wrkfn_prefix}.log")
    fh.setFormatter(formatter)
    loglevel = getattr(logging, loglevel)
    logging.basicConfig(handlers=[fh], level=loglevel)
    logger = logging.getLogger(__name__)
    return logger


def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        task = asyncio.ensure_future(f(*args, **kwargs), loop=loop)
        loop.run_until_complete(task)
        rv = task.result()
        return rv if rv is not None else 0

    return wrapper


@cli.command()
@click.option(
    "--log-level",
    required=True,
    help="Log Level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    show_default=True,
)
@click.option(
    "--wrk-stub",
    required=True,
    help="The prefix for working files and the log file",
    default="/tmp/termestra",
    show_default=True,
)
@click.option(
    "--geometry",
    required=True,
    help="term geometry: <cols>x,rows+<hz_px>+<vt_px>",
    default="132x40+125+125",
    show_default=True,
)
@click.option(
    "--tab-names",
    required=True,
    help="Comma separated list of tab names",
    default="Tmux terminal",
    show_default=True,
)
@coro
async def base(**args):
    # setup the output file prefix
    ts = get_timestamp()
    wrkfn_prefix = f'{args["wrk_stub"]}-{sys.argv[1]}-{ts}'
    log_lvl_str = args["log_level"]

    logger = setup_logging(log_lvl_str, wrkfn_prefix)
    logger.info(f'Starting "{sys.argv[0]} {sys.argv[1]}"')

    tab_name_list = [x.strip() for x in args["tab_names"].split(",")]
    try:
        app = AppBase(args["geometry"], tab_name_list, wrkfn_prefix, log_lvl_str)
        rv = await app.run()
    except Exception:
        logger.exception(f'Exception in "{sys.argv[0]} {sys.argv[1]}"')
        rv = 99
    return rv


@cli.command()
@click.option(
    "--log-level",
    required=True,
    help="Log Level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    show_default=True,
)
@click.option(
    "--wrk-stub",
    required=True,
    help="The prefix for working files and the log file",
    default="/tmp/termestra",
    show_default=True,
)
@click.option(
    "--geometry",
    required=True,
    help="term geometry: <cols>x,rows+<hz_px>+<vt_px>",
    default="80x48+125+250",
    show_default=True,
)
@click.option(
    "--tab-names",
    required=True,
    help="Comma separated list of tab names",
    default="Tmux terminal",
    show_default=True,
)
def tmux(**args):
    # setup the output file prefix
    ts = get_timestamp()
    wrkfn_prefix = f'{args["wrk_stub"]}-{sys.argv[1]}-{ts}'

    logger = setup_logging(args["log_level"], wrkfn_prefix)
    logger.info(f'Starting "{sys.argv[0]} {sys.argv[1]}"')

    tab_name_list = [x.strip() for x in args["tab_names"].split(",")]
    tmux_mgr = TmuxMgr(args["geometry"], tab_name_list)
    for tab_name in tab_name_list:
        tmux_mgr.add_session(tab_name)

    return 0


if __name__ == "__main__":
    sys.exit(cli(standalone_mode=False))
