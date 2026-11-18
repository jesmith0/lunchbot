from typing import Protocol

from lunchbot.messages import Message


class ChatAdapter(Protocol):
    """What the scheduled jobs need from a chat platform.

    Receiving commands is platform-specific (a slash command, a terminal prompt),
    so each adapter wires that up itself and passes the text to `Bot.handle`.
    """

    def send(self, message: Message) -> None:
        """Post a message to the adapter's announcement channel."""
        ...
