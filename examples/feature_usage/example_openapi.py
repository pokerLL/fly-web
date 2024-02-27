from fly import Fly

app = Fly({"fly": {"name": "dev"}})


@app.get("/")
def index():
    return {"message": "Hello, World!"}


@app.post("/op")
def op(request):
    return {"message": "op"}


if __name__ == "__main__":
    app.run(port=8000, debug=True)
