from enum import Enum
from fly.constant import BuiltinSignal
from fly.utils import logger, run_sync_func

from fly.signal.exception import SignaleNotFoundError
from fly.signal.builtin import OnStatus


class SignalManager:
    def __init__(self, app):
        self.signals = {}
        self._last_send_signal = {}
        self._init_builtin_signal()

    def _init_builtin_signal(self):
        for signal in BuiltinSignal:
            self.signals[signal.value] = set()

    def register_signal(self, signal):
        # signal = signal.value if signal in BuiltinSignal else signal
        if signal not in self.signals:
            logger.info(f"new signal {signal}")
            self.signals[signal] = set()

        OnStatus.register(self)

    def connect(self, signal, func):
        signal = signal.value if isinstance(signal, Enum) else signal
        if signal not in self.signals:
            logger.info(f"new signal {signal}")
            self.signals[signal] = set()
        self.signals[signal].add(func)

    def send_signal(self, signal, *args, **kwargs):
        """
        目前不支持异步信号
        """
        signal = signal.value if isinstance(signal, Enum) else signal
        if signal not in self.signals:
            raise SignaleNotFoundError
        # logger.warning(f"send signal {signal} with args: {args} and kwargs: {kwargs} -> func: {self.signals[signal]}")
        for func in self.signals[signal]:
            try:
                run_sync_func(func, *args, **kwargs)
                logger.debug(f"{signal} func called succeed")
            except Exception as e:
                logger.error(f"{signal} func {func} failed for reason: {e}")

    def disconnect(self, signal, func):
        signal = signal.value if isinstance(signal, Enum) else signal
        if signal not in self.signals:
            raise SignaleNotFoundError
        self.signals[signal].remove(func)
