from fly import Fly

app = Fly(__name__)


def cost_task(*args, **kwargs):
    with open("test.txt", "a") as f:
        f.write(f"cost_task\n{args}\n{kwargs}\n")
    print(f"cost_task {args} {kwargs}")
    return "cost_task"


@app.route("/")
def index():
    app.add_delay_task(cost_task, 10, args=(1, 2, 3), kwargs={"a": 1, "b": 2})
    return {"hello": "world"}


if __name__ == "__main__":
    app.run(debug=True, port=5060)
