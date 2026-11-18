"""Command-line entry point: `lunchbot <command>` (or `python -m lunchbot`)."""

import argparse
import getpass
import logging

from lunchbot.adapters.base import ChatAdapter
from lunchbot.adapters.console import ConsoleAdapter
from lunchbot.config import Config
from lunchbot.core import Bot
from lunchbot.storage import Store


def make_bot(config: Config) -> Bot:
    return Bot(Store(config.data_dir))


def make_adapter(config: Config) -> ChatAdapter:
    return ConsoleAdapter()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lunchbot", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat", help="try the bot in this terminal")
    chat.add_argument("--user", default=getpass.getuser(), help="who you are (for votes)")
    sub.add_parser("post-lunch", help="announce today's lunch (run on a schedule)")
    sub.add_parser("close-voting", help="close veto voting for today (run on a schedule)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    config = Config.from_env()
    bot = make_bot(config)

    if args.command == "chat":
        ConsoleAdapter().serve(bot, args.user)
        return

    message = bot.daily_pick() if args.command == "post-lunch" else bot.close_voting()
    if message is None:
        logging.info("Nothing to post today")
        return
    make_adapter(config).send(message)
