import ast
import datetime
from pathlib import Path

import pytest

import lunchbot
from lunchbot.core import COMMANDS, FRIDAY, MONDAY, THURSDAY, TUESDAY, Bot
from lunchbot.messages import Icon, Mention
from tests.conftest import FixedRandom

PACKAGE = Path(lunchbot.__file__).parent


def read(data_dir, name):
    return (data_dir / name).read_text()


def test_add_restaurant(bot, data_dir):
    msg = bot.handle("add restaurant holy hog", "u")
    assert msg.text == "HOLY HOG added to RESTAURANT list!"
    assert "HOLY HOG, 1\n" in read(data_dir, "restaurants.txt")


def test_leading_slash_command_is_optional(bot):
    assert bot.handle("/lunchbot list drivers", "u").text == bot.handle("list drivers", "u").text


def test_add_existing_restaurant(bot, data_dir):
    msg = bot.handle("add restaurant chipotle", "u")
    assert msg.text == "CHIPOTLE already exists in RESTAURANT list!"
    assert read(data_dir, "restaurants.txt").count("CHIPOTLE") == 1


def test_add_driver_accepts_plural_list_name(bot, data_dir):
    assert bot.handle("add drivers mason", "u").text == "MASON added to DRIVER list!"
    assert "MASON, 1\n" in read(data_dir, "drivers.txt")


def test_remove_restaurant(bot, data_dir):
    msg = bot.handle("remove restaurant evos", "u")
    assert msg.text == "EVOS removed from RESTAURANT list!"
    assert "EVOS" not in read(data_dir, "restaurants.txt")


def test_remove_missing_restaurant(bot):
    assert bot.handle("remove restaurant nowhere", "u").text == (
        "NOWHERE doesn't exist in RESTAURANT list!"
    )


def test_remove_does_not_delete_items_sharing_a_prefix(bot, data_dir):
    # Regression for #20: removing EVOS used to also delete EVOS GRILL.
    with open(data_dir / "restaurants.txt", "a") as f:
        f.write("EVOS GRILL, 3\n")
    bot.handle("remove restaurant evos", "u")
    assert read(data_dir, "restaurants.txt") == "CHIPOTLE, 5\nEVOS GRILL, 3\n"


def test_upvote_and_downvote(bot, data_dir):
    msg = bot.handle("upvote chipotle", "u")
    assert (msg.text, msg.icon) == ("CHIPOTLE upvoted (weight 6)", Icon.UPVOTE)
    assert "CHIPOTLE, 6" in read(data_dir, "restaurants.txt")
    msg = bot.handle("downvote chipotle", "u")
    assert (msg.text, msg.icon) == ("CHIPOTLE downvoted (weight 5)", Icon.DOWNVOTE)
    assert "CHIPOTLE, 5" in read(data_dir, "restaurants.txt")


def test_downvote_does_not_go_below_one(bot, data_dir):
    msg = bot.handle("downvote evos", "u")
    assert msg.text == "EVOS is already at the minimum weight (1)"
    assert "EVOS, 1" in read(data_dir, "restaurants.txt")


def test_upvote_does_not_go_above_ten(bot, data_dir):
    (data_dir / "restaurants.txt").write_text("PITA PIT, 10\n")
    assert (
        bot.handle("upvote pita pit", "u").text == "PITA PIT is already at the maximum weight (10)"
    )
    assert read(data_dir, "restaurants.txt") == "PITA PIT, 10\n"


def test_vote_unknown_restaurant(bot):
    assert bot.handle("upvote nowhere", "u").text == "NOWHERE does not exist in restaurants list..."


def test_vote_matches_names_with_stray_whitespace(bot, data_dir):
    # data/restaurants.txt shipped with "THE PUB , 2", which could never be voted on.
    (data_dir / "restaurants.txt").write_text("THE PUB , 2\n")
    bot.handle("upvote the pub", "u")
    assert read(data_dir, "restaurants.txt") == "THE PUB, 3\n"


def test_list_restaurants(bot):
    msg = bot.handle("list restaurants", "u")
    assert msg.text == "RESTAURANTS, WEIGHT\nCHIPOTLE, 5\nEVOS, 1\n"
    assert msg.public


def test_list_empty(bot, data_dir):
    (data_dir / "drivers.txt").write_text("")
    assert bot.handle("list drivers", "u").text.startswith("No drivers yet.")


@pytest.mark.parametrize("text", ["", "/lunchbot", "dance", "(upvote) chipotle"])
def test_unknown_or_missing_command_prints_general_help(bot, text, data_dir):
    # "/lunchbot" alone used to raise IndexError (#21); "(upvote)" was dead code (#22).
    msg = bot.handle(text, "u")
    assert msg.text.startswith("Proper usage: /lunchbot [command (")
    assert not msg.public
    assert "CHIPOTLE, 5" in read(data_dir, "restaurants.txt")


