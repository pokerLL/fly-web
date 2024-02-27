from fly import Fly
from fly.context import crequest
import shutil

app = Fly(__name__)


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


if __name__ == "__main__":
    app.run(debug=True)
