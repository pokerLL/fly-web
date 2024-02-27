import asyncio
from functools import partial
import json as _json
from contextlib import asynccontextmanager
from fly.utils import logger
from fly.exception import App_Internal_Error


class TestClientResponse:
    def __init__(self, status, headers, body, messages):
        self.status_code = status
        self.headers = headers
        self.body = body
        self.messages = self.process_messages(messages)  # 最后一条消息是用来关闭连接的空消息

    @property
    def dict(self):
        try:
            _dict = _json.loads(self.body.decode())
            return _dict
        except Exception as e:
            logger.error(f"Reponse body cannot be loaded as a dict - body:{self.body} for reason : {e}")
            pass

    def process_messages(self, messages):
        messages = messages[:-1] if messages and messages[-1] == b"" else messages
        return messages


class WebSocketTestSession:
    def __init__(self, app, path):
        self.app = app
        self.path = path
        self.scope = {
            "type": "websocket",
            "path": self.path,
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 80),
            "subprotocols": [],
            "asgi": {"version": "3.0"},
        }
        self.send_queue = asyncio.Queue()
        self.receive_queue = asyncio.Queue()

    async def connect(self):
        # 在另一个线程中运行app接受ws请求 - 避免阻塞
        asyncio.create_task(self.app(self.scope, self.server_receive, self.server_send))
        await self.send_queue.put({"type": "websocket.connect"})
        assert await self.receive_queue.get() == {"type": "websocket.accept"}

    async def disconnect(self):
        await self.send_queue.put({"type": "websocket.disconnect"})

    async def send(self, message):
        message = {"type": "websocket.receive", "text": message}
        await self.send_queue.put(message)

    async def receive(self):
        messgae = await self.receive_queue.get()
        messgae = messgae["text"]
        return messgae

    async def server_receive(self):
        return await self.send_queue.get()

    async def server_send(self, message):
        await self.receive_queue.put(message)


class TestClient:
    def __init__(self, app):
        self.app = app

    def parse_query_string(self, path):
        parts = path.split("?", 1)
        return parts[1].encode("utf-8") if len(parts) > 1 else b""

    async def simulate_http_request(self, method: str, path: str, headers: dict, body: bytes, is_sse: bool = False):
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path.split("?")[0],
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
            "server": ("testserver", 80),
            "client": ("testclient", 80),
            "query_string": self.parse_query_string(path),
            "body": body or b"",
            "asgi": {"version": "3.0"},
        }

        response: dict = {"status": None, "headers": [], "body": b"", "messages": []}

        async def receive():
            return {"type": "http.request", "body": scope["body"], "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                response["status"] = message["status"]
                response["headers"] = [(k.decode(), v.decode()) for k, v in message["headers"]]
            elif message["type"] == "http.response.body":
                if is_sse:
                    response["messages"].append(message["body"])
                else:
                    response["body"] += message["body"]
            else:
                raise TestClientInteralError(f"Not handled asgi reponse message type : {message['type']}")

        await self.app(scope, receive, send)

        return TestClientResponse(**response)

    def handle_request(sellf, headers=None, body=None, json=None):
        headers = headers or {}
        if json is not None:
            body = _json.dumps(json)
            headers["content-type"] = "application/json"
        if body:
            headers["content-length"] = str(len(body))
            body = body.encode("utf-8")

        return headers, body

    def request(self, method, path, headers=None, body=None, json=None, is_sse: bool = False):
        headers, body = self.handle_request(headers, body, json)
        if not is_sse:
            loop = asyncio.get_event_loop()
            resp = loop.run_until_complete(self.simulate_http_request(method, path, headers, body, is_sse=False))
        else:
            resp = self.simulate_http_request(method, path, headers, body, is_sse=True)
        return resp

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)

    @asynccontextmanager
    async def ws(self, path):
        session = WebSocketTestSession(self.app, path)
        try:
            await session.connect()
            yield session
        finally:
            await session.disconnect()


def get_test_client(app):
    return TestClient(app)


class TestClientInteralError(App_Internal_Error):
    pass
