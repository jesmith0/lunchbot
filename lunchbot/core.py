"""Bot logic: commands, weighted picks and veto voting.

Nothing here talks to a chat service. Every entry point returns a `Message`
(or None), and the caller's adapter decides how to deliver it.
"""

import datetime
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import get_args

from lunchbot.messages import Action, Icon, Mention, Message
from lunchbot.storage import Entry, ListName, Store, normalize

logger = logging.getLogger(__name__)

MIN_WEIGHT = 1
MAX_WEIGHT = 10
VETOES_TO_REROLL = 3
# Chance that a Friday lunch is replaced by the tech talk
TECH_TALK_CHANCE = 0.6

MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY = range(5)
PICK_DAYS = (MONDAY, WEDNESDAY, FRIDAY)


@dataclass(frozen=True)
class Command:
    args: int  # minimum number of arguments
    usage: str


COMMANDS: dict[str, Command] = {
    "add": Command(2, "[restaurant, driver] [name]"),
    "remove": Command(2, "[restaurant, driver] [name]"),
    "upvote": Command(1, "[restaurant]"),
    "downvote": Command(1, "[restaurant]"),
    "list": Command(1, "[restaurants, drivers]"),
    "gross": Command(0, "[no arguments]"),
}


class UsageError(Exception):
    """The command was malformed; the user gets the usage text."""


def _list_name(word: str) -> ListName:
    """Accept singular or plural: "restaurant" and "restaurants" both work."""
    word = word.lower()
    plural = word if word.endswith("s") else word + "s"
    if plural not in get_args(ListName):
        raise UsageError
    return plural  # type: ignore[return-value]  # checked against ListName above


def _singular(list_name: ListName) -> str:
    return list_name.removesuffix("s").upper()


