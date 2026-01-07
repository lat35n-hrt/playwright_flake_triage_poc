from __future__ import annotations

import httpx
import pytest

from tests.app_import import load_fastapi_app


@pytest.fixture(scope="session")
def app():
    return load_fastapi_app()


@pytest.fixture()
async def client(app):
    transport = httpx.ASGITransport(app=app)
    # base_url is required by httpx even for ASGITransport
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
