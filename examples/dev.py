from fly import Fly

app = Fly(__name__)


@app.get("/")
def hello():
    return {"message": "fly fly"}


if __name__ == "__main__":
    app.run()
