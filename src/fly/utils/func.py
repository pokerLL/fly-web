import copy
import inspect
import asyncio
import socket
from fly.exception import App_Internal_Error


def is_sync_generator_function(obj):
    """
    def sync_gen():
        yield 1
        yield 2
    """
    return inspect.isgeneratorfunction(obj)


def is_async_generator_function(obj):
    """
    async def async_gen():
        yield 1
        yield 2
    """
    return inspect.isasyncgenfunction(obj)


def is_coroutine_function(obj):
    """
    async def coro():
        pass
    """
    return inspect.iscoroutinefunction(obj) and not inspect.isasyncgenfunction(obj)


def is_sync_function(obj):
    """
    def sync():
        pass
    """
    if inspect.ismethod(obj):
        obj = obj.__func__
    return inspect.isfunction(obj) and not inspect.iscoroutinefunction(obj) and not inspect.isgeneratorfunction(obj) and not inspect.isasyncgenfunction(obj)


def get_available_port():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("localhost", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def update_dict(origin_dict, *dicts):
    od = copy.deepcopy(origin_dict)
    for nd in dicts:
        for k, v in od.items():
            if k in nd:
                if isinstance(v, dict):
                    od[k] = update_dict(v, nd[k])
                else:
                    od[k] = nd[k]
    return od


def get_func_type(func):
    is_coro = is_coroutine_function(func), "coro"
    is_sync = is_sync_function(func), "sync"
    is_sync_gen = is_sync_generator_function(func), "sync_gen"
    is_async_gen = is_async_generator_function(func), "async_gen"

    _is = [is_coro, is_sync, is_sync_gen, is_async_gen]
    _type = [it[1] for it in _is if it[0]]

    if len(_type) != 1:
        raise App_Internal_Error(f"UnSupported View func type: {func.__module__}.{func.__name__} type: {_type}")

    return _type[0]


def run_sync_func(func, *args, **kwargs):
    _type = get_func_type(func)
    forbidden = ("coro", "async_gen")

    if _type in forbidden:
        raise App_Internal_Error(f"UnSupported View func type: {func.__module__}.{func.__name__} forbidden {forbidden}")

    if _type == "sync":
        return func(*args, **kwargs)
    elif _type == "sync_gen":
        return list(func(*args, **kwargs))


async def run_func(func, *args, **kwargs):
    _type = get_func_type(func)

    if _type == "coro":
        return await func(*args, **kwargs)
    elif _type == "async_gen":
        return [data async for data in func(*args, **kwargs)]
    elif _type == "sync":
        return func(*args, **kwargs)
    elif _type == "sync_gen":
        return list(func(*args, **kwargs))


async def run_in_threadpool(sync_funcs, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sync_funcs, *args, **kwargs)


def run_in_threadpool_wrapper(func):
    def wrapper(*args, **kwargs):
        return run_in_threadpool(func, *args, **kwargs)

    return wrapper