class Bot:
    def __init__(
        self,
        store: Store,
        rng: random.Random | None = None,
        today: Callable[[], datetime.date] | None = None,
    ) -> None:
        self.store = store
        self.rng = rng or random.Random()
        self._today = today

    def today(self) -> datetime.date:
        return self._today() if self._today else datetime.date.today()

    # -- commands ------------------------------------------------------------

    def handle(self, text: str, user: str) -> Message:
        """Run one command, e.g. "add restaurant holy hog", sent by `user`."""
        words = text.split()
        if words and words[0].lower() == "/lunchbot":
            words = words[1:]
        if not words:
            return self.usage()

        command, args = words[0].lower(), words[1:]
        spec = COMMANDS.get(command)
        if spec is None or len(args) < spec.args:
            return self.usage(command)
        try:
            if command == "list":
                return self._list(_list_name(args[0]))
            if command == "add":
                return self._add(_list_name(args[0]), " ".join(args[1:]))
            if command == "remove":
                return self._remove(_list_name(args[0]), " ".join(args[1:]))
            if command in ("upvote", "downvote"):
                return self._vote(" ".join(args), 1 if command == "upvote" else -1)
            assert command == "gross"
            return self._gross(user)
        except UsageError:
            return self.usage(command)

    def usage(self, command: str | None = None) -> Message:
        spec = COMMANDS.get(command or "")
        if spec is not None:
            text = f"Proper usage: /lunchbot {command} {spec.usage}"
        else:
            names = ", ".join(COMMANDS)
            text = f"Proper usage: /lunchbot [command ({names})] [option 1] [option 2] ..."
        return Message.of(text, public=False)

    def _list(self, list_name: ListName) -> Message:
        entries = self.store.entries(list_name)
        if not entries:
            return Message.of(
                f"No {list_name} yet. Add one with /lunchbot add {_singular(list_name).lower()} "
                "<name>"
            )
        lines = "".join(f"{e.name}, {e.weight}\n" for e in entries)
        return Message.of(f"{list_name.upper()}, WEIGHT\n{lines}")

    def _add(self, list_name: ListName, name: str) -> Message:
        entry = Entry(normalize(name))
        if self.store.add(list_name, entry):
            return Message.of(f"{entry.name} added to {_singular(list_name)} list!")
        return Message.of(f"{entry.name} already exists in {_singular(list_name)} list!")

    def _remove(self, list_name: ListName, name: str) -> Message:
        name = normalize(name)
        if self.store.remove(list_name, name):
            return Message.of(f"{name} removed from {_singular(list_name)} list!")
        return Message.of(f"{name} doesn't exist in {_singular(list_name)} list!")

    def _vote(self, name: str, delta: int) -> Message:
        entry = self.store.find("restaurants", name)
        if entry is None:
            return Message.of(f"{normalize(name)} does not exist in restaurants list...")

        icon = Icon.UPVOTE if delta > 0 else Icon.DOWNVOTE
        weight = entry.weight + delta
        if not MIN_WEIGHT <= weight <= MAX_WEIGHT:
            bound = "maximum" if delta > 0 else "minimum"
            return Message.of(f"{entry.name} is already at the {bound} weight ({entry.weight})")

        self.store.update("restaurants", entry.with_weight(weight))
        verb = "upvoted" if delta > 0 else "downvoted"
        return Message.of(f"{entry.name} {verb} (weight {weight})", icon=icon)

    def _gross(self, user: str) -> Message:
        if not self.store.voting_enabled():
            return Message.of("Voting disabled", public=False)

        # Users may vote more than once: the duplicate-vote check was disabled on purpose
        # in the original bot (see 1ce9aa7).
        votes = self.store.add_veto(user)
        if votes < VETOES_TO_REROLL:
            return Message.of(
                f"Every vote counts! ({votes} of {VETOES_TO_REROLL} to reroll)", icon=Icon.GROSS
            )

        logger.info("%d votes to skip; rerolling lunch", votes)
        return self.daily_pick() or Message.of("Lunch vetoed!", icon=Icon.GROSS)

    # -- scheduled -----------------------------------------------------------

    def daily_pick(self, day: int | None = None) -> Message | None:
        """Today's lunch announcement, or None on weekends.

        Mon/Wed/Fri pick a weighted restaurant and driver and open veto voting;
        Tuesday is knowledge lunch and Thursday is the logic puzzle group.
        """
        if day is None:
            day = self.today().weekday()

        if day == TUESDAY:
            return Message.of("Today for lunch is KNOWLEDGE", icon=Icon.MIND_BLOWN)
        if day == THURSDAY:
            return Message.of(
                "Today we're having food for thought at the LOGIC PUZZLE GROUP",
                icon=Icon.THINKING,
            )
        if day not in PICK_DAYS:
            return None

        restaurant = self.pick("restaurants")
        driver = self.pick("drivers")
        if restaurant is None or driver is None:
            missing = "restaurant" if restaurant is None else "driver"
            return Message.of(
                f"No {missing}s to pick from! Add one with /lunchbot add {missing} <name>"
            )

        self.store.set_voting(True)
        driving = Mention(driver.name, driver.ids)
        gross = Action("Gross", "gross", Icon.GROSS)
        if day == FRIDAY and self.rng.random() < TECH_TALK_CHANCE:
            return Message(
                ("Hello there children! Today we're going to the TECH TALK and ", driving,
                 " is driving!"),
                icon=Icon.CHEF,
                actions=(gross,),
            )  # fmt: skip
        return Message(
            ("Hello there children! Today we're going on a field trip to ", restaurant.name,
             " and ", driving, " is driving!"),
            icon=Icon.CHEF,
            actions=(
                Action("Upvote", f"upvote {restaurant.name}", Icon.UPVOTE),
                Action("Downvote", f"downvote {restaurant.name}", Icon.DOWNVOTE),
                gross,
            ),
        )  # fmt: skip

    def close_voting(self, day: int | None = None) -> Message | None:
        """Close veto voting on pick days and announce that lunch is final."""
        if day is None:
            day = self.today().weekday()
        if day not in PICK_DAYS:
            return None
        self.store.set_voting(False)
        return Message.of("It has been decided! Go forth and lunch..", icon=Icon.DONE)

    def pick(self, list_name: ListName) -> Entry | None:
        """A weighted random entry. Entries with weight 0 or less are never picked."""
        entries = [e for e in self.store.entries(list_name) if e.weight > 0]
        if not entries:
            return None
        return self.rng.choices(entries, weights=[e.weight for e in entries])[0]
