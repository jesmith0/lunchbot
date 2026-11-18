"""Slack adapter, built on Bolt for Python.

Two ways to receive `/lunchbot` commands and button clicks:
- Socket Mode (`lunchbot serve`): the bot connects out to Slack; no public URL needed.
- HTTP (`lunchbot.wsgi`): Slack posts to /slack/events on the Flask app.
Bolt verifies request signatures in HTTP mode; Socket Mode is authenticated by the app token.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

from slack_bolt import Ack, App, Respond
from slack_sdk import WebClient

from lunchbot.config import SlackConfig
from lunchbot.core import Bot
from lunchbot.messages import Icon, Mention, Message

logger = logging.getLogger(__name__)

PLATFORM = "slack"
COMMAND = "/lunchbot"
ACTION_ID = re.compile(r"^lunchbot_action_\d+$")
# Slack's limit on a section block's text
SECTION_LIMIT = 3000

EMOJI = {
    Icon.CHEF: ":cook:",
    Icon.MIND_BLOWN: ":exploding_head:",
    Icon.THINKING: ":thinking_face:",
    Icon.UPVOTE: ":+1:",
    Icon.DOWNVOTE: ":-1:",
    Icon.GROSS: ":nauseated_face:",
    Icon.DONE: ":white_check_mark:",
}

# <@U0123ABC> or <@U0123ABC|name>: how Slack escapes a user mention in command text
USER_MENTION = re.compile(r"<@([UW][A-Z0-9]+)(?:\|([^>]*))?>")


def escape(text: str) -> str:
    """Escape the three characters Slack's mrkdwn treats as control characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(message: Message) -> dict[str, Any]:
    """The keyword arguments for chat.postMessage / respond: text fallback plus blocks."""
    text = "".join(
        f"<@{p.ids[PLATFORM]}>" if isinstance(p, Mention) and PLATFORM in p.ids
        else escape(p.name if isinstance(p, Mention) else p)
        for p in message.parts
    )  # fmt: skip
    if message.icon is not None:
        text = f"{EMOJI[message.icon]} {text}"
    text = text.rstrip("\n")

    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": chunk}}
        for chunk in _chunks(text, SECTION_LIMIT)
    ]
    if message.actions:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": f"lunchbot_action_{i}",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": f"{EMOJI[a.icon]} {a.label}" if a.icon else a.label,
                        },
                        "value": a.command,
                    }
                    for i, a in enumerate(message.actions)
                ],
            }
        )
    return {"text": text, "blocks": blocks}


def _chunks(text: str, size: int) -> list[str]:
    """Split on line breaks into pieces of at most `size` characters."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > size:  # a single overlong line
            chunks.append(line[:size])
            line = line[size:]
        if len(current) + len(line) > size:
            chunks.append(current)
            current = ""
        current += line
    if current or not chunks:
        chunks.append(current)
    return [c.rstrip("\n") or " " for c in chunks]


def parse_mentions(
    text: str, display_name: Callable[[str], str]
) -> tuple[str, tuple[Mention, ...]]:
    """Replace Slack user mentions with names; return the new text and the mentions."""
    mentions: list[Mention] = []

    def sub(match: re.Match[str]) -> str:
        user_id, name = match.group(1), match.group(2) or display_name(match.group(1))
        mentions.append(Mention(name, {PLATFORM: user_id}))
        return name

    return USER_MENTION.sub(sub, text), tuple(mentions)


class SlackAdapter:
    """Posts scheduled messages (the daily pick) to the configured channel."""

    def __init__(self, client: WebClient, channel: str) -> None:
        self.client = client
        self.channel = channel

    def send(self, message: Message) -> None:
        self.client.chat_postMessage(channel=self.channel, **render(message))


def create_app(bot: Bot, config: SlackConfig, **app_kwargs: Any) -> App:
    """A Bolt app that routes /lunchbot and button clicks to `bot`."""
    app = App(token=config.bot_token, signing_secret=config.signing_secret, **app_kwargs)

    def display_name(client: WebClient, user_id: str) -> str:
        try:
            user = client.users_info(user=user_id)["user"]
        except Exception:
            logger.exception("Could not look up Slack user %s", user_id)
            return user_id
        profile = user.get("profile", {})
        return str(profile.get("display_name") or profile.get("real_name") or user["name"])

    @app.command(COMMAND)
    def on_command(ack: Ack, command: dict[str, Any], client: WebClient) -> None:
        text, mentions = parse_mentions(command["text"], lambda u: display_name(client, u))
        message = bot.handle(text, command["user_id"], mentions)
        # Replying through ack() answers within Slack's 3-second window in one round trip.
        ack(response_type="in_channel" if message.public else "ephemeral", **render(message))

    @app.action(ACTION_ID)
    def on_button(ack: Ack, body: dict[str, Any], respond: Respond) -> None:
        ack()
        message = bot.handle(body["actions"][0]["value"], body["user"]["id"])
        # A vote from a button only needs to be seen by the voter, but a vetoed lunch's
        # new pick (it has its own buttons) is news for the whole channel.
        response_type = "in_channel" if message.actions else "ephemeral"
        respond(response_type=response_type, replace_original=False, **render(message))

    return app
