from typing import Any

from fly.constant import VALID_ROUTE_METHOD
from fly.context import crequest
from fly.exception import App_Internal_Error


class View:
    @classmethod
    def as_view(cls, route_dict=None):
        if route_dict is None:
            route_dict = {k: getattr(cls, k.lower()) for k in VALID_ROUTE_METHOD if hasattr(cls, k.lower())}
        cls._route_dict = route_dict
        return cls

    @classmethod
    def _get_func(cls):
        func = cls._route_dict[crequest.method]
        # logger.debug(f"_get_func: {method} {cls.route_dict} -> {func}")
        ins = cls()
        func = getattr(ins, func.__name__)
        return func

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        raise App_Internal_Error("View class should not be called directly")
