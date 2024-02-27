from fly import Fly
from fly.route import Router

app = Fly(__name__)

user_router = Router(None, "/user")


@user_router.get("/<int:id>")
def user(id: int):
    return {"id": id}


@user_router.post("/<int:id>/info")
def user_info(id: int):
    return {"id": id, "info": "info"}


user_operation_router = user_router.group("/operation")


@user_operation_router.post("/<int:id>")  # /user/operation/1
def user_operation(id: int, operation):
    return {"id": id, "operation": operation}


app.register_router(user_router)

if __name__ == "__main__":
    app.run(debug=True, port=8000)

"""
host: http://127.0.0.1:8000

curl http://127.0.0.1:8000/user/1
curl -X POST http://127.0.0.1:8000/user/1/info
curl -X POST http://127.0.0.1:8000/user/operation/1?operation=delete
"""
