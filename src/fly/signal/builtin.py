from fly.constant import BuiltinSignal


class OnStatus:
    _status_handler = {}

    @classmethod
    def on_status(cls, status_code) -> None:
        def wrapper(func):
            cls._add_status_handler(status_code, func)
            return func

        return wrapper

    @classmethod
    def _add_status_handler(cls, status_code, func):
        if status_code not in cls._status_handler:
            cls._status_handler[status_code] = []
        if func not in cls._status_handler[status_code]:
            cls._status_handler[status_code].append(func)

    @classmethod
    def handle(cls, request, response):
        status_code = response.status_code
        if status_code in cls._status_handler:
            for func in cls._status_handler[status_code]:
                func(request, response)

    @classmethod
    def register(cls, signal_manager):
        signal_manager.connect(BuiltinSignal.REQUEST_AFTER, cls.handle)
