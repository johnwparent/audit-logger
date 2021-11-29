import argparse
import sys
import toml
from typing import Any, List

from . import alog


def main(argv: List[Any] = None):
    args = argparse.ArgumentParser(description="Aggregate and Stream Logs")
    args.add_argument(
        "--config",
        action="store",
        dest="conf",
        required=True,
        help="Config file designating logs to aggregate\
            and streaming destination"
    )
    args.add_argument(
        "--detached",
        "-d",
        action="store",
        required=False,
        default=False,
        help="Run Audit Logger in the background"
    )
    args.add_argument(
        "-f",
        "--feed",
        action='store',
        dest="feed",
        required=False,
        default=False
    )
    args.add_argument(
        "-C",
        action='store',
    )
    cmd_line = args.parse_args(argv if argv else sys.argv[1:])
    if cmd_line.command_mode:
        for rsp in alog.client(cmd_line.queries):
            print(rsp)

    else:
        toml_logger_conf = toml.load(cmd_line.conf)
        logs, log_attrs = alog.build_logs(toml_logger_conf)
        alog.start_logging(logs, log_attrs)


if __name__ == '__main__':
    main(sys.argv[1:])
