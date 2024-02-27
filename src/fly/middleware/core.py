import contextvars

from fly.constant import BuiltinSignal
from fly.utils import is_sync_generator_function, is_async_generator_function, run_func
from fly.middleware.exception import MiddlewareInitialCheckFailedError, MiddlewareAlreadyRegisteredError


class MiddlewareManager:
    def __init__(self, app):
        self._app = app
        self._sginal = app._signal
        self.cls_middlewares = []
        self.yield_funcs = []
        self.process_request_funcs = []
        self.process_response_funcs = []
        self.local = contextvars.ContextVar("fly.middleware")
        self._init()

    def _init(self):
        self._sginal.connect(BuiltinSignal.SERVER_STARTUP, self._add_builtin_middlewares)
        self._sginal.connect(BuiltinSignal.REQUEST_BEFORE, self._init_before_request)
        self._sginal.connect(BuiltinSignal.REQUEST_AFTER, self._del_after_request)

    def _add_builtin_middlewares(self):
        from fly.middleware.builtin import FlyCorsMiddleware

        FlyCorsMiddleware.register(self._app)

    def _init_before_request(self, *args, **kwargs):
        """
        执行顺序:
        1. 装饰器注册的函数
        2. yield函数
        3. cls中间件
        """
        data = {"yield_funcs": [], "process_request_funcs": [], "process_response_funcs": [], "middleware": []}
        for func in self.process_request_funcs:
            data["process_request_funcs"].append(func)

        for func in self.process_response_funcs:
            data["process_response_funcs"].append(func)

        for yield_func in self.yield_funcs:
            func = yield_func()
            func.send(None)
            data["yield_funcs"].append(func)

        for middleware in self.cls_middlewares:
            data["middleware"].append(middleware())

        funcs = {
            "process_request_funcs": [*data["process_request_funcs"], *data["yield_funcs"], *[middleware.process_request for middleware in data["middleware"]]],
            "process_response_funcs": [*data["process_response_funcs"], *data["yield_funcs"], *[middleware.process_response for middleware in data["middleware"][::-1]]],
        }

        self.local.set(funcs)

    def _del_after_request(self, *args, **kwargs):
        self.local.set(None)

    def add_process_request_func(self, func):
        if func in self.process_request_funcs:
            raise MiddlewareAlreadyRegisteredError(f"Middleware-process_ {func} already registered")
        self.process_request_funcs.append(func)

    def add_process_response_func(self, func):
        if func in self.process_response_funcs:
            raise MiddlewareAlreadyRegisteredError(f"Middleware-process_response {func} already registered")
        self.process_response_funcs.append(func)

    before_request = add_process_request_func
    after_request = add_process_response_func

    def add_yield_middleware(self, func):
        if func in self.yield_funcs:
            raise MiddlewareAlreadyRegisteredError(f"Middleware-yield_func {func} already registered")

        if not is_sync_generator_function(func) and not is_async_generator_function(func):
            raise MiddlewareInitialCheckFailedError(f"Middleware-yield_func {func} must be a generator function")
        # logger.debug(f"Middleware add_yield_middleware {func}")
        self.yield_funcs.append(func)

    def add_kls_middleware(self, cls):
        if cls in self.cls_middlewares:
            raise MiddlewareAlreadyRegisteredError(f"Middleware-cls {cls} already registered")
        # logger.debug(f"Middleware add_kls_middleware {cls}")
        self.cls_middlewares.append(cls)

    def remove_cls_middleware(self, cls):
        # logger.debug(f"Middleware remove_cls_middleware {cls}")
        if cls in self.cls_middlewares:
            self.cls_middlewares.remove(cls)

    async def do_process_request(self, request, response):
        data = self.local.get()
        funcs = data.get("process_request_funcs", [])
        for func in funcs:
            resp = await run_func(func, request, response)
            if resp is not None:
                return resp

    async def do_process_response(self, request, response):
        data = self.local.get()
        funcs = data.get("process_response_funcs", [])

        for func in funcs:
            resp = await run_func(func, request, response)
            if resp is not None:
                return resp


class _MiddlewareMeta(type):
    def __new__(cls, name, bases, attrs):
        if all(item not in attrs for item in ("process_request", "process_response")):
            raise MiddlewareInitialCheckFailedError(f"Middleware {name} must have process_request or process_response method")
        middleware = super().__new__(cls, name, bases, attrs)
        return middleware


class BaseMiddleware(metaclass=_MiddlewareMeta):
    async def process_request(self, request, response):
        pass

    async def process_response(self, request, response):
        pass

    @classmethod
    def register_once(cls, middleware_manager, signal_manager):
        middleware_manager.add_kls_middleware(cls)

        def unregister():
            middleware_manager.remove_cls_middleware(cls)

        signal_manager.connect(BuiltinSignal.REQUEST_AFTER, unregister)

    @classmethod
    def register(cls, middleware_manager):
        middleware_manager.add_kls_middleware(cls)
