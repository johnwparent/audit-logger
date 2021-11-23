import contextlib
import glob
import os
import threading
import sys

from typing import Any, Callable, Dict, List, MutableMapping, Optional, TextIO

from . import store


__loggers_stop = False


@contextlib.contextmanager
def lock_access(lock: threading.Lock):
    """
    Context manager syntatic sugar for lock
    aquisition and release
    """
    lock.aquire()
    yield
    lock.release()


class LogMetaData(dict):
    pass


class Message(object):
    """
    Represents one Log message
    """
    def __init__(self, content: str):
        self.content = content


class LoggerDaemon(object):
    """
    Logger Daemon recieveing and all individual log messages
    from the loggers themselves

    Holds a queue of log messages to be processed
    FIFO
    """
    def __init__(self, lock: threading.Lock):
        self.__q_lock = lock
        self.__message_queue = []

    def capture_message(self, msg: Message):
        if not self.__p_stop:
            with lock_access(self.__q_lock):
                self.__message_queue.append(msg)

    def poll(self):
        """
        Return True if there is an available capture, false otherwise
        does not remove capture
        """
        if self.__message_queue:
            return True
        return False

    def pop(self):
        """
        Return oldest capture, remove from queue
        """
        with lock_access(self.__q_lock):
            try:
                return self.__message_queue.pop(0)
            except IndexError:
                return None

    def pop_top(self):
        """
        Return newest capture, remove from queue
        """
        with lock_access(self.__q_lock):
            try:
                return self.__message_queue.pop(len(self.__message_queue)-1)
            except IndexError:
                return None

class Logger(object):
    """
    Representation of a log file
    Stores fs location, log formatting,
    """
    def __init__(self, name: str, file: TextIO, style: Callable, val: Optional[Callable]= None):
        self.name = name
        self.file = file
        self.style = style
        self.fd = None
        self.validator = val
        self.__generate_metadata()

    def __generate_metadata(self):
        self.metadata = LogMetaData(self.__dict__)

    def load(self):
        self.fd = open(self.file, 'r')
        if self.fd.seekable():
            self.fd.seek(whence=2)
        else:
            self.fd.read()

    def start_logging(self, monitor: threading.Condition, daemon: LoggerDaemon= None):
        while():
            with monitor:
                if __loggers_stop:
                    return
            _message = self.fd.read()
            new_message = Message(_message, self.style, self.metadata)  \
                if self.validator and self.validator(_message) else None
            # Assume logs are updated atomically
            if new_message:
                if daemon:
                    daemon.capture_message(new_message)


class LoadManager(object):
    """
    Reads from log aggregation endpoint, indexes and provides
    storage for the logs, as well as a runtime interface to query the logs.
    """
    def __init__(self, endpoint: LoggerDaemon, schema: store.Schema):
        self.__r_w_lock = threading.RLock()
        self.__p_thread = threading.Thread(target=self.__process_logs)
        self.endpoint = endpoint
        self.__p_stop = False
        self.tail = False
        self.local_store = {}
        self.schema = schema
        self.root = schema.root

    def __process_logs(self, message: Message):
        """
        Read messages from the connected endpoint.
        Store in local FS in structure defined by user schema

        Directories and filestores represent relational keypoints
        specified by the user
        """
        while(not self.__p_stop):
            if self.endpoint.poll():
                op = self.endpoint.pop
                if self.tail:
                    op = self.endpoint.pop_top
                with lock_access(self.__r_w_lock):
                    nxt_msg = op()
                if nxt_msg:
                    msg_pth = self.schema.compute_path(nxt_msg)
                    if self.schema.is_key(nxt_msg):
                        if not os.path.isdir(msg_pth):
                            os.mkdir(msg_pth)
                            with open(self.schema.agg_file(nxt_msg), 'w+') as f:
                                f.write(nxt_msg)
                                if nxt_msg.correlation_id not in self.local_store:
                                    self.local_store[nxt_msg.correlation_id] = f.name
                                else:
                                    for log in self.local_store[nxt_msg.correlation_id]:
                                        f.write(log)
                                    self.local_store[nxt_msg.correlation_id] = f.name
                    else:
                        if nxt_msg.correlation_id:
                            if nxt_msg.correlation_id not in self.local_store:
                                self.local_store[nxt_msg.correlation_id] = [nxt_msg]
                            elif type(self.local_store[nxt_msg.correlation_id]) == Message:
                                self.local_store[nxt_msg.correlation_id].append(nxt_msg)
                            else:
                                with open(self.local_store[nxt_msg.correlation_id], 'a') as f:
                                    f.write(nxt_msg)

    def start(self):
        self.__p_thread.start()

    def stop(self):
        self.__p_stop = True
        self.__p_thread.join()

    def query(self, query: str):
        pass


def start_logging(logs: List[Logger], log_attrs: List, manager_conf: Dict, cl_handler: Callable= None, detached= False):

    def interrupt(notifier: threading.Condition):
        with notifier:
            __loggers_stop = True
            notifier.notify_all()

    logdaemon = LoggerDaemon(threading.RLock())
    lm = LoadManager(logdaemon)
    cv_lock = threading.Lock()
    notifier = threading.Condition(cv_lock)
    for log in logs:
        threading.Thread(target=log.start_logging, args=[notifier, logdaemon]).start()
    lm.start()
    while(not detached):
        try:
            cl_handler(detached)
        # exit gracefully on user interrupt
        except KeyboardInterrupt:
            interrupt(notifier)
        finally:
            # effect graceful exit
            lm.stop()
            break

def build_logs(conf: MutableMapping[str, Any]):
    """
    Constructs and returns log objects based on settings established in config
    file.
    """
    attributes = []
    attributes.append(name = conf["log_name"])
    root = conf.get("root", os.path.join(os.environ.get("HOME"), ".logaudit","store"))
    attributes.append(root)
    logs = conf.get("logs", None)
    if not logs:
        raise RuntimeError("ParseError: Logs attribute required, not found")
    full_logs = []
    for l in logs:
        if type(logs[l]) is dict:
            log_extension = logs[l].get("ext", ".txt")
            log_names = logs[l].get("log_names", [])
            log_format = logs[l].get("format", "string")
            log_prefix = logs[l].get("log_prefix", "")
            if not log_prefix and not log_names:
                    raise RuntimeError("ParseError: log {} requires either log_prefix or log_names attribute".format(l))
            elif not log_names:
                # assume all files of type extension in log_prefix are to be parsed
                log_names = [found_log for found_log in glob.glob(os.path.join(log_prefix, "*" + log_extension))]
            gen_log = lambda x: Logger(x, os.path.join(log_prefix,x,log_extension), log_format)
            pylogs = [x for x in map(gen_log, log_names)]
            full_logs.extend(pylogs)
    return full_logs, attributes
