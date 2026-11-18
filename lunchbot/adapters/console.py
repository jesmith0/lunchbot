"""Chat with the bot in a terminal. Handy for trying it without a chat service."""

import sys
from typing import TextIO

from lunchbot.core import Bot
from lunchbot.messages import Icon, Mention, Message

EMOJI = {
    Icon.CHEF: "🧑‍🍳",
    Icon.MIND_BLOWN: "🤯",
    Icon.THINKING: "🤔",
    Icon.UPVOTE: "👍",
    Icon.DOWNVOTE: "👎",
    Icon.GROSS: "🤢",
    Icon.DONE: "✅",
}


def render(message: Message) -> str:
    text = "".join(f"@{p.name}" if isinstance(p, Mention) else p for p in message.parts)
    if message.icon is not None:
        text = f"{EMOJI[message.icon]} {text}"
    if message.actions:
        buttons = "  ".join(
            f"[{EMOJI[a.icon] + ' ' if a.icon else ''}{a.label}: {a.command}]"
            for a in message.actions
        )
        text = f"{text}\n{buttons}"
    return text.rstrip("\n")


class ConsoleAdapter:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out = out

    @property
    def out(self) -> TextIO:
        # resolved per call so redirected stdout (e.g. in tests) is honored
        return self._out or sys.stdout

    def send(self, message: Message) -> None:
        print(render(message), file=self.out)

    def serve(self, bot: Bot, user: str, inp: TextIO | None = None) -> None:
        """Read commands line by line until EOF or "quit"."""
        inp = inp or sys.stdin
        print('Type a command like "list restaurants", or "quit" to exit.', file=self.out)
        for line in inp:
            line = line.strip()
            if line in ("quit", "exit"):
                break
            if line:
                self.send(bot.handle(line, user))
