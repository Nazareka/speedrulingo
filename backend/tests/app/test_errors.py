from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from errors import register_error_handlers


def test_unhandled_exception_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise ValueError("kaboom")

    register_error_handlers(app)

    with caplog.at_level(logging.ERROR), TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    assert "Unhandled exception on GET /boom" in caplog.text
    assert "ValueError: kaboom" in caplog.text


def test_http_500_exception_detail_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()

    @app.get("/http-boom")
    def http_boom() -> dict[str, str]:
        raise HTTPException(status_code=500, detail="broken payload")

    register_error_handlers(app)

    with caplog.at_level(logging.ERROR), TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/http-boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "broken payload"}
    assert "HTTPException on GET /http-boom: status=500 detail=broken payload" in caplog.text
