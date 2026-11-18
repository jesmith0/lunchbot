import json

import pytest

import backend


@pytest.fixture
def client(monkeypatch):
    calls = []
    monkeypatch.setattr(
        backend, "process_message", lambda msg, user, room: calls.append((msg, user, room)) or "ok"
    )
    backend.app.config.update(TESTING=True)
    with backend.app.test_client() as c:
        c.calls = calls
        yield c


def hipchat_payload(message, user="Alice", room="Rogue One"):
    return json.dumps(
        {
            "item": {
                "message": {"message": message, "from": {"name": user}},
                "room": {"name": room},
            }
        }
    )


def test_index_page(client):
    assert client.get("/").status_code == 200


def test_lunchbot_page(client):
    resp = client.get("/lunchbot")
    assert resp.status_code == 200
    assert b"lunchbot.png" in resp.data


def test_webhook_dispatches_message(client):
    resp = client.post("/lunchbot", data=hipchat_payload("/lunchbot list restaurants"))
    assert resp.status_code == 200
    assert resp.data == b"ok"
    assert client.calls == [("/lunchbot list restaurants", "Alice", "Rogue One")]


def test_webhook_rejects_invalid_json(client):
    resp = client.post("/lunchbot", data="not json")
    assert resp.status_code == 400
    assert resp.data.startswith(b"Invalid JSON in request")
    assert client.calls == []
