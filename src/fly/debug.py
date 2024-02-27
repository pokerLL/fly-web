import time

from pyinstrument import Profiler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from fly.constant import BuiltinSignal
from fly.middleware.core import BaseMiddleware
from fly.utils import logger

WATCHED_FILE_EXTEND = ("py",)
DEBOUNCE_TIME = 1.0  # 防抖时间


class _FileWatcherHandler(FileSystemEventHandler):
    def __init__(self, signal):
        self.signal = signal
        self.last_modified_time = {}  # 用于存储每个文件的最后修改时间

    def on_modified(self, event):
        if event.src_path.split(".")[-1] not in WATCHED_FILE_EXTEND:
            return

        current_time = time.time()
        last_modified = self.last_modified_time.get(event.src_path, 0)

        if current_time - last_modified > DEBOUNCE_TIME:
            self.signal.send_signal(BuiltinSignal.DEBUG_RELOAD)
            self.last_modified_time[event.src_path] = current_time

    def on_created(self, event):
        # 创建和删除事件不太可能需要防抖，所以保持原样
        if event.src_path.split(".")[-1] not in WATCHED_FILE_EXTEND:
            return
        self.signal.send_signal(BuiltinSignal.DEBUG_RELOAD)

    def on_deleted(self, event):
        if event.src_path.split(".")[-1] not in WATCHED_FILE_EXTEND:
            return
        self.signal.send_signal(BuiltinSignal.DEBUG_RELOAD)


class DebugFileWatcher:
    def __init__(self, path, signal):
        self.path = path
        self._signal = signal
        self._init()
        self.observer = None

    def _init(self):
        self._signal.connect(BuiltinSignal.SERVER_SHUTDOWN, self.stop)

    def start(self):
        self.event_handler = _FileWatcherHandler(self._signal)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.path, recursive=True)
        self.observer.start()

    def stop(self):
        if self.observer is not None:
            logger.info(f"{self} : file watcher stopping ...")
            self.observer.stop()
            # self.observer.join(timeout=10)


class DebugProfilerMiddleware(BaseMiddleware):
    async def process_request(self, request, response):
        self.p = Profiler()
        self.p.start()

    async def process_response(self, request, response):
        self.p.stop()
        output = self.p.output_text(unicode=True, color=True)
        logger.info(output)


class DebugManager:
    def __init__(self, app) -> None:
        self._app = app
        self._signal = app._signal
        self._init()

    def _init(self):
        self._signal.connect(BuiltinSignal.DEBUG_LISTENER, self._run_signal_debug_listener)
        self._signal.connect(BuiltinSignal.DEBUG_MODE, self._run_signal_debug_mode)

    def _run_signal_debug_listener(self):
        self.filewatcher = DebugFileWatcher(self._app.root_path, self._signal)
        self.filewatcher.start()

    def _run_signal_debug_mode(self):
        if self._app.debug:
            DebugProfilerMiddleware.register(self._app)
