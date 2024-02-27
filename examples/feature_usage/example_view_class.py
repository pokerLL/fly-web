from fly.view import View
from fly import Fly

app = Fly(__name__)


class UserService(View):
    def __init__(self) -> None:
        self.name = "fly"

    def get(self, id: int):
        return {"method": "get", "id": id, "name": self.name}

    def post(self, id: int):
        return {"method": "post", "id": id, "name": self.name}


app.kls_route("/user", UserService.as_view())

""" 
curl -X GET http://127.0.0.1:5000/user?id=1
curl -X POST http://127.0.0.1:5000/user?id=1
"""


if __name__ == "__main__":
    app.run(debug=True)
