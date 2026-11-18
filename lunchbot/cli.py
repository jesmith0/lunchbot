"""Command-line entry point: `lunchbot <command>` (or `python -m lunchbot`)."""

import argparse
import getpass
import logging
import sys

from lunchbot.adapters.base import ChatAdapter
from lunchbot.adapters.console import ConsoleAdapter
from lunchbot.config import Config, ConfigError
from lunchbot.core import Bot
from lunchbot.storage import Store


def make_bot(config: Config) -> Bot:
    return Bot(Store(config.data_dir))


def make_adapter(config: Config) -> ChatAdapter:
    if config.platform == "slack":
        from slack_sdk import WebClient

        from lunchbot.adapters.slack import SlackAdapter

        config.slack.require("bot_token", "channel")
        assert config.slack.channel is not None
        return SlackAdapter(WebClient(token=config.slack.bot_token), config.slack.channel)
    return ConsoleAdapter()


def serve_slack(config: Config) -> None:
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    from lunchbot.adapters.slack import create_app

    config.slack.require("bot_token", "app_token")
    app = create_app(make_bot(config), config.slack)
    SocketModeHandler(app, config.slack.app_token).start()  # type: ignore[no-untyped-call]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lunchbot", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="try the bot in this terminal")
    chat.add_argument("--user", default=getpass.getuser(), help="who you are (for votes)")
    sub.add_parser("serve", help="answer /lunchbot in Slack over Socket Mode")
    sub.add_parser("post-lunch", help="announce today's lunch (run on a schedule)")
    sub.add_parser("close-voting", help="close veto voting for today (run on a schedule)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    try:
        config = Config.from_env()
        if args.command == "chat":
            ConsoleAdapter().serve(make_bot(config), args.user)
        elif args.command == "serve":
            serve_slack(config)
        else:
            bot = make_bot(config)
            message = bot.daily_pick() if args.command == "post-lunch" else bot.close_voting()
            if message is None:
                logging.info("Nothing to post today")
                return
            make_adapter(config).send(message)
    except ConfigError as e:
        sys.exit(f"lunchbot: {e}")
