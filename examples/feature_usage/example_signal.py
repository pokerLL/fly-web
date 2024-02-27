from fly import Fly
from fly.constant import BuiltinSignal
from fly.utils import logger

app = Fly(__name__)


def server_startup():
    logger.info("server_startup....")


custom_signal = "custom_signal"
app.register_signal(custom_signal)


def handler(*args, **kwargs):
    logger.info(f"handler got {args} - {kwargs}")


app.connect(BuiltinSignal.SERVER_STARTUP, server_startup)
app.connect(custom_signal, handler)


@app.get("/")
def index():
    app.send_signal(custom_signal, "index")
    return {"message": "hello world~"}


if __name__ == "__main__":
    app.run(debug=True)

"""
curl http://127.0.0.1:5000/
"""
