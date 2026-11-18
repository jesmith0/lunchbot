import datetime
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode

import pytest
from flask import Flask
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier

from lunchbot import cli
from lunchbot.adapters.slack import SlackAdapter, _chunks, parse_mentions, render
from lunchbot.config import Config, ConfigError, SlackConfig
from lunchbot.core import MONDAY
from lunchbot.messages import Action, Icon, Mention, Message
from lunchbot.web import mount_slack

SECRET = "test-signing-secret"


# -- rendering ---------------------------------------------------------------


def test_render_daily_pick(bot, data_dir):
    (data_dir / "restaurants.txt").write_text("TACO BUS, 1\n")
    (data_dir / "drivers.txt").write_text("JEREMY, 1, slack:U0123ABC\n")
    out = render(bot.daily_pick(MONDAY))
    assert out["text"] == (
        ":cook: Hello there children! Today we're going on a field trip to TACO BUS and "
        "<@U0123ABC> is driving!"
    )
    assert out["blocks"][0] == {"type": "section", "text": {"type": "mrkdwn", "text": out["text"]}}
    buttons = out["blocks"][1]["elements"]
    assert [(b["text"]["text"], b["value"]) for b in buttons] == [
        (":+1: Upvote", "upvote TACO BUS"),
        (":-1: Downvote", "downvote TACO BUS"),
        (":nauseated_face: Gross", "gross"),
    ]
    assert len({b["action_id"] for b in buttons}) == 3


def test_render_mention_without_slack_id_uses_name():
    assert render(Message(("Hi ", Mention("MASON"), "!")))["text"] == "Hi MASON!"


def test_render_escapes_user_text():
    # Names come from users; "<!channel>" must not become an @channel ping.
    text = render(Message.of("<!channel> & <@U1> added"))["text"]
    assert text == "&lt;!channel&gt; &amp; &lt;@U1&gt; added"


def test_render_splits_long_text_into_sections():
    message = Message.of("".join(f"RESTAURANT {i}, 5\n" for i in range(400)))
    blocks = render(message)["blocks"]
    assert len(blocks) > 1
    assert all(len(b["text"]["text"]) <= 3000 for b in blocks)
    assert "\n".join(b["text"]["text"] for b in blocks) == render(message)["text"]


def test_chunks_handles_one_overlong_line():
    assert _chunks("x" * 7, 3) == ["xxx", "xxx", "x"]


def test_parse_mentions():
    looked_up = []

    def name_of(user_id):
        looked_up.append(user_id)
        return "masonj"

    text, mentions = parse_mentions("add driver <@U0123ABC|jeremy> <@W999>", name_of)
    assert text == "add driver jeremy masonj"
    assert mentions == (
        Mention("jeremy", {"slack": "U0123ABC"}),
        Mention("masonj", {"slack": "W999"}),
    )
    assert looked_up == ["W999"]


# -- a fake Slack: Web API plus response_url, on a local port ---------------------


class FakeSlack:
    def __init__(self):
        self.calls = []  # (path, body dict)
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers["Content-Length"] or 0)).decode()
                if self.headers.get("Content-Type", "").startswith("application/json"):
                    body = json.loads(raw) if raw else {}
                else:
                    body = {k: v[0] for k, v in parse_qs(raw).items()}
                fake.calls.append((self.path, body))
                reply = {"ok": True}
                if self.path.endswith("auth.test"):
                    reply.update(user_id="UBOT", bot_id="B1", team_id="T1")
                elif self.path.endswith("users.info"):
                    reply["user"] = {"name": "mjeffers", "profile": {"display_name": "mason"}}
                data = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/"
        threading.Thread(target=self.server.serve_forever, args=(0.01,), daemon=True).start()

    def paths(self):
        return [p for p, _ in self.calls]

    def wait_for(self, path, count=1):
        deadline = time.monotonic() + 5
        while self.paths().count(path) < count and time.monotonic() < deadline:
            time.sleep(0.01)
        return [b for p, b in self.calls if p == path]


@pytest.fixture
def slack(bot):
    fake = FakeSlack()
    config = Config(slack=SlackConfig(bot_token="xoxb-test", signing_secret=SECRET))
    flask_app = Flask("test")
    cli_make_bot = cli.make_bot
    cli.make_bot = lambda config: bot
    try:
        mount_slack(
            flask_app,
            config,
            client=WebClient(token="xoxb-test", base_url=fake.url),
            process_before_response=True,  # finish listeners before replying, for asserts
        )
    finally:
        cli.make_bot = cli_make_bot
    fake.client = flask_app.test_client()
    yield fake
    fake.server.shutdown()


def post(fake, form, secret=SECRET):
    body = urlencode(form)
    ts = str(int(time.time()))
    sig = SignatureVerifier(secret).generate_signature(timestamp=ts, body=body)
    return fake.client.post(
        "/slack/events",
        data=body,
        content_type="application/x-www-form-urlencoded",
        headers={"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": sig},
    )


def slash(fake, text, user="U0ALICE", secret=SECRET):
    return post(
        fake,
        {
            "command": "/lunchbot",
            "text": text,
            "user_id": user,
            "user_name": "alice",
            "team_id": "T1",
            "channel_id": "C1",
            "response_url": fake.url + "respond",
            "trigger_id": "1.2.3",
        },
        secret,
    )


