import re
from typing import Callable, Iterable

from fly.utils import logger

from fly.constant import VALID_ROUTE_METHOD, RouteType
from fly.exception import HTTP_404_NOT_FOUND, App_Init_Error, Uncaught_Exception


class URLPattern:
    def __init__(self, path: str, methods: list[str], route_func: Callable, route_type: str) -> None:
        # assert len(methods) == 1, 'URLPattern only support one method now'
        self._path = path
        self._func = route_func
        self._methods = [method.upper() for method in methods]
        self.route_type = route_type
        self.regex = self.get_path_regex()
        self.hash = hash(f"{self._path}-{self._methods}-{self.route_type}")

    def match(self, path: str, method: str, route_type: str) -> bool:
        assert not method or method.isupper()  # websockets has no method
        match = 0
        match_func = (self._match_normal, self._match_sse, self._match_websocket, self._match_static)
        for func in match_func:
            match = match + func(path, method, route_type)

        assert match <= 1

        logger.debug(f"match [{self._path}-{self.regex}-{self._methods}-{self.route_type}] with [{path} {method} {route_type}] -> {match}")
        return bool(match)

    def _match_normal(self, path: str, method: str, route_type: str) -> bool:
        return bool(re.match(self.regex, path)) and method in self._methods and self.route_type == RouteType.NORMAL

    def _match_sse(self, path: str, method: str, route_type: str) -> bool:
        return bool(re.match(self.regex, path)) and method in self._methods and self.route_type == RouteType.SSE

    def _match_websocket(self, path: str, method: str, route_type: str) -> bool:
        return bool(re.match(self.regex, path)) and method == "" and self.route_type == RouteType.WEBSOCKET

    def _match_static(self, path: str, method: str, route_type: str) -> bool:
        return bool(re.match(self.regex, path)) and method == "GET" and self.route_type == RouteType.STATIC

    @property
    def func(self):
        if hasattr(self._func, "_get_func"):
            return self._func._get_func()
        return self._func

    def get_path_regex(self) -> str:
        """
        "/user/<int:id>" -> "^/user/(?P<id>\d+)$"
        """
        route_type_mapping = {"int": r"\d+", "str": r"[^/]+", "path": r".+"}

        path = self._path
        if self.route_type == RouteType.STATIC:
            path = self._path.rstrip("/") + "/<path:static_file_path>"

        # path = path.replace("/", r"\/")

        def replace_pattern(match):
            route_type_ = match.group(1)
            name = match.group(2)
            regex_part = route_type_mapping.get(route_type_, r"[^/]+")  # 默认为 str 类型的正则
            return rf"(?P<{name}>{regex_part})"

        regex = re.sub(r"<(\w+):(\w+)>", replace_pattern, path)

        return f"^{regex}$"

    def __hash__(self) -> int:
        return self.hash

    def __eq__(self, o) -> bool:
        return self.hash == o.hash

    def __str__(self) -> str:
        return f"<URLPattern {self.route_type} {self._path} {self._methods}>"

    def get_path_params(self, path: str):
        match = re.match(self.regex, path)
        if match:
            return match.groupdict()
        raise RouteNotFoundException("URL does not match the pattern")


class Router:
    def __init__(self, _=None, prefix="") -> None:
        self.patterns: set[URLPattern] = set()
        self.cache: dict[str, URLPattern] = {}
        self.prefix = prefix
        self._sub_router = []

    def _add_route(self, path: str, methods: list[str], route_func: Callable, route_type: str) -> None:
        assert not methods or all(method.isupper() for method in methods)
        path = self.prefix + path
        if isinstance(methods, str):
            methods = [methods]
        if any(method not in VALID_ROUTE_METHOD for method in methods):
            raise RouteMethodUnsupportedError(f"Method '{methods}' (for route '{path}') is not supported")
        if not path.startswith("/"):
            raise RoutePrefixError(f"Route '{path}' must start with '/'")

        pattern = URLPattern(path, methods, route_func, route_type)
        if pattern in self.patterns:
            raise RouteDulplicateError(f"Method '{methods}' for route '{path}' already exists")
        self.patterns.add(pattern)

        # logger.debug(f"Route added: {pattern}")

    def _route(self, path: str, methods: list[str], route_type) -> Callable:
        def decorator(route_func: Callable) -> Callable:
            try:
                self._add_route(path, methods, route_func, route_type)
            except App_Init_Error as e:
                logger.error("Failed to add route: %s", e)
                raise e
            except Exception as e:
                logger.error("Failed to add route: %s", e)
                raise Uncaught_Exception(e) from e
            return route_func

        return decorator

    def route(self, path: str, methods: Iterable[str] = VALID_ROUTE_METHOD, route_type=RouteType.NORMAL) -> Callable:
        methods = [method.upper() for method in methods]
        return self._route(path, methods, route_type)

    def get(self, path: str, route_type=RouteType.NORMAL) -> Callable:
        return self._route(path, ["GET"], route_type)

    def post(self, path: str, route_type=RouteType.NORMAL) -> Callable:
        return self._route(path, ["POST"], route_type)

    def put(self, path: str, route_type=RouteType.NORMAL) -> Callable:
        return self._route(path, ["PUT"], route_type)

    def delete(self, path: str, route_type=RouteType.NORMAL) -> Callable:
        return self._route(path, ["DELETE"], route_type)

    def sse(self, path: str, methods: list[str]) -> Callable:
        return self._route(path, methods, RouteType.SSE)

    def websocket(self, path: str) -> Callable:
        return self._route(path, [], RouteType.WEBSOCKET)

    def static(self, path: str, root: str) -> None:
        return self._add_route(path, ["GET"], lambda: root, RouteType.STATIC)

    def add_route(self, path: str, methods: list[str], route_func: Callable, route_type: str) -> None:
        return self._add_route(path, methods, route_func, route_type)

    def kls_route(self, path: str, kls) -> None:
        methods = kls._route_dict.keys()
        return self._add_route(path, methods, kls, RouteType.NORMAL)

    def dispatch(self, path: str, method: str, route_type: str) -> URLPattern:
        method = method.upper()
        route_cache_key = f"{path}-{method}-{route_type}"
        pattern_func = self.cache.get(route_cache_key, None)
        if pattern_func is not None:
            return pattern_func
        matched_pattern = []
        for pattern in self.patterns:
            if pattern.match(path, method, route_type):
                self.cache[route_cache_key] = pattern
                matched_pattern.append(pattern)
        assert len(matched_pattern) <= 1
        if matched_pattern:
            return matched_pattern[0]
        raise RouteNotFoundException(f"Route '{path} [{method}] {route_type}' not found")

    def group(self, prefix: str) -> "Router":
        r = Router(self, self.prefix + prefix)
        self._sub_router.append(r)
        return r

    def _register_router(self, router: "Router"):
        # 一条条添加 避免冲突
        for pattern in router.patterns:
            if pattern in self.patterns:
                raise RouteDulplicateError(f"Route '{pattern._path}' already exists")
            self.patterns.add(pattern)

    def register_router(self, router: "Router"):
        self._register_router(router)
        for sub_router in router._sub_router:
            self.register_router(sub_router)


class RouteDulplicateError(App_Init_Error):
    pass


class RouteMethodUnsupportedError(App_Init_Error):
    pass


class RoutePrefixError(App_Init_Error):
    pass


class RouteNotFoundException(HTTP_404_NOT_FOUND):
    pass


class RouteFuncIllegalError(App_Init_Error):
    pass
