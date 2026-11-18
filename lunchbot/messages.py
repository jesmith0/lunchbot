"""Platform-neutral messages. The core produces them; adapters render them."""

from dataclasses import dataclass, field
from enum import Enum


class Icon(Enum):
    """A mood for a message. Each adapter maps it to its own emoji."""

    CHEF = "chef"
    MIND_BLOWN = "mind_blown"
    THINKING = "thinking"
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    GROSS = "gross"
    DONE = "done"


@dataclass(frozen=True)
class Mention:
    """A person the message should notify, such as the day's driver.

    `ids` maps a platform name to that person's user ID there, e.g.
    {"slack": "U0123ABC"}. Platforms without an ID fall back to `name`.
    """

    name: str
    ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Action:
    """A button. Clicking it runs `command` through `Bot.handle` as the clicker."""

    label: str
    command: str
    icon: Icon | None = None


@dataclass(frozen=True)
class Message:
    parts: tuple[str | Mention, ...]
    icon: Icon | None = None
    # False: only the person who ran the command needs to see it (help, errors)
    public: bool = True
    actions: tuple[Action, ...] = ()

    @classmethod
    def of(
        cls,
        text: str,
        icon: Icon | None = None,
        public: bool = True,
        actions: tuple[Action, ...] = (),
    ) -> "Message":
        return cls((text,), icon, public, actions)

    @property
    def text(self) -> str:
        """Plain text, with mentions rendered as names."""
        return "".join(p.name if isinstance(p, Mention) else p for p in self.parts)

    @property
    def mentions(self) -> tuple[Mention, ...]:
        return tuple(p for p in self.parts if isinstance(p, Mention))
