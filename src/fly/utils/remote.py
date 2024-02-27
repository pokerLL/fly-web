import code
import sys
import threading
from io import StringIO
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer

from fly.constant import BuiltinSignal
from fly.utils.func import get_available_port
from fly.utils.logger import logger


class OutputHookContext:
    def __enter__(self):
        self.output = StringIO()

        self.sys_stdout = sys.stdout
        sys.stdout = self.output

        self.sys_stderr = sys.stderr
        sys.stderr = self.output

    def __exit__(self, *args, **kwargs):
        sys.stdout = self.sys_stdout
        sys.stderr = self.sys_stderr

    def get_output(self):
        return self.output.getvalue()


class CodeRunner:
    def __init__(self):
        self.interpreter = code.InteractiveInterpreter()
        self.lock = threading.RLock()
        self.output_hook = OutputHookContext()

        self.run("import __main__ as main")
        self.run("import sys")

    def run(self, code, filename="<input>", symbol="single"):
        with self.lock:
            with self.output_hook:
                more = self.interpreter.runsource(code, filename, symbol)
                output = self.output_hook.get_output()
                return more, output


class ConsoleServer:
    def __init__(self, addr="127.0.0.1", port=44444, code=""):
        self.addr = addr
        self.port = port
        self.code = code
        self._thread = None
        self._shutdown_requested = False

    def serve_forever(self):
        with SimpleXMLRPCServer((self.addr, self.port), logRequests=False) as server:
            self.server = server
            logger.info(f"Serving XML-RPC on {self.addr}:{self.port}...")
            server.register_introspection_functions()
            server.register_instance(CodeRunner())

            while not self._shutdown_requested:
                server.handle_request()

    def serve_in_new_thread(self, thread_name=None):
        self._thread = threading.Thread(target=self.serve_forever)
        self._thread.setName(thread_name or ConsoleServer.__name__)
        self._thread.setDaemon(True)
        self._thread.start()

    def shutdown(self):
        self._shutdown_requested = True


class ConsoleClient(code.InteractiveConsole):
    def __init__(self, addr="127.0.0.1", port=44444):
        super().__init__()

        self.addr = addr
        self.port = port

        self.uri = "http://{addr}:{port}/".format(
            addr=self.addr,
            port=self.port,
        )
        self.proxy = ServerProxy(self.uri)

    def runsource(self, source, filename="<stdin>", symbol="single"):
        more, output = self.proxy.run(source, filename, symbol)
        if output:
            self.write(output)

        return more


def run_console_server(addr="0.0.0.0", port=44444, code="", thread_name=ConsoleServer.__name__, startup=True):
    server = ConsoleServer(addr=addr, port=port, code=code)
    if startup:
        server.serve_in_new_thread(thread_name=thread_name)
    return server


def run_console_client(addr="127.0.0.1", port=44444):
    client = ConsoleClient(addr=addr, port=port)
    client.interact()


def close_console_server(server):
    server.shutdown()


class RemoteConsoleManager:
    def __init__(self, app=None, addr="0.0.0.0", port=None, code=""):
        self.addr = addr
        self.port = port if port is not None else get_available_port()
        self.code = code
        self.server = None
        if app is not None:
            self._app = app
            self._signal = app._signal
            self._init()

    def _init(self):
        self._signal.connect(BuiltinSignal.SERVER_STARTUP, self.run_server)
        self._signal.connect(BuiltinSignal.SERVER_SHUTDOWN, self.stop_server)

    def run_server(self):
        self.server = run_console_server(addr=self.addr, port=self.port, code=self.code)

    def stop_server(self):
        if self.server is not None:
            logger.info(f"{self} : console server stopping...")
            close_console_server(self.server)

    def run_client(self):
        self.client = run_console_client(addr=self.addr, port=self.port)
