import multiprocessing
import os
import threading
from typing import Any


class FlyLogger:
    default_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name: <12}</cyan>:<cyan>{function: <12}</cyan>:<cyan>{line:<3}</cyan> | "
        "<red>PID:{process: >5}</red> | "
        "<blue>TID:{thread: >5}</blue> - "
        "<level>{message}</level>"
    )

    def __init__(self, *, log_dir="logs", config=None, basic_extra=None, logger=None):
        import loguru

        self.log_dir = log_dir
        self.config = self.default_config() if config is None else config
        self.basic_extra = {} if basic_extra is None else basic_extra
        self.logger = logger or loguru.logger
        self.handler_ids = {}
        self.initialize_logger()

    def default_config(self):
        """默认日志配置。"""
        return {
            "_default_file": {
                # "type": "file",
                "sink": os.path.join(self.log_dir, "all.log"),
                "rotation": "10 MB",
                "level": "INFO",
                "format": self.default_format,
            },
            "_default_warning_file": {
                # "type": "file",
                "sink": os.path.join(self.log_dir, "warning.log"),
                "rotation": "10 MB",
                "level": "WARNING",
                "format": self.default_format,
            },
            "_default_console": {
                # "type": "console",
                "sink": lambda msg: print(msg, end=""),  # noqa: T201
                "level": "DEBUG",
                "colorize": True,
                "format": self.default_format,
            },
        }

    def _get_current_pid_thread(self):
        """获取当前进程和线程的ID。"""
        return multiprocessing.current_process().ident, threading.current_thread().ident

    def _init_config(self, config, extra=None):
        extra = {} if extra is None else extra
        d = {"level": "INFO", "format": self.default_format}
        d.update(config)
        d.update(self.basic_extra)
        d.update(extra)
        return d

    def _add_handler(self, handler_name, handler_config):
        """添加日志处理器。"""
        config = self._init_config(handler_config)
        self.handler_ids[handler_name] = self.logger.add(**config)

    def initialize_logger(self):
        """初始化日志记录器。"""
        try:
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir)
            process, thread = self._get_current_pid_thread()
            self.logger.remove()
            self.logger = self.logger.bind(process=process, thread=thread)

            for handler_name, handler_config in self.config.items():
                self._add_handler(handler_name, handler_config)
        except OSError as e:
            raise Exception(f"Failed to initialize log directory '{self.log_dir}': {e}") from e

    def add_log_level(self, name, level_no):
        """动态添加日志级别。"""
        try:
            self.logger.level(name, no=level_no)
        except ValueError as e:
            raise ValueError(f"Failed to add log level '{name}': {e}") from e

    def set_handler_log_level(self, handler_name, level):
        """设置日志处理器的日志级别。"""
        try:
            handler_id = self.handler_ids.get(handler_name)
            if handler_id:
                self.logger.remove(handler_id)

            config = self._init_config(self.config[handler_name], {"level": level})
            self.handler_ids[handler_name] = self.logger.add(**config)
        except ValueError as e:
            raise ValueError(f"Failed to set handler '{handler_name}' log level: {e}") from e
        except KeyError as e:
            raise KeyError(f"Handler name '{handler_name}' not found: {e}") from e

    def set_console_handler_level(self, level):
        """设置控制台输出的日志级别。"""
        self.set_handler_log_level("_default_console", level)

    def banner(self, msg: str, *, level="INFO", extra=None, fill="-", length=56):
        """输出banner。"""
        if not msg:
            logger.log(level, fill * length)
            return
        level = level.upper()
        _extra = {} if extra is None else extra
        _length, _more = (length - len(msg) - 2) / 2, (length - len(msg) - 2) % 2
        # _msg = f'{fill*int(_length)} {msg} {fill*int(_length)}'
        _msg = f"{fill*int(_length)} {msg} {fill*int(_length)}{fill*int(_more)}"
        assert len(_msg) == length
        self.logger.log(level, _msg, **_extra)

    def __getattribute__(self, name: str) -> Any:
        """重写__getattribute__，使得logger的方法可以直接调用。"""
        logger_methods = {"debug", "info", "warning", "error", "critical", "exception", "log", "add", "remove", "bind"}
        if name in logger_methods:
            return getattr(self.logger, name)

        return super().__getattribute__(name)


logger = FlyLogger()
