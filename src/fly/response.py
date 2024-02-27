import json
import mimetypes
import os
from fly.exception import HTTP_404_NOT_FOUND


class Response:
    status_code = 200

    def __init__(self, status_code, content):
        self.status_code = status_code
        self.body = content.encode("utf-8") if isinstance(content, str) else content
        self.headers = {"content-type": "text/html", "content-length": len(self.body)}
        self.has_sent_header = False
        self.has_closed = False

    def set_header(self, key, value):
        self.headers[key.lower()] = value

    def set_body(self, body):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers["content-length"] = len(self.body)

    async def send_header(self, send):
        if self.has_sent_header:
            return
        self.has_sent_header = True
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [(str(key).lower().encode("utf-8"), str(value).encode("utf-8")) for key, value in self.headers.items()],
            }
        )

    async def __call__(self, send):
        if self.has_closed:
            return
        if not self.has_sent_header:
            await self.send_header(send)
        self.has_closed = True
        await send({"type": "http.response.body", "body": self.body})

    def dict(self):
        return {"status_code": self.status_code, "body": self.body, "headers": self.headers}

    def __repr__(self) -> str:
        return f"<Response status_code={self.status_code} " f"headers={self.headers} " f"body={self.body}>"

    __str__ = __repr__


class JsonResponse(Response):
    def __init__(self, resp_dict):
        if not isinstance(resp_dict, dict):
            raise TypeError("JsonRespons must init with a dict")
        self.body = json.dumps(resp_dict).encode("utf-8")
        super().__init__(self.status_code, self.body)
        self.headers.update({"Content-Type": "application/json", "Content-Length": len(self.body)})


class SSEResponse(Response):
    def __init__(self, send):
        self.body = ""
        super().__init__(self.status_code, self.body)
        self._send = send
        self.headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }

    async def send_header(self):
        if self.has_sent_header:
            return
        self.has_sent_header = True
        # logger.debug(f"send header: {self.headers}")
        await self._send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [(str(key).lower().encode("utf-8"), str(value).encode("utf-8")) for key, value in self.headers.items()],
            }
        )

    async def send(self, content):
        if not self.has_sent_header:
            await self.send_header()
        # 根据SSE标准 content前必须带data:
        # 此外还有event id 和 retry的可选字段
        formatted_content = f"data: {content}".encode("utf-8")
        await self._send({"type": "http.response.body", "body": formatted_content, "more_body": True})

    async def close(self):
        if self.has_sent_header and not self.has_closed:
            self.has_closed = True
            await self._send(
                {
                    "type": "http.response.body",
                    "body": b"",
                    "more_body": False,  # 关闭连接
                }
            )

    async def __call__(self, send):
        raise RuntimeError("SSEResponse can not be called directly, use send() instead")


class StreamingFileResponse(Response):
    def __init__(self, status_code, file_path):
        super().__init__(status_code, b"")
        self.file_path = file_path
        self._init_header()

    def _init_header(self):
        content_type, _ = mimetypes.guess_type(self.file_path)
        if content_type is None:
            content_type = "application/octet-stream"
        self.set_header("Content-Type", content_type)
        self.set_header("Content-Length", os.path.getsize(self.file_path))

    async def __call__(self, send):
        if self.has_closed:
            return

        if not self.has_sent_header:
            await self.send_header(send)

        try:
            with open(self.file_path, "rb") as file:
                chunk_size = 8192  # You can adjust the chunk size based on your requirements
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    await send({"type": "http.response.body", "body": chunk, "more_body": True})
        except FileNotFoundError as e:
            raise HTTP_404_NOT_FOUND(f"Static file not found: {self.file_path}") from e

        self.has_closed = True
        await send({"type": "http.response.body", "body": b"", "more_body": False})
