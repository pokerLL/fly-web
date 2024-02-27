import datetime

from fly import Fly
from fly.utils import logger
from fly.exception import WebSocketDisconnectedError


app = Fly(__name__)


@app.websocket("/ws")
async def websocket_func(ws):
    try:
        while True:
            msg = await ws.receive()
            # logger.debug(f"ws received: {msg}")
            await ws.send(f"hello world {datetime.datetime.now()} : {msg}")
    except WebSocketDisconnectedError as e:
        # logger.debug(f"ws disconnected : {e}")
        pass


if __name__ == "__main__":
    app.run(debug=True)
