import contextvars
import operator
from functools import partial
from typing import Any, List

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from fly.fly import Fly

    from fly.request import Request


class Context:
    def __init__(self, ctx_var: contextvars.ContextVar, var: Any) -> None:
        self._var = var
        self._ctx_var = ctx_var
        self._cv_tokens: List[contextvars.Token] = []

    def push(self) -> None:
        self._cv_tokens.append(self._ctx_var.set(self._var))

    def pop(self) -> None:
        if len(self._cv_tokens) == 1:
            token = self._cv_tokens.pop()
            self._ctx_var.reset(token)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._var} {self._cv_tokens}>"


class ApplicationContext(Context):
    def __init__(self, app):
        self._app = app
        super().__init__(ctx_var=_current_app_ctx, var=self._app)


class RequestContext(Context):
    def __init__(self, request):
        self._request = request
        super().__init__(ctx_var=_current_request_ctx, var=self._request)


def mk_request_context(request):
    return RequestContext(request)


def mk_app_context(app):
    return ApplicationContext(app)


_current_request_ctx = contextvars.ContextVar("fly.request")
_current_app_ctx = contextvars.ContextVar("fly.app")


class _ProxyLookup:
    def __init__(self, func):
        def bind_f(instance, obj):
            return partial(func, obj)

        self.bind_f = bind_f

    def __get__(self, instance, owner: type | None = None):
        obj = instance._get_current_object()
        return self.bind_f(instance, obj)

    def __call__(self, instance, *args, **kwargs):
        return self.__get__(instance, type(instance))(*args, **kwargs)


class LocalProxy:
    def __init__(self, local, proxy_type):
        self.local = local
        self.proxy_type = proxy_type

    def _get_current_object(self):
        if isinstance(self.local, contextvars.ContextVar):
            obj = self.local.get()
            if obj is None:
                raise RuntimeError(f"Context {self.local.context} is missing")
            return obj
        raise RuntimeError(f"Unsupported local type:{type(self.local)}")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.proxy_type}>"

    __getattr__ = _ProxyLookup(getattr)  # 等价于 __getattr__(self, name) -> getattr(self._get_current_object(), name)
    __getitem__ = _ProxyLookup(operator.__getitem__)  # 等价于 __getitem__(self, name) -> operator.__getitem__(self._get_current_object(), name)


crequest: "Request" = LocalProxy(_current_request_ctx, "Request")
capp: "Fly" = LocalProxy(_current_app_ctx, "Fly")
