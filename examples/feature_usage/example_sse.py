import random
import datetime
import time

from fly import Fly

app = Fly(__name__)


@app.sse("/sse", methods=["GET"])
async def sse_func(id: int):
    total = random.randint(1, 10) * 5
    for _ in range(total):
        yield f"SSE1 id:{id} {_+1}/{total} - {datetime.datetime.now()}"
        time.sleep(1)


@app.sse("/sse2", methods=["GET"])
def sse_func2(id: int):
    total = random.randint(1, 10) * 5
    for _ in range(total):
        yield f"SSE2 id:{id} {_+1}/{total} - {datetime.datetime.now()}"
        time.sleep(1)


if __name__ == "__main__":
    app.run(debug=True)
