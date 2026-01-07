from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio

async def test_health_returns_200_and_json(client):
    resp = await client.get("/health")

    assert resp.status_code == 200, (
        f"GET /health should return 200. got={resp.status_code}, body={resp.text}"
    )

    # must be JSON
    data = resp.json()
    assert isinstance(data, dict), (
        f"GET /health should return JSON object. got_type={type(data)}, body={data}"
    )

    # optional, but helpful: if 'status' exists, it should look healthy
    if "status" in data:
        assert str(data["status"]).lower() in {"ok", "healthy", "pass"}, (
            f"/health 'status' should indicate healthy. got={data['status']}"
        )
