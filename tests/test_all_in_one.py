import json
import random

import pytest

from fly.testclient import get_test_client

from examples.feature_usage.example_all_in_one import app


class TestAllInOne:
    def setup_class(self):
        self.client = get_test_client(app)

    def test_index(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        assert resp.body == json.dumps({"message": "hello world"}).encode("utf-8")
        assert resp.dict == {"message": "hello world"}

    def test_param(self):
        pid = random.randint(1, 10)  # noqa
        qid = random.randint(1, 10)  # noqa
        hid = random.randint(1, 10)  # noqa
        cid = random.randint(1, 10)  # noqa
        resp = self.client.post(f"/param/{pid}?qid={qid}", headers={"hid": f"{hid}", "Cookie": f"cid={cid}"})
        assert resp.status_code == 200
        assert resp.body == json.dumps({"pid": pid, "qid": qid, "cid": cid, "hid": hid}).encode("utf-8")

    def test_schema1(self):
        resp = self.client.post("/schema/1", json={"name": "fly", "age": 1})
        assert resp.status_code == 200
        assert resp.body == json.dumps({"name": "fly", "age": 1}).encode("utf-8")

    def test_schema2(self):
        resp = self.client.get("/schema/2")
        assert resp.status_code == 200
        assert resp.body == json.dumps({"name": "fly", "age": 1}).encode("utf-8")

    @pytest.mark.asyncio
    async def test_sse1(self):
        total = random.randint(1, 10)  # noqa
        resp = await self.client.get(f"/sse1?total={total}", is_sse=True)
        assert resp.status_code == 200
        assert len(resp.messages) == total
        assert all(msg == f"data: SSE1 {total}: {_+1}/{total}\n".encode() for _, msg in enumerate(resp.messages))

    @pytest.mark.asyncio
    async def test_sse2(self):
        total = random.randint(1, 10)  # noqa
        resp = await self.client.get(f"/sse2?total={total}", is_sse=True)
        assert resp.status_code == 200
        assert len(resp.messages) == total
        assert all(msg == f"data: SSE2 {total}: {_+1}/{total}\n".encode() for _, msg in enumerate(resp.messages))

    @pytest.mark.asyncio
    async def test_ws(self):
        async with self.client.ws("/ws") as ws:
            await ws.send("PING")
            assert await ws.receive() == "PONG"
            await ws.send("ping")
            assert await ws.receive() == "PONG"
            await ws.send("hello world")
            assert await ws.receive() == "hello world~"

    def test_user_get(self):
        resp = self.client.get("/user?id=1")
        assert resp.status_code == 200
        assert resp.body == json.dumps({"method": "get", "id": 1, "name": "fly"}).encode("utf-8")

    def test_user_post(self):
        resp = self.client.post("/user?id=1")
        assert resp.status_code == 200
        assert resp.body == json.dumps({"method": "post", "id": 1, "name": "fly"}).encode("utf-8")