def click(fake, value, user="U0ALICE"):
    payload = {
        "type": "block_actions",
        "user": {"id": user},
        "team": {"id": "T1"},
        "channel": {"id": "C1"},
        "trigger_id": "1.2.3",
        "response_url": fake.url + "respond",
        "actions": [
            {"type": "button", "action_id": "lunchbot_action_0", "block_id": "b", "value": value}
        ],
    }
    return post(fake, {"payload": json.dumps(payload)})


# -- slash commands ------------------------------------------------------------


def test_slash_command_replies_in_channel(slack):
    resp = slash(slack, "list restaurants")
    assert resp.status_code == 200
    assert resp.json["response_type"] == "in_channel"
    assert resp.json["text"] == "RESTAURANTS, WEIGHT\nCHIPOTLE, 5\nEVOS, 1"


def test_help_is_ephemeral(slack):
    resp = slash(slack, "")
    assert resp.json["response_type"] == "ephemeral"
    assert resp.json["text"].startswith("Proper usage: /lunchbot")


def test_unsigned_request_rejected(slack, data_dir):
    resp = slash(slack, "remove restaurant chipotle", secret="wrong-secret")
    assert resp.status_code == 401
    assert "CHIPOTLE" in (data_dir / "restaurants.txt").read_text()


def test_add_driver_by_mention_stores_slack_id(slack, data_dir):
    resp = slash(slack, "add driver <@U0MASON|mason>")
    assert resp.json["text"] == "MASON added to DRIVER list!"
    assert "MASON, 1, slack:U0MASON\n" in (data_dir / "drivers.txt").read_text()


def test_mention_without_name_is_looked_up(slack, data_dir):
    slash(slack, "add driver <@U0MASON>")
    assert [c["user"] for c in slack.wait_for("/users.info")] == ["U0MASON"]
    assert "MASON, 1, slack:U0MASON\n" in (data_dir / "drivers.txt").read_text()


def test_mention_links_existing_driver(slack, data_dir):
    resp = slash(slack, "add driver <@U0JEREMY|jeremy>")
    assert resp.json["text"] == "JEREMY will now be @-mentioned when driving!"
    assert (data_dir / "drivers.txt").read_text() == "JEREMY, 1, slack:U0JEREMY\n"
    assert slash(slack, "add driver <@U0JEREMY|jeremy>").json["text"] == (
        "JEREMY already exists in DRIVER list!"
    )


# -- buttons -------------------------------------------------------------------


def test_vote_button_updates_weight_and_replies_to_voter(slack, data_dir):
    assert click(slack, "upvote CHIPOTLE").status_code == 200
    (reply,) = slack.wait_for("/respond")
    assert reply["response_type"] == "ephemeral"
    assert reply["replace_original"] is False
    assert reply["text"] == ":+1: CHIPOTLE upvoted (weight 6)"
    assert "CHIPOTLE, 6" in (data_dir / "restaurants.txt").read_text()


def test_third_gross_click_reposts_lunch_to_channel(slack, bot):
    bot._today = lambda: datetime.date(2026, 11, 16)  # a Monday
    for user in ("U1", "U2", "U3"):
        click(slack, "gross", user)
    replies = slack.wait_for("/respond", 3)
    assert [r["response_type"] for r in replies] == ["ephemeral", "ephemeral", "in_channel"]
    assert "field trip to" in replies[2]["text"]
    assert replies[2]["blocks"][1]["type"] == "actions"


# -- scheduled posts -------------------------------------------------------------


def test_adapter_posts_to_channel():
    fake = FakeSlack()
    try:
        adapter = SlackAdapter(WebClient(token="xoxb-test", base_url=fake.url), "C0LUNCH")
        adapter.send(Message.of("hi", icon=Icon.DONE, actions=(Action("Gross", "gross"),)))
        (call,) = fake.wait_for("/chat.postMessage")
        assert call["channel"] == "C0LUNCH"
        assert call["text"] == ":white_check_mark: hi"
        assert call["blocks"][1]["elements"][0]["value"] == "gross"
    finally:
        fake.server.shutdown()


def test_make_adapter_for_slack():
    config = Config(platform="slack", slack=SlackConfig(bot_token="xoxb-t", channel="C0LUNCH"))
    adapter = cli.make_adapter(config)
    assert isinstance(adapter, SlackAdapter)
    assert adapter.channel == "C0LUNCH"


def test_missing_slack_settings_named_without_values():
    config = SlackConfig(bot_token="xoxb-secret-value")
    with pytest.raises(ConfigError) as exc:
        config.require("bot_token", "channel", "signing_secret")
    assert str(exc.value) == (
        "Slack needs these environment variables: LUNCHBOT_SLACK_CHANNEL, SLACK_SIGNING_SECRET"
    )


def test_cli_exits_cleanly_on_missing_config(monkeypatch, data_dir):
    monkeypatch.setenv("LUNCHBOT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("LUNCHBOT_PLATFORM", "slack")
    for var in ("SLACK_BOT_TOKEN", "LUNCHBOT_SLACK_CHANNEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(cli.Bot, "close_voting", lambda self: Message.of("x"))
    with pytest.raises(SystemExit, match="SLACK_BOT_TOKEN, LUNCHBOT_SLACK_CHANNEL"):
        cli.main(["close-voting"])
    with pytest.raises(SystemExit, match="SLACK_APP_TOKEN"):
        cli.main(["serve"])
