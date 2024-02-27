from fly import Fly

app = Fly(__name__)

app.static("/static", "./statics")

if __name__ == "__main__":
    app.run(debug=True)
