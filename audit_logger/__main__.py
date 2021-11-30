import argparse
import sys
import toml
from typing import Any, List

from . import alog


def main(argv: List[Any] = None):
    args = argparse.ArgumentParser(description="Aggregate and Stream Logs")
    sub_cmds = args.add_subparsers(required=True)
    c1 = sub_cmds.add_parser("start", help='start Audit Logger')
    c1.add_argument(
        "--config",
        action="store",
        dest="conf",
        required=True,
        help="Config file designating logs to aggregate\
            and streaming destination"
    )
    c1.add_argument(
        "--detached",
        "-d",
        action="store",
        required=False,
        default=True,
        dest='detached',
        help="Run Audit Logger in the background"
    )
    c1.set_defaults(command_mode=False)
    c1.set_defaults(status=False)

    c2 = sub_cmds.add_parser("C", help="Issue queries to Audit system")
    c2.add_argument('-Q',action='append',dest='queries')
    c2.set_defaults(command_mode=True)
    c2.set_defaults(status=False)

    c3 = sub_cmds.add_parser("status", help="Status of Audit System")
    c3.set_defaults(status=True)
    c3.set_defaults(command_mode=False)

    if not argv:
        argv = sys.argv[1:] if sys.argv[1:] else ['None']
    cmd_line = args.parse_args(argv)

    if cmd_line.command_mode:
        if alog.is_already_active():
            for rsp in alog.client([alog.Query(query) for query in cmd_line.queries]):
                print(rsp)
        else:
            raise alog.AuditLoggerError("Cannot issue query if no instance of Audit Logger is running")
    elif cmd_line.status:
        if alog.is_already_active():
            print("Audit Logger is active and running in the background.")
        else:
            print("Audit Logger is not active.")
    else:
        toml_logger_conf = toml.load(cmd_line.conf)
        logs, log_attrs = alog.build_logs(toml_logger_conf)
        alog.start_logging(logs, log_attrs, cmd_line.detached)


if __name__ == '__main__':
    main(sys.argv[1:])