@pytest.mark.parametrize("text", ["add", "add restaurant", "list", "list tacos", "add pizza x"])
def test_bad_arguments_print_command_help(bot, text):
    command = text.split()[0]
    msg = bot.handle(text, "u")
    assert msg.text == f"Proper usage: /lunchbot {command} {COMMANDS[command].usage}"


def test_gross_disabled(bot, data_dir):
    (data_dir / "vetos.txt").write_text("DISABLED\n")
    msg = bot.handle("gross", "a")
    assert (msg.text, msg.public) == ("Voting disabled", False)


def test_gross_three_votes_rerolls_lunch(store, data_dir):
    bot = Bot(store, rng=FixedRandom(), today=lambda: datetime.date(2026, 11, 16))  # Monday
    assert bot.handle("gross", "a").text == "Every vote counts! (1 of 3 to reroll)"
    assert bot.handle("gross", "b").text == "Every vote counts! (2 of 3 to reroll)"
    third = bot.handle("gross", "c")
    assert "field trip to" in third.text
    assert read(data_dir, "vetos.txt") == ""  # votes reset for the new pick


def test_pick_respects_weights(bot, data_dir):
    (data_dir / "restaurants.txt").write_text("ONLY ONE, 3\nNEVER, 0\n")
    for _ in range(20):
        assert bot.pick("restaurants").name == "ONLY ONE"


def test_pick_from_empty_list(bot, data_dir):
    (data_dir / "restaurants.txt").write_text("")
    assert bot.pick("restaurants") is None
    assert "No restaurants to pick from" in bot.daily_pick(MONDAY).text


@pytest.mark.parametrize(
    "day, expected, icon",
    [
        (TUESDAY, "Today for lunch is KNOWLEDGE", Icon.MIND_BLOWN),
        (THURSDAY, "Today we're having food for thought at the LOGIC PUZZLE GROUP", Icon.THINKING),
    ],
)
def test_daily_pick_theme_days(bot, day, expected, icon):
    msg = bot.daily_pick(day)
    assert (msg.text, msg.icon, msg.actions) == (expected, icon, ())


def test_daily_pick_mentions_driver_and_offers_votes(bot, data_dir):
    (data_dir / "restaurants.txt").write_text("TACO BUS, 1\n")
    (data_dir / "vetos.txt").write_text("DISABLED\n")
    msg = bot.daily_pick(MONDAY)
    assert msg.text == (
        "Hello there children! Today we're going on a field trip to TACO BUS and JEREMY is driving!"
    )
    assert msg.mentions == (Mention("JEREMY"),)
    assert msg.icon is Icon.CHEF
    assert [a.command for a in msg.actions] == ["upvote TACO BUS", "downvote TACO BUS", "gross"]
    assert read(data_dir, "vetos.txt") == ""  # voting opened


def test_daily_pick_mention_carries_platform_ids(bot, data_dir):
    (data_dir / "drivers.txt").write_text("JEREMY, 1, slack:U0123ABC\n")
    assert bot.daily_pick(MONDAY).mentions == (Mention("JEREMY", {"slack": "U0123ABC"}),)


def test_friday_can_be_tech_talk(store):
    bot = Bot(store, rng=FixedRandom(0.0))
    msg = bot.daily_pick(FRIDAY)
    assert "TECH TALK" in msg.text
    assert [a.command for a in msg.actions] == ["gross"]


@pytest.mark.parametrize("day", [5, 6])
def test_no_lunch_on_weekends(bot, day):
    # The original bot posted an empty message on weekends.
    assert bot.daily_pick(day) is None
    assert bot.close_voting(day) is None


def test_daily_pick_defaults_to_today(store):
    bot = Bot(store, today=lambda: datetime.date(2026, 11, 17))  # Tuesday
    assert "KNOWLEDGE" in bot.daily_pick().text


def test_daily_pick_reads_current_lists(bot, data_dir):
    # The old default arguments picked once at import; every call must read the files.
    (data_dir / "restaurants.txt").write_text("NEW SPOT, 1\n")
    assert "NEW SPOT" in bot.daily_pick(MONDAY).text


def test_close_voting(bot, data_dir):
    assert bot.close_voting(MONDAY).text == "It has been decided! Go forth and lunch.."
    assert bot.handle("gross", "a").text == "Voting disabled"
    assert bot.close_voting(TUESDAY) is None


@pytest.mark.parametrize("module", ["core.py", "storage.py", "messages.py"])
def test_core_has_no_chat_or_http_imports(module):
    # #9: the core must stay platform-neutral so adapters can be added without touching it.
    banned = {"requests", "http", "urllib", "flask", "slack_bolt", "slack_sdk", "lunchbot.adapters"}
    tree = ast.parse((PACKAGE / module).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert not any(name == b or name.startswith(b + ".") for b in banned), name
