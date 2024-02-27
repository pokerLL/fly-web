import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

import __main__

from fly.command import CommandManager
from fly.config import FlyConfig
from fly.constant import BuiltinSignal, RouteType
from fly.context import mk_app_context, mk_request_context
from fly.debug import DebugManager, DebugProfilerMiddleware
from fly.exception import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_ERROR, App_Error, App_Internal_Error, ErrorHandler, Uncaught_Exception
from fly.handle import AsgiHttpHandle, AsgiLifespanHandle, AsgiWebsocketHandle
from fly.middleware import MiddlewareManager
from fly.openapi import FlyOpenAPIManager
from fly.request import Request
from fly.response import JsonResponse, Response
from fly.route import Router
from fly.signal import SignalManager
from fly.utils import RemoteConsoleManager, logger, get_host_ip
from fly.signal.builtin import OnStatus


class Fly:
    ROUTE_METHODS = ("route", "get", "post", "put", "delete", "sse", "websocket", "static", "kls_route", "register_router")
    MIDDLEWARE_METHODS = ("before_request", "after_request", "add_kls_middleware", "add_yield_middleware")
    SIGNAL_METHODS = ("register_signal", "send_signal", "connect")
    COMMAND_METHODS = ("manage", "register_command", "execute")
    TASK_METHODS = ("add_delay_task", "add_interval_task", "add_cron_task", "add_background_task", "add_task")
    ONSTATUS_METHODS = ("on_status",)
    # 确保没有重复的方法名
    assert set(ROUTE_METHODS) & set(MIDDLEWARE_METHODS) & set(SIGNAL_METHODS) & set(COMMAND_METHODS) & set(TASK_METHODS) & set(ONSTATUS_METHODS) == set()

    assert set(ROUTE_METHODS) & set(MIDDLEWARE_METHODS) & set(SIGNAL_METHODS) & set(COMMAND_METHODS) == set()

    def __init__(self, name_or_dict: dict | str):
        logger.banner("App Initializing")
        if isinstance(name_or_dict, dict):
            self.config = FlyConfig(name_or_dict)
            self.name = self.config.get("name", "fly")
        else:
            self.config = FlyConfig({})
            self.name = name_or_dict
        # self.root_path = os.path.abspath(os.path.dirname(__main__.__file__))
        self.root_path = Path(__file__).parent.parent.parent.absolute()
        self._signal: SignalManager = SignalManager(self)
        self._route: Router = Router(self)
        self._middleware: MiddlewareManager = MiddlewareManager(self)
        self._command: CommandManager = CommandManager(self)
        self._debug: DebugManager = DebugManager(self)
        self._console: RemoteConsoleManager = RemoteConsoleManager(self)
        self._error: ErrorHandler = ErrorHandler(self)
        self._openapi: FlyOpenAPIManager = FlyOpenAPIManager(self)
        self._init()

    def _init(self):
        self._signal.connect(BuiltinSignal.APP_SHUTDOWN, self.stop)

    def __getattr__(self, attr):
        # 当访问当前实例不存在的属性时会调用__getattr__
        # 核心思想: app作绝对大部分操作的入口
        if attr in self.ROUTE_METHODS:
            return getattr(self._route, attr)
        elif attr in self.MIDDLEWARE_METHODS:
            return getattr(self._middleware, attr)
        elif attr in self.SIGNAL_METHODS:
            return getattr(self._signal, attr)
        elif attr in self.COMMAND_METHODS:
            return getattr(self._command, attr)
        elif attr in self.TASK_METHODS:
            return getattr(self._task, attr)
        elif attr in self.ONSTATUS_METHODS:
            return getattr(OnStatus, attr)

        return super().__getattr__(attr)

    def _run_server(self):
        # 运行服务器的逻辑
        self.app_ctx = mk_app_context(self)
        self.app_ctx.push()

        # self._run_server_hypercorn()
        # self._run_server_daphne()
        self._run_server_uvicorn()

    def _run_server_daphne(self):
        from daphne.server import Server

        logger.info(f'Running {"Server":6} in process:{multiprocessing.current_process().ident} - thread:{threading.current_thread().ident}')
        logger.info(f"-> on http://{self.host}:{self.port}")
        endpoint_str = f"tcp:port={self.port}:interface={self.host}"
        logger.banner("")

        self._signal.send_signal(BuiltinSignal.SERVER_STARTUP)

        try:
            self.server = Server(application=self, endpoints=[endpoint_str])

            def stop_server(self):
                self.server.stop()

            self.stop_server = stop_server
            self.server.run()
        except Exception as e:
            raise e
        finally:
            self._signal.send_signal(BuiltinSignal.SERVER_SHUTDOWN)

    def _run_server_hypercorn(self):
        import asyncio

        from hypercorn.asyncio import serve
        from hypercorn.config import Config

        logger.info(f"Running Server in process:{multiprocessing.current_process().ident} - thread:{threading.current_thread().ident}")
        logger.info(f"-> on http://{self.host}:{self.port}")
        logger.banner("")
        self._signal.send_signal(BuiltinSignal.SERVER_STARTUP)

        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        config.loglevel = "info"

        def stop_server(self):
            # loop = asyncio.get_event_loop()
            # loop.stop()
            # loop.close()
            self._signal.send_signal(BuiltinSignal.SERVER_SHUTDOWN)

        self.stop_server = stop_server

        asyncio.run(serve(self, config))

    def _run_server_uvicorn(self):
        import uvicorn

        logger.info(f"Running Server in process:{multiprocessing.current_process().ident} - thread:{threading.current_thread().ident}")
        logger.info(f"-> on http://{self.host}:{self.port}")
        logger.banner("")
        self._signal.send_signal(BuiltinSignal.SERVER_STARTUP)
        log_level = "debug" if self.debug else "info"

        config = uvicorn.Config(app=self, host=self.host, port=self.port, log_level=log_level)

        def stop_server(self):
            # Note: Uvicorn does not provide a direct way to programmatically stop the server from within.
            # Stopping the Uvicorn server usually involves stopping the event loop.
            # This method might need to be adapted based on how you handle your event loop.
            # self.server.stop()
            pass

        self.stop_server = stop_server

        server = uvicorn.Server(config)
        self.server = server
        server.run()

    def _run_debug_listener(self):
        if not self.is_debug_listener:
            return

        self._signal.send_signal(BuiltinSignal.DEBUG_LISTENER)
        self._signal.connect(BuiltinSignal.DEBUG_RELOAD, self._reload)

        self._full_command = self._get_full_command()
        self._sub_env = os.environ.copy()
        self._sub_env.update({"FLY_DEBUG_WORKER": "1"})
        self._server_process = subprocess.Popen(self._full_command, env=self._sub_env)
        while True:
            pass

    def run(self, host="0.0.0.0", port=5000, debug=False):
        try:
            self.host = self.config["host"] = host
            self.port = self.config["port"] = port
            self.debug = self.config["debug"] = debug
            self.host_ip = self.config["host_ip"] = get_host_ip()
            self.is_debug_listener = debug and os.environ.get("FLY_DEBUG_WORKER") is None
            if os.environ.get("FLY_DEBUG_WORKER") is not None and not self.debug:
                raise App_Internal_Error("Please do not set FLY_DEBUG_WORKER env in production mode.")
            if not self.debug:
                logger.set_console_handler_level("INFO")
            else:
                self._signal.send_signal(BuiltinSignal.DEBUG_MODE)

            self._signal.send_signal(BuiltinSignal.APP_STARTUP)

            logger.banner("Running Fly Server")
            logger.info(f'Running {"App":6} in process:{multiprocessing.current_process().ident} - thread:{threading.current_thread().ident}')
            logger.info(f"-> name: {self.name}")
            logger.info(f"-> debug: {self.debug}")
            logger.info(f"-> is_debug_listener: {self.is_debug_listener}")
            logger.info(f"-> root_path: {self.root_path}")

            if self.is_debug_listener:
                self._run_debug_listener()
            else:
                self._run_server()
        except App_Error as e:
            logger.error(f"Got an App_Error:\n{e}")
            traceback.print_exc()
        except Exception as e:
            logger.error(f"Got an Uncatched Exception:\n{e}")
            traceback.print_exc()
            raise Uncaught_Exception(e) from e
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt")

    def _get_full_command(self):
        entry_executable = sys.executable
        entry_file_path = os.path.abspath(__main__.__file__)
        entry_args = sys.argv[1:]
        full_command = [entry_executable, entry_file_path] + entry_args
        return full_command

    def _reload(self):
        if not self.is_debug_listener:
            return
        # logger.debug(f"Running in {multiprocessing.current_process().ident}-{threading.current_thread().ident}")
        logger.info("Reloading the application...")
        if self._server_process:
            self._server_process.terminate()
            self._server_process.wait()
        self._server_process = subprocess.Popen(self._full_command, env=self._sub_env)
        logger.info("Application reloaded successfully.")
        os.system("clear" if os.name == "posix" else "cls")

    def manage(self):
        self._command.execute()

    def stop(self):
        if self.is_debug_listener:
            self._server_process.terminate()
        else:
            self.app_ctx.pop()
            self.stop_server(self)
        logger.info(f'{"-"*20} {"Server Stopped":^20} {"-"*20}')
        exit(1)

    async def __call__(self, scope, receive, send):
        t0 = time.time()

        logger.banner(f"New Request - {scope.get('method', '').upper()} - {scope.get('path')}", level="INFO")

        if "profile" in scope["query_string"].decode() and scope["type"] == RouteType.NORMAL:
            DebugProfilerMiddleware.register_once(self._middleware, self._signal)

        request = Request(scope, receive, send)
        request_cxt = mk_request_context(request)
        request_cxt.push()

        self._signal.send_signal(BuiltinSignal.REQUEST_BEFORE)

        # logger.debug(f"type: {scope['type']}")

        if scope["type"] == "http":
            handle = AsgiHttpHandle(self)
        elif scope["type"] == "websocket":
            handle = AsgiWebsocketHandle(self)
        elif scope["type"] == "lifespan":
            handle = AsgiLifespanHandle(self)
        else:
            raise App_Internal_Error(f"Unknown scope type: {scope['type']}")

        try:
            response = await self._middleware.do_process_request(request, None)
        except Exception as e:
            logger.error(f"Got an Uncatched Exception:\n{e}")
            logger.error(traceback.format_exc())
            raise Uncaught_Exception(e) from e

        t1 = time.time()
        if not isinstance(response, Response):
            try:
                response = await handle()
            except HTTP_ERROR as e:
                response = Response(e.status_code, str(e))
                traceback.print_exc()
                self._signal.send_signal(BuiltinSignal.EXCEPTION, e)
            except App_Error as e:
                response = Response(HTTP_500_INTERNAL_SERVER_ERROR.status_code, str(e))
                traceback.print_exc()
            except Exception as e:
                logger.error(f"Got an Uncatched Exception:\n{e}")
                traceback.print_exc()
                raise Uncaught_Exception(e) from e

        if not isinstance(response, Response) and not isinstance(response, dict):
            raise TypeError(f"Response must be a dict or Response, not {type(response)}")

        t2 = time.time()
        try:
            await self._middleware.do_process_response(request, response)
        except Exception as e:
            logger.error(f"Got an Uncatched Exception:\n{e}")
            logger.error(traceback.format_exc())
            raise Uncaught_Exception(e) from e

        if isinstance(response, dict):
            response = JsonResponse(response)

        self._signal.send_signal(BuiltinSignal.REQUEST_AFTER, request, response)

        if not response.has_closed:
            await response(send)

        t3 = time.time()
        du = (t3 - t0) * 1000
        du1 = (t1 - t0) * 1000
        du2 = (t2 - t1) * 1000
        du3 = (t3 - t2) * 1000
        if du > 1000 and scope["type"] == RouteType.NORMAL:
            logger.warning(f"Slow request: {request.type} {request.method} {request.path} -> {response.status_code} {du:.2f}ms")
            logger.warning(f"-> cost time: {du:.2f}ms(100%) = {du1:.2f}ms({du1/du*100:.2f}%) + {du2:.2f}ms({du2/du*100:.2f}%) + {du3:.2f}ms({du3/du*100:.2f}%)")
            logger.warning(f"-> request: {request.dict()}")
            logger.warning(f"-> response: {response.dict()}")
        else:
            logger.info(f"Request:  {request.type} {request.method} {request.path} -> {response.status_code} {du:.2f}ms")
            logger.info(f"-> cost time: {du:.2f}ms(100%) = {du1:.2f}ms({du1/du*100:.2f}%) + {du2:.2f}ms({du2/du*100:.2f}%) + {du3:.2f}ms({du3/du*100:.2f}%)")

        logger.banner("END OF Request")
        del request
        del response
        request_cxt.pop()
