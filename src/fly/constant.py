from enum import Enum


class BuiltinSignal(Enum):
    APP_STARTUP = "app.startup"
    APP_SHUTDOWN = "app.shutdown"
    SERVER_STARTUP = "server.startup"
    SERVER_SHUTDOWN = "server.shutdown"
    REQUEST_BEFORE = "request.before"
    REQUEST_AFTER = "request.after"
    EXCEPTION = "exception"
    DEBUG_RELOAD = "debug.reload"
    DEBUG_LISTENER = "debug.listener"
    DEBUG_MODE = "debug.mode"


VALID_ROUTE_METHOD = ("GET", "POST", "DELETE", "PUT")


class RouteType:
    NORMAL = "HTTP"
    WEBSOCKET = "WebSocket"
    SSE = "SSE"
    STATIC = "STATIC"

    @classmethod
    def validate_type(cls, route_type):
        if route_type not in cls.__dict__.values():
            raise ValueError(f"Invalid route type: {route_type}")
        return route_type
