import contextlib
import glob
import json
import os
import pprint
import sys
import threading

from multiprocessing.connection import Client, Listener
from typing import Any, Callable, Dict, List, MutableMapping, Optional, TextIO


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


class AuditLoggerError(RuntimeError):
    """
    Wrapper around traditional RuntimeError
    """
    pass


class QueryResponse(object):
    """
    Representation of response from Log Auditor
    with all log messages matching the requested attributes
    """
    def __init__(self, messages):
        self.messages = messages

    def genereate_response(self):
        return "\n".join(self.messages)


class Query(object):
    """
    A user created query specified by CL. Defined by schema:
    <log_attibute>=<value>

    or

    <log_attribute>.<log_attribute>=<value>
    ... etc.
    Multiple values can be chanined by ';' or multiple
    command line arguments to '-Q'
    """
    def __init__(self, query):
        self.query = query
        self.__parse()
        self.STOP = False

    def __parse(self):
        if self.query == 'STOP':
            self.STOP = True
            return
        queries = self.query.split(';')
        for query in queries:
            key, val = query.split('=')
            self.__setattr__(key, val)

    def get(self, attribute):
        """
        Aquire terms from Query
        """
        attr = self.__dict__.get(attribute)
        if attr:
            return attr
        return self.attribute


class LogMetaData(dict):
    """
    Wrapper around dictionary
    """
    pass


class Message(object):
    """
    Represents one Log message
    """
    def __init__(self, content: str, metadata):
        self.content = content
        self.parsed_content = metadata['style'](self.content)
        self.metadata = metadata

    def __str__(self):
        return pprint.pformat(self.parsed_content)

    def __getattribute__(self, __name: str):
        attr = self.parsed_content.get(__name)
        if attr:
            return attr
        return super().__getattribute__(__name)


class Schema(object):
    """
    Representation of the audited log schema on the local filesystem
    Relates user defined schema to file system location, relates log
    messages via defined attributes to arrgegate log files in specified
    directories
    """
    def __init__(self, schema: MutableMapping[str, Any], name: str, root: str):
        self.key = schema['key']
        self.name = name
        self.root = root
        self.key_type = schema['key_type']
        self.relator = [schema['relator']]
        self.lookup_keys = []
        self.root_key = (schema.keys() - set(['key', 'key_type', 'relator'])).pop()
        schema_root = schema[self.root_key]
        self.file_schema = [self.root_key]
        self.attribute_keys = set(['relator','lookup'])
        self._key_check = self.attribute_check
        self.__process_structure(schema_root)
        self.__process_lookup_schema()

    def __process_lookup_schema(self):
        if self.key_type == "file":
            self._key_check = self.file_check

    def __process_structure(self, schema_root: MutableMapping[str, Any]):
        self.lookup_keys.extend(schema_root['lookup'])
        try:
            next_key = (schema_root.keys() - self.attribute_keys).pop()
            if next_key and schema_root[next_key]:
                self.file_schema.append(next_key)
            self.__process_structure(schema_root[next_key])
        except KeyError:
            return

    def compute_path(self, msg: Message):
        """
        Process and return Messages's schema location in the filesystem
        """
        return os.path.join(self.root, *[msg.__getattribute__(item) for item in self.file_schema], "aggregate.log")

    def file_check(self, file_name, *attrs: List):
        """
        Check if message is key based on file name as key
        """
        return file_name == self.key

    def attribute_check(self, *attrs: List):
        """
        Check if message is key based on attributes in message and schema
        """
        return self.key in attrs

    def key_check(self, file_name: str, info: Dict):
        """
        Check if message is key based on schema defined criteria
        """
        return self._key_check(file_name, info.keys())

    def log_glob_lookup(self, query):
        """
        On message search, return a glob for logs specified by query
        """
        log_glob_str = ""
        for attribute in self.lookup_keys:
            join_str = '*'
            if query.get(attribute):
                join_str = query.get(attribute)
            log_glob_str = os.path.join(log_glob_str, join_str)
        return os.path.join(log_glob_str,"aggregate.log")


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
        """
        Add message to queue.
        Thread safe
        """
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
    def __init__(self, name: str, file: TextIO, style: Callable):
        self.name = name
        self.file = file
        self.style = style
        self.fd = None
        self.__generate_metadata()

    def __generate_metadata(self):
        self.metadata = LogMetaData(self.__dict__)

    def load(self):
        """
        initial load of real log file
        """
        self.fd = open(self.file, 'r')
        if self.fd.seekable():
            self.fd.seek(whence=2)
        else:
            self.fd.read()

    def start_logging(self, monitor: threading.Condition, daemon: LoggerDaemon= None):
        """
        Start reading from designated log file, determining when a file has new info to be read, and
        processing new log entry into Message objects, to be sent to Audit Manager accesible endpoint
        """
        while():
            with monitor:
                if __loggers_stop:
                    return
            _message = self.fd.read()
            new_message = Message(_message, self.metadata)  \
                if _message else None
            # Assume logs are updated atomically
            if new_message:
                if daemon:
                    daemon.capture_message(new_message)


