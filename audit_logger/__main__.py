import argparse
import os
import sys
import threading
import toml
import glob
import os
from typing import Any, List, MutableMapping

from . import alog


def cl_handler(live: bool):
    pass

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
        help="Run Audit Logger in the background"
    )
    cmd_line = args.parse_args(argv if argv else sys.argv[1:])
    toml_logger_conf = toml.load(cmd_line.conf)
    logs, log_attrs = alog.build_and_validate_logs(toml_logger_conf)
    alog.start_logging(logs, log_attrs, cl_handler=cl_handler)


if __name__ == '__main__':
    main(sys.argv[1:])
