import io

from lunchbot.adapters.base import ChatAdapter
from lunchbot.adapters.console import ConsoleAdapter, render
from lunchbot.core import MONDAY
from lunchbot.messages import Message


class FakeAdapter:
    """The smallest possible adapter: records what it was asked to send."""

    def __init__(self) -> None:
        self.sent: list[Message] = []

    def send(self, message: Message) -> None:
        self.sent.append(message)


def test_fake_adapter_receives_core_messages(bot):
    adapter: ChatAdapter = FakeAdapter()
    adapter.send(bot.daily_pick(MONDAY))
    adapter.send(bot.close_voting(MONDAY))
    assert [m.icon.value for m in adapter.sent] == ["chef", "done"]


def test_console_renders_icons_mentions_and_buttons(bot, data_dir):
    (data_dir / "restaurants.txt").write_text("TACO BUS, 1\n")
    assert render(bot.daily_pick(MONDAY)) == (
        "🧑‍🍳 Hello there children! Today we're going on a field trip to TACO BUS and "
        "@JEREMY is driving!\n"
        "[👍 Upvote: upvote TACO BUS]  [👎 Downvote: downvote TACO BUS]  [🤢 Gross: gross]"
    )


def test_console_plain_message():
    assert render(Message.of("RESTAURANTS, WEIGHT\nEVOS, 1\n")) == "RESTAURANTS, WEIGHT\nEVOS, 1"


def test_console_session(bot):
    out = io.StringIO()
    ConsoleAdapter(out).serve(bot, "alice", io.StringIO("add driver mason\n\nlist drivers\nquit\n"))
    assert out.getvalue().splitlines()[1:] == [
        "MASON added to DRIVER list!",
        "DRIVERS, WEIGHT",
        "JEREMY, 1",
        "MASON, 1",
    ]
