import cgi
import json
import os
import shutil
import tempfile
import uuid
from io import BytesIO

from fly.exception import HTTP_400_BAD_REQUEST


class Request:
    def __init__(self, scope, receive, send):
        self.uuid = uuid.uuid4().hex
        self._scope = scope
        self._receive = receive
        self._send = send
        self.type = scope["type"].upper()
        self.http_version = scope.get("http_version")
        self.method = scope.get("method", "").upper()
        self.path = scope["path"]
        self.header = self.parse_header(scope["headers"])
        self.client = scope["client"]
        self.server = scope["server"]
        self.query_params = self.parse_qs(scope["query_string"].decode("utf-8"))
        self.path_params = {}
        self.asgi = scope["asgi"]
        self._content_type = self.header.get("content-type", "")
        self._content_length = self.header.get("content-length", 0)
        self.body = RequestBody(self._content_type, self._content_length, receive)
        self.cookie = self.parse_cookie(self.header.get("cookie"))

    @staticmethod
    def parse_qs(query_string: str):
        if not query_string:
            return {}
        items = query_string.split("&")
        params = {}
        for item in items:
            if "=" in item:
                params[item.split("=")[0]] = item.split("=")[1]
            else:
                params[item] = ""
        return params

    @staticmethod
    def parse_cookie(_cookie: str):
        # logger.debug(f"parse cookie: {_cookie}")
        if not _cookie:
            return {}
        cookies: dict[str, str] = {}
        items = _cookie.split(";")
        for item in items:
            k, v = item, ""
            if "=" in item:
                k, v = item.split("=", 1)
            k, v = k.strip(), v.strip()
            if k in cookies:
                cookies[k] += f";{v}"
            else:
                cookies[k] = v
        return cookies

    @staticmethod
    def parse_header(header: list[tuple]):
        header_dict: dict[str, str] = {}
        for k, v in header:
            k, v = k.decode("utf-8").lower(), v.decode("utf-8")
            if k in header_dict:
                header_dict[k] += f";{v}"
            else:
                header_dict[k] = v
        return header_dict

    def __repr__(self) -> str:
        return f"<Request {self.method} {self.path}>\n" f"- headers: {self.header}\n" f"- query_params: {self.query_params}\n"

    def __del__(self):
        del self.body

    def dict(self):
        return {
            "type": self.type,
            "http_version": self.http_version,
            "method": self.method,
            "path": self.path,
            "headers": self.header,
            "client": self.client,
            "server": self.server,
            "query_params": self.query_params,
            "path_params": self.path_params,
            "asgi": self.asgi,
            "cookie": self.cookie,
            # 'body': self.body,
        }


class RequestBody:
    def __init__(self, content_type, content_length, receive):
        self.content_type = content_type
        self.content_length = content_length
        self.receive = receive
        if "multipart/form-data" in self.content_type:
            self._content_type, self.boumdary = self.content_type, self.content_type.split("boundary=")[-1]
            self.content_type = "multipart/form-data"
        self.__body = None
        self._tempfiles = []

    @property
    async def body(self):
        if self.__body is not None:
            return self.__body
        # t0 = time.time()
        self.__body, more_body = b"", True
        tp_bodys = []
        while more_body:
            _body = await self.receive()
            more_body = _body.get("more_body", b"")
            tp_bodys.append(_body)  # warning: 可以尝试一下这里用self.__body += _body['body']，会发现性能差距巨大
        # t1 = time.time()
        # logger.debug(f"-> cost {(t1-t0)*1000:.2f}ms on parse request.body")
        self.__body = b"".join([body.get("body", b"") for body in tp_bodys])
        return self.__body

    async def dict(self):
        resp_dict = {}
        if self.content_type == "application/json":
            resp_dict = await self.parse_json()
        elif self.content_type == "multipart/form-data":
            resp_dict = await self.parse_form()
        else:
            raise Unsupported_Content_Type(f"Can not parse Content-Type: {self.content_type} to dict")
        return resp_dict

    async def parse_json(self):
        body_bytes = await self.body
        resp_dict = json.loads(body_bytes.decode())
        return resp_dict

    async def parse_form(self):
        body_bytes = await self.body
        headers = {"content-type": self._content_type}
        environ = {"REQUEST_METHOD": "POST"}
        form = cgi.FieldStorage(fp=BytesIO(body_bytes), headers=headers, environ=environ)
        fields = {}
        for field in form.keys():
            field_data = form[field]
            if field_data.filename:
                temp_file = await self.write_to_tempfile(field_data.file)
                fields[field] = {"filename": field_data.filename, "content_type": field_data.type, "tempfile": temp_file}
            else:
                fields[field] = field_data.value
        return fields

    async def json(self):
        return json.dumps(await self.dict())

    async def write_to_tempfile(self, file_data):
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        with temp_file as f:
            shutil.copyfileobj(file_data, f)
        self._tempfiles.append(temp_file)
        return temp_file.name

    def __del__(self):
        for temp_file in self._tempfiles:
            os.remove(temp_file.name)
        self._tempfiles = []


class Unsupported_Content_Type(HTTP_400_BAD_REQUEST):
    pass
