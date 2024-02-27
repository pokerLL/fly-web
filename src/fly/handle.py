import os
from abc import ABC, abstractmethod
from asyncio.coroutines import iscoroutine

from fly.constant import RouteType
from fly.context import crequest
from fly.exception import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR, App_Internal_Error, WebSocketDisconnectedError, WebSocketError
from fly.response import JsonResponse, SSEResponse, StreamingFileResponse
from fly.schema import process_request, process_response
from fly.utils import is_sync_generator_function, is_async_generator_function, logger, run_func


class BaseHandle(ABC):
    def __init__(self, app):
        self.app = app

    @abstractmethod
    def __call__(self):
        raise NotImplementedError


class AsgiHttpHandle(BaseHandle):
    async def __call__(self):
        # t0 = time.time()
        pattern = self.app._route.dispatch(crequest.path, crequest.method, route_type=RouteType.NORMAL)
        if pattern.route_type == RouteType.NORMAL:
            resp = await self.handle_http(pattern)
        elif pattern.route_type == RouteType.SSE:
            resp = await self.handle_sse(pattern)
        elif pattern.route_type == RouteType.STATIC:
            resp = await self.handle_static(pattern)
        else:
            raise HTTP_500_INTERNAL_SERVER_ERROR(f"Unsupported route type: {pattern.route_type}")
        # t1 = time.time()
        # logger.debug(f"Handle request: {crequest.method} {crequest.path} -> {resp}")
        # logger.debug(f"cost {(t1-t0)*1000:.2f}ms on handle request")
        return resp

    async def handle_http(self, pattern):
        pattern_func = pattern.func
        crequest.path_params = pattern.get_path_params(crequest.path)
        # t2 = time.time()
        func_args = await process_request(crequest, pattern_func)
        # t3 = time.time()

        func_res = await run_func(pattern_func, **func_args)

        # t4 = time.time()
        response = await process_response(func_res, pattern_func)
        # t5 = time.time()
        # logger.debug(f"cost {(t3-t2)*1000:.2f}ms on request schema validate")
        # logger.debug(f"cost {(t4-t3)*1000:.2f}ms on call handle view func")
        # logger.debug(f"cost {(t5-t4)*1000:.2f}ms on response schema validate")
        return response

    async def handle_sse(self, pattern):
        asgi_send = crequest._send
        sse_resp = SSEResponse(asgi_send)
        try:
            pattern_func = pattern.func
            crequest.path_params = pattern.get_path_params(crequest.path)
            func_args = await process_request(crequest, pattern_func)
            # logger.debug(f"func_args: {func_args}")

            await sse_resp.send_header()
            sse_func = pattern_func(**func_args)
            if is_sync_generator_function(pattern_func):
                for data in sse_func:
                    # logger.debug(f"sse_func data: {data}")
                    await sse_resp.send(data)
            elif is_async_generator_function(pattern_func):
                async for data in sse_func:
                    # logger.debug(f"sse_func data: {data}")
                    await sse_resp.send(data)
            else:
                raise App_Internal_Error(f"UnSupported View func type: {type(pattern_func)}")
        finally:
            await sse_resp.close()
        return sse_resp

    async def handle_static(self, pattern):
        pattern_func = pattern.func
        crequest.path_params = pattern.get_path_params(crequest.path)
        root = pattern_func()
        static_file_path = crequest.path_params["static_file_path"]
        fp = f"{root}/{static_file_path}"
        logger.debug(f"static:{fp}")
        if not os.path.exists(fp) and not os.path.isfile(fp):
            raise HTTP_404_NOT_FOUND(f"File not found: {fp}")

        response = StreamingFileResponse(200, fp)
        return response


class AsgiLifespanHandle(BaseHandle):
    async def __call__(self):
        self.receive = crequest._receive
        while True:
            message = await self.receive()
            # logger.debug(f"Lifespan message: {message}")
            if message["type"] == "lifespan.startup":
                try:
                    await self.send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    logger.error(f"Error during lifespan startup: {e}")
                    await self.send({"type": "lifespan.startup.failed", "message": str(e)})
            elif message["type"] == "lifespan.shutdown":
                try:
                    await self.send({"type": "lifespan.shutdown.complete"})
                except Exception as e:
                    logger.error(f"Error during lifespan shutdown: {e}")
                    await self.send({"type": "lifespan.shutdown.failed", "message": str(e)})
            else:
                logger.error(f'Unhandled Lifespane message type : {message["type"]}')


class WebSocket:
    def __init__(self, scope, receive, send):
        self._scope = scope
        self._receive = receive
        self._send = send
        self.has_closed = False
        self.has_accepted = False

    async def receive(self):
        try:
            while True:
                message = await self._receive()
                # logger.debug(f"Websocket received: {message}")
                if message["type"] == "websocket.receive":
                    msg = message["text"]
                    if msg == "EXIT":
                        raise WebSocketDisconnectedError(f"Websocket disconnect by client: {message}")
                    elif msg in ("PING", "ping"):
                        await self.send("PONG")
                        continue
                    return msg
                elif message["type"] == "websocket.disconnect":
                    raise WebSocketDisconnectedError(f"Websocket disconnect by client: {message}")
                elif message["type"] == "websocket.connect":
                    await self.send_accept()
                else:
                    raise WebSocketError(f"Unexpected WebSocket message type: {message['type']}")
        except WebSocketError as e:
            logger.error(f"Websocket error: {e}")
            await self.close()
            raise e

    async def send(self, message):
        await self._send({"type": "websocket.send", "text": message})

    async def close(self):
        if not self.has_closed:
            # logger.debug("ws close")
            import traceback

            traceback.print_stack()
            await self._send(
                {
                    "type": "websocket.close",
                }
            )
            self.has_closed = True

    async def send_accept(self):
        if not self.has_accepted:
            await self._send(
                {
                    "type": "websocket.accept",
                }
            )
        else:
            await self.send("hello world")


class AsgiWebsocketHandle(BaseHandle):
    async def __call__(self):
        self.scope = crequest._scope
        self.receive = crequest._receive
        self.send = crequest._send

        # logger.debug(f"Websocket scope: {self.scope} - asgi : {crequest.asgi}")

        ws = WebSocket(self.scope, self.receive, self.send)
        # await ws.handshake()
        # await ws.send('hello')
        logger.debug(f"Websocket connect: {crequest.path} - {crequest.method}")
        pattern = self.app._route.dispatch(crequest.path, crequest.method, route_type=RouteType.WEBSOCKET)
        pattern_func = pattern.func
        try:
            handle_res = pattern_func(ws)
            if iscoroutine(handle_res):
                await handle_res
        except Exception as e:
            raise e
        finally:
            await ws.close()

        ws_resp = JsonResponse({})
        ws_resp.has_sent_header = True
        return ws_resp
