"""Flask app. Chat platforms that deliver commands over HTTP mount their routes here."""

import logging
from typing import Any

from flask import Flask, Response, render_template, request

from lunchbot.config import Config

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.update(PROPAGATE_EXCEPTIONS=True)


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/lunchbot")
def lunchbot() -> str:
    return render_template("lunchbot.html")


def mount_slack(flask_app: Flask, config: Config, **app_kwargs: Any) -> None:
    """Serve Slack's slash commands and button clicks at POST /slack/events."""
    from slack_bolt.adapter.flask import SlackRequestHandler

    from lunchbot.adapters.slack import create_app
    from lunchbot.cli import make_bot

    config.slack.require("bot_token", "signing_secret")
    handler = SlackRequestHandler(create_app(make_bot(config), config.slack, **app_kwargs))

    @flask_app.route("/slack/events", methods=["POST"])
    def slack_events() -> Response:
        return handler.handle(request)


_config = Config.from_env()
if _config.slack.signing_secret:
    mount_slack(app, _config)
    logger.info("Slack HTTP mode: listening at /slack/events")


if __name__ == "__main__":
    app.run(debug=True)
