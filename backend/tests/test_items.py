from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio

ITEMS_PATH = "/api/items"


def _extract_items(payload):
    # Accept both patterns:
    #  - list: [...]
    #  - dict: {"items": [...]}
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "items" in payload and isinstance(payload["items"], list):
        return payload["items"]
    return None


async def test_get_items_returns_200_and_json(client):
    resp = await client.get(ITEMS_PATH)

    assert resp.status_code == 200, (
        f"GET {ITEMS_PATH} should return 200. got={resp.status_code}, body={resp.text}"
    )

    payload = resp.json()
    items = _extract_items(payload)
    assert items is not None, (
        f"GET {ITEMS_PATH} should return list or {{'items': list}}. got_type={type(payload)}, body={payload}"
    )


async def test_post_item_returns_200_or_201_and_json(client):
    # Keep payload minimal and generic; adjust to your API contract if needed.
    new_item = {"name": "poc-item"}

    resp = await client.post(ITEMS_PATH, json=new_item)
    assert resp.status_code in (200, 201), (
        f"POST {ITEMS_PATH} should return 200 or 201. got={resp.status_code}, body={resp.text}"
    )

    payload = resp.json()
    assert isinstance(payload, (dict, list)), (
        f"POST {ITEMS_PATH} should return JSON. got_type={type(payload)}, body={payload}"
    )

    # Contract-lite: response should include at least the name we sent (common pattern)
    if isinstance(payload, dict):
        assert payload.get("name") == new_item["name"], (
            f"POST response should include the created item's name. expected={new_item['name']}, got={payload}"
        )
