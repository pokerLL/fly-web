from collections import defaultdict

from fly.constant import BuiltinSignal


class HTTP_ERROR(Exception):
    status_code = 502


class HTTP_400_BAD_REQUEST(HTTP_ERROR):
    status_code = 400


class HTTP_401_UNAUTHORIZED(HTTP_ERROR):
    status_code = 401


# UNAUTHENTICATED class fellows HTTP_401_UNAUTHORIZED


class HTTP_403_FORBIDDEN(HTTP_ERROR):
    status_code = 403


class HTTP_404_NOT_FOUND(HTTP_ERROR):
    status_code = 404


class HTTP_500_INTERNAL_SERVER_ERROR(HTTP_ERROR):
    status_code = 500


class HTTP_502_BAD_GATEWAY(HTTP_ERROR):
    status_code = 502


"#########################################################"


class WebSocketError(Exception):
    pass


class WebSocketDisconnectedError(WebSocketError):
    pass


"#########################################################"


class App_Error(Exception):
    pass


class App_Init_Error(App_Error):
    pass


class App_Internal_Error(App_Error):
    pass


"#########################################################"


class Uncaught_Exception(Exception):
    pass


"#########################################################"


class ErrorHandler:
    def __init__(self, app):
        self._app = app
        self._signal = app._signal
        self.rigistry = defaultdict(set)
        self._init()

    def _init(self):
        self._signal.connect(BuiltinSignal.EXCEPTION, self._handle)

    def register_error_handler(self, exp, handler):
        self.rigistry[exp].add(handler)

    def _handle(self, exp, *args, **kwargs):
        exp_type = type(exp)
        if exp_type not in self.rigistry:
            # raise App_Internal_Error(f"ErrorHandler: {exp_type} not registered")
            return
        for handler in self.rigistry[exp_type]:
            handler(exp, *args, **kwargs)
