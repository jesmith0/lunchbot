import pytest

from lunchbot.web import app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_index_page(client):
    assert client.get("/").status_code == 200


def test_lunchbot_page(client):
    resp = client.get("/lunchbot")
    assert resp.status_code == 200
    assert b"lunchbot.png" in resp.data
    assert client.get("/static/lunchbot.png").status_code == 200


def test_hipchat_webhook_is_gone(client):
    # HipChat shut down in 2019; its webhook endpoint was removed in #9.
    assert client.post("/lunchbot", data="{}").status_code == 405
