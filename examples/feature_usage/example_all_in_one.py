from typing import Annotated
from fly import Fly
from fly.context import crequest
from fly.exception import WebSocketDisconnectedError
from fly.middleware import BaseMiddleware
from fly.schema import HeaderParam, PathParam, QueryParam, CookieParam
from fly.utils import logger
from fly.view import View
from pydantic import BaseModel
import random
import datetime
import time
import shutil

config = {
    "fly": {
        "name": "Fly demo - All In One",
        "openapi": {
            "info": {"description": "A demo for Fly", "contact": {"email": "llggg2323@163.com", "name": "fly"}, "license": {"name": "MIT"}},
            "servers": [{"url": "http://localhost:5000", "description": "Local server"}],
            "openapi_route": "/openapi",
            "swagger_route": "/swagger",
        },
        "task": {
            "start_with_server": False,
        },
        "CORS": {
            "allow_origins": ["*"],
            "allow_methods": ["*"],
            "allow_headers": ["*"],
            "allow_credentials": True,
            "expose_headers": ["*"],
            "max_age": 600,
        },
    }
}

app = Fly(config)


@app.get("/")
def index():
    """
    A simple route to return a hello world message.

    Returns:
        dict: A greeting message.
    """
    return {"message": "hello world"}


@app.post("/param/<int:pid>")
def param(pid: Annotated[int, PathParam()], qid: Annotated[int, QueryParam()], cid: Annotated[int, CookieParam()], hid: Annotated[int, HeaderParam()]):
    """
    A route to demonstrate the use of different parameter types: path, query, cookie, and header parameters.

    Args:
        pid (int): The path parameter.
        qid (int): The query parameter.
        cid (int): The cookie parameter.
        hid (int): The header parameter.

    Returns:
        dict: A dictionary of received parameters.
    """
    return {"pid": pid, "qid": qid, "cid": cid, "hid": hid}


class User(BaseModel):
    name: str
    age: int


@app.post("/schema/1")
def schema1(user: User):
    """
    A route to demonstrate the use of request body schema validation.

    Args:
        user (User): The user data parsed from the request body.

    Returns:
        User: The received user data.
    """
    return user


@app.get("/schema/2")
def schema2() -> User:
    """
    A route to demonstrate the use of response body schema validation.

    Returns:
        User: A mock user data.
    """
    return {"name": "fly", "age": 1}


@app.sse("/sse1", methods=["GET"])
async def sse_func(total: int):
    """
    A route for server-sent events (SSE), demonstrating a simple event stream.

    Args:
        id (int): An identifier to customize the event stream.

    Yields:
        str: An event stream message.
    """
    # total = random.randint(1, 5) * id
    for _ in range(total):
        # yield f"SSE1 id:{id} {_+1}/{total} - {datetime.datetime.now()}"
        yield f"SSE1 {total}: {_+1}/{total}\n"
        time.sleep(1)


@app.sse("/sse2", methods=["GET"])
def sse_func2(total: int):
    """
    Another route for server-sent events (SSE), similar to the first but without async.

    Args:
        id (int): An identifier to customize the event stream.

    Yields:
        str: An event stream message.
    """
    # total = random.randint(1, 5) * id
    for _ in range(total):
        # yield f"SSE2 id:{id} {_+1}/{total} - {datetime.datetime.now()}"
        yield f"SSE2 {total}: {_+1}/{total}\n"
        time.sleep(1)


# app.get('/url', handle)


@app.websocket("/ws")
async def websocket_func(ws):
    """
    A route for WebSocket communication.

    Args:
        ws: The WebSocket connection object.

    Yields:
        str: WebSocket messages.
    """
    try:
        while True:
            msg = await ws.receive()
            await ws.send(f"{msg}~")
            # await ws.send(f"hello world {datetime.datetime.now()} : {msg}")
    except WebSocketDisconnectedError as e:
        pass


class UserService(View):
    def __init__(self) -> None:
        self.name = "fly"

    def get(self, id: int):
        """
        Handles GET requests for the user service.

        Args:
            id (int): The user identifier.

        Returns:
            dict: User information.
        """
        return {"method": "get", "id": id, "name": self.name}

    def post(self, id: int):
        """
        Handles POST requests for the user service.

        Args:
            id (int): The user identifier.

        Returns:
            dict: User information.
        """
        return {"method": "post", "id": id, "name": self.name}


app.kls_route("/user", UserService.as_view())


@app.route("/upload", methods=["POST"])
async def upload():
    form_data = await crequest.body.dict()
    file_names = ["file1", "file2"]
    print(form_data)
    for fn in file_names:
        fio = form_data[fn]["tempfile"]
        fnn = form_data[fn]["filename"]
        with open(fio, "rb") as fin, open(f"temp_{fnn}", "wb") as fout:
            shutil.copyfileobj(fin, fout)
    return {}


# Middleware
class AddRequestInfoMiddleware(BaseMiddleware):
    async def process_request(self):
        pass

    async def process_response(self, response):
        logger.debug(f"AddRequestInfoMiddleware after_request, type: {type(response)}")
        if isinstance(response, dict):
            # response["request_info"] = {"url": crequest.path, "method": crequest.method, "uuid": crequest.uuid}
            pass


if __name__ == "__main__":
    app.run(debug=True)