class AuditManager(object):
    """
    Reads from log aggregation endpoint, indexes and provides
    storage for the logs, as well as a runtime interface to query the logs.
    """
    def __init__(self, endpoint: LoggerDaemon, schema: Schema):
        self.__r_w_lock = threading.RLock()
        self.__p_thread = threading.Thread(target=self.__process_logs)
        self.endpoint = endpoint
        self.__p_stop = False
        self.tail = False
        self.local_store = {}
        self.schema = schema
        self.root = schema.root

    def __process_logs(self):
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
                    if self.schema.key_check(nxt_msg):
                        msg_pth = self.schema.compute_path(nxt_msg)
                        file_op = 'a'
                        if not os.path.isdir(msg_pth):
                            file_op = 'w+'

                        with open(msg_pth, file_op) as f:
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
                            elif type(self.local_store[nxt_msg.correlation_id][0]) == Message:
                                self.local_store[nxt_msg.correlation_id].append(nxt_msg)
                            else:
                                with open(self.local_store[nxt_msg.correlation_id], 'a') as f:
                                    f.write(nxt_msg)

    def start(self):
        """
        Begin the Audit Manager reading from the log endpoints
        """
        self.__p_thread.start()

    def stop(self):
        """
        Stop the Audit Manager from reading from the log endpoints
        """
        self.__p_stop = True
        self.__p_thread.join()

    def query(self, query: Query):
        """
        Process a user query from the command line.
        Return a list of log Messages, wrapped in QueryResponse
        objects for convenience
        """
        log_collection = []
        if query.get(self.schema.relator):
            log_files = [self.local_store[query.get(self.schema.relator)]]
        else:
            log_files = glob.glob(os.path.join(self.root, self.schema.lookup(query)))
        for file in log_files:
            json_log = json.load(file)
            for log_entry in json_log:
                log_collection.append(Message(json_log[log_entry]))
        return QueryResponse(log_collection)


def reset_sys_fd():
    """
    Close out system fd's after daemonizing
    """
    os.close(0)
    os.close(1)
    os.close(2)
    sys.stdin = sys.__stdin__ = open("/dev/null")
    sys.stdout = sys.__stdout__ = open("/dev/null", "w")
    sys.stderr = sys.__stderr__ = open("/dev/null", "w")

pid_root = os.path.join(os.environ.get("HOME"),
                                ".audit_logger")

pid_path = os.path.join(pid_root, "pidfile")


def write_pid_file():
    """
    Write Audit Logger PID file
    to assist in cleaning up
    and ensuring only one Audit Logger process is running
    at a time.
    """
    if is_already_active():
        with open(pid_path, 'r') as pidf:
            other_pid = pidf.read()
        raise AuditLoggerError("There is already a running instance of Audit Logger. Please kill this instance at %s before starting a new one." % other_pid)
    if not os.path.isdir(pid_root):
        os.makedirs(pid_root)
    with open(pid_path, 'w+') as f:
        f.write(str(os.getpid()))


def is_already_active():
    """
    Check to determine if there is already an active instance of Audit Logger running in the background
    """
    if os.path.isfile(pid_path):
        return True
    return False


def clean_pid_file():
    """
    Cleanup PID file after program is finished with execution.
    """
    try:
        os.remove(pid_path)

    except FileNotFoundError:
        return


def daemonize():
    """
    Daemonize the running process
    """
    pid = os.fork()
    if pid != 0:
        os._exit(pid > 0)

    reset_sys_fd()
    os.umask(0)
    os.setsid()


def client(*queries: List[Query]):
    """
    Establish a client connection to the Audit Logger,
    submit queries, then block on response.
    Returns list of QueryResponse objects
    """
    client = Client(('127.0.0.1', 6600), authkey=os.environ.get("AUDIT_LOGGER_AUTH",b'auditlogger'))
    rsp = []
    for query in queries:
        client.send(query)
        rsp.append(client.recv())
    client.close()
    return rsp


def start_logging(logs: List[Logger], schema: Schema, detached:bool= True):
    """
    Initite Logging process.
    If detached is true, process is daemonized.
    """
    if detached:
        daemonize()
        write_pid_file()

    def interrupt(notifier: threading.Condition):
        with notifier:
            __loggers_stop = True
            notifier.notify_all()
    try:
        listener = Listener(('127.0.0.1',6600), authkey=os.environ.get("AUDIT_LOGGER_AUTH",b'auditlogger'))
        notifier = threading.Condition(threading.Lock())
        logdaemon = LoggerDaemon(threading.RLock())
        am = AuditManager(logdaemon, schema)
        tp = []
        for log in logs:
            tp.append(threading.Thread(target=log.start_logging, args=[notifier, logdaemon]))
            tp[-1].start()
        am.start()
        while(True):
                with listener.accept() as conn:
                    query = conn.recv()
                    if query.STOP:
                        conn.send(0)
                        break
                    conn.send(am.query(query))
    finally:
        # effect graceful exit
        clean_pid_file()
        interrupt(notifier)
        am.stop()
        listener.close()
        for thread in tp:
            thread.join()
        exit(0)


def build_logs(conf: MutableMapping[str, Any]):
    """
    Constructs and returns log objects based on settings established in config
    file.
    """
    name = conf["log_name"]
    root = conf.get("root", os.path.join(os.environ.get("HOME"), ".logaudit", "store"))
    logs = conf.get("logs", None)
    if not logs:
        raise AuditLoggerError("ParseError: Logs attribute required, not found")
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
    schema_conf = conf.get("schema")
    if not schema_conf:
        raise AuditLoggerError("ParseError: Improperly formatted conf, a schema is required")
    schema = Schema(schema_conf, name, root)
    return full_logs, schema
