"""Big JSON answers are compressed for clients that accept it; small ones and the chat stream are left alone."""
import gzip
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

import main


def _client() -> TestClient:
    return TestClient(main.app, raise_server_exceptions=False)


def test_the_real_app_compresses_a_large_answer_and_it_decodes_to_the_same_json():
    app = FastAPI()
    for layer in main.app.user_middleware:
        if layer.cls.__name__ == "GZipMiddleware":
            app.add_middleware(layer.cls, **layer.kwargs)
    big = {"entries": [{"id": i, "note": "steady sleep and a calm morning"} for i in range(200)]}

    @app.get("/big")
    def big_answer():
        return JSONResponse(big)

    @app.get("/small")
    def small_answer():
        return JSONResponse({"ok": True})

    @app.get("/stream")
    def stream():
        return StreamingResponse(iter([b"data: " + b"x" * 2000 + b"\n\n"]), media_type="text/event-stream")

    client = TestClient(app)
    raw = client.get("/big", headers={"Accept-Encoding": "gzip"})
    assert raw.headers.get("content-encoding") == "gzip"
    assert raw.json() == big   # the client library decodes it; same answer
    assert len(gzip.compress(json.dumps(big).encode())) < len(json.dumps(big)) / 3
    assert client.get("/small", headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding") is None
    assert client.get("/stream", headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding") is None
    assert client.get("/big", headers={"Accept-Encoding": "identity"}).headers.get("content-encoding") is None


def test_the_app_has_the_compression_layer_installed():
    assert any(layer.cls.__name__ == "GZipMiddleware" for layer in main.app.user_middleware)
