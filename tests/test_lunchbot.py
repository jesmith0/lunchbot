import os

import pytest

import lunchbot
from config import Config

get_random_item = lunchbot._get_random_item
post_lunch = lunchbot._post_lunch
post_to_hipchat = lunchbot._post_to_hipchat

DEFAULT_URL = "https://example.test/default"
ROOM_URLS = {
    "The Force Awakens": "https://example.test/tfa",
    "sandy lunchbox": "https://example.test/sandbox",
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point every data path at a temp dir and capture outgoing HipChat posts."""
    files = {
        "REST_PATH": "CHIPOTLE, 5\nEVOS, 1\n",
        "DRIVER_PATH": "JEREMY, 1\n",
        "VETO_PATH": "",
        "LAST_DRIVER_PATH": "",
        "LAST_REST_PATH": "",
    }
    for const, content in files.items():
        p = tmp_path / const.lower()
        p.write_text(content)
        monkeypatch.setattr(lunchbot, const, str(p))
    config = Config(data_dir=tmp_path, webhook_url=DEFAULT_URL, room_webhooks=ROOM_URLS)
    monkeypatch.setattr(lunchbot, "CONFIG", config)

    posts = []
    monkeypatch.setattr(lunchbot.requests, "post", lambda url, json: posts.append((url, json)))

    class Env:
        pass

    e = Env()
    e.posts = posts
    e.read = lambda const: open(getattr(lunchbot, const)).read()
    return e


def test_no_merge_conflict_markers():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in os.listdir(root):
        if name.endswith(".py"):
            with open(os.path.join(root, name)) as f:
                for line in f:
                    assert not line.startswith(("<<<<<<< ", ">>>>>>> ")), name


def test_add_restaurant(env):
    msg = lunchbot.process_message("/lunchbot add restaurant holy hog", "u", "Rogue One")
    assert msg == "HOLY HOG added to RESTAURANT list!"
    assert "HOLY HOG, 1\n" in env.read("REST_PATH")


def test_add_existing_restaurant(env):
    msg = lunchbot.process_message("/lunchbot add restaurant chipotle", "u", "Rogue One")
    assert msg == "CHIPOTLE already exists in RESTAURANT list!"
    assert env.read("REST_PATH").count("CHIPOTLE") == 1


def test_remove_restaurant(env):
    msg = lunchbot.process_message("/lunchbot remove restaurant evos", "u", "Rogue One")
    assert msg == "EVOS removed from RESTAURANT list!"
    assert "EVOS" not in env.read("REST_PATH")


def test_upvote_and_downvote(env):
    lunchbot.process_message("/lunchbot upvote chipotle", "u", "Rogue One")
    assert "CHIPOTLE, 6" in env.read("REST_PATH")
    lunchbot.process_message("/lunchbot downvote chipotle", "u", "Rogue One")
    assert "CHIPOTLE, 5" in env.read("REST_PATH")


def test_downvote_does_not_go_below_one(env):
    lunchbot.process_message("/lunchbot downvote evos", "u", "Rogue One")
    assert "EVOS, 1" in env.read("REST_PATH")


def test_vote_unknown_restaurant(env):
    msg = lunchbot.process_message("/lunchbot upvote nowhere", "u", "Rogue One")
    assert msg == "NOWHERE does not exist in restaurants list..."


def test_list_restaurants(env):
    msg = lunchbot.process_message("/lunchbot list restaurants", "u", "Rogue One")
    assert msg.startswith("RESTAURANTS, WEIGHT\n")
    assert "CHIPOTLE, 5" in msg


def test_unknown_command_prints_help(env):
    msg = lunchbot.process_message("/lunchbot dance", "u", "Rogue One")
    assert msg.startswith("Proper usage: /lunchbot [command (")


def test_missing_args_prints_command_help(env):
    msg = lunchbot.process_message("/lunchbot add", "u", "Rogue One")
    assert msg == "Proper usage: /lunchbot add " + lunchbot.commandinfo["add"]["help"]


def test_gross_disabled(env):
    with open(lunchbot.VETO_PATH, "w") as f:
        f.write("DISABLED")
    assert lunchbot.process_message("/lunchbot gross", "a", "Rogue One") == "Voting disabled"


def test_gross_three_votes_rerolls_lunch(env):
    assert lunchbot.process_message("/lunchbot gross", "a", "Rogue One") == "Every vote counts!"
    assert lunchbot.process_message("/lunchbot gross", "b", "Rogue One") == "Every vote counts!"
    third = lunchbot.process_message("/lunchbot gross", "c", "Rogue One")
    assert third != "Every vote counts!"  # third vote posts a new lunch instead
    assert env.read("VETO_PATH") in ("", "DISABLED")


def test_random_item_respects_weights(env):
    with open(lunchbot.REST_PATH, "w") as f:
        f.write("ONLY ONE, 3\nNEVER, 0\n")
    for _ in range(20):
        assert get_random_item(lunchbot.REST_PATH) == "ONLY ONE"


@pytest.mark.parametrize(
    "day, expected",
    [(1, "KNOWLEDGE"), (3, "LOGIC PUZZLE GROUP"), (0, "field trip to TACO PLACE")],
)
def test_post_lunch_by_weekday(env, day, expected):
    msg = post_lunch("Rogue One", day=day, rest="TACO PLACE", driver="JEREMY")
    assert expected in msg


def test_post_lunch_picks_fresh_restaurant_each_call(env):
    # Defaults used to be evaluated once at import; they must now read the current files.
    with open(lunchbot.REST_PATH, "w") as f:
        f.write("NEW SPOT, 1\n")
    msg = post_lunch("Rogue One", day=0)
    assert "NEW SPOT" in msg or "TECH TALK" in msg


@pytest.mark.parametrize(
    "room, url",
    [
        ("The Force Awakens", ROOM_URLS["The Force Awakens"]),
        ("sandy lunchbox", ROOM_URLS["sandy lunchbox"]),
        ("Rogue One", DEFAULT_URL),
        ("Some Other Room", DEFAULT_URL),
    ],
)
def test_post_to_hipchat_routes_by_room(env, room, url):
    post_to_hipchat(room, "hi", "gray")
    assert env.posts == [
        (url, {"color": "gray", "message": "hi", "notify": False, "message_format": "text"})
    ]


def test_remove_does_not_delete_items_sharing_a_prefix(env):
    # Regression for #20: removing EVOS used to also delete EVOS GRILL.
    with open(lunchbot.REST_PATH, "a") as f:
        f.write("EVOS GRILL, 3\n")
    lunchbot.process_message("/lunchbot remove restaurant evos", "u", "Rogue One")
    contents = env.read("REST_PATH")
    assert "EVOS GRILL, 3" in contents
    assert "EVOS, 1" not in contents
    assert "CHIPOTLE, 5" in contents


def test_bare_command_prints_general_help(env):
    # Regression for #21: "/lunchbot" alone used to raise IndexError (HTTP 500).
    msg = lunchbot.process_message("/lunchbot", "u", "Rogue One")
    assert msg.startswith("Proper usage: /lunchbot [command (")


@pytest.mark.parametrize("command", ["(upvote)", "(downvote)"])
def test_emoticon_vote_aliases_print_help(env, command):
    # #22: these aliases were never reachable; they get the general help text.
    msg = lunchbot.process_message(f"/lunchbot {command} chipotle", "u", "Rogue One")
    assert msg.startswith("Proper usage: /lunchbot [command (")
    assert "CHIPOTLE, 5" in env.read("REST_PATH")


def test_remove_after_failed_read_keeps_file(env, monkeypatch):
    # A failed read must never lead to rewriting (and wiping) the list.
    monkeypatch.setattr(lunchbot, "_get_lines", lambda path: None)
    lunchbot._remove_item(lunchbot.REST_PATH, "chipotle")
    assert env.read("REST_PATH") == "CHIPOTLE, 5\nEVOS, 1\n"


def test_file_errors_are_logged(env, caplog):
    assert lunchbot._get_lines("/nonexistent/lunchbot.txt") is None
    assert "Could not read file /nonexistent/lunchbot.txt" in caplog.text
    assert "FileNotFoundError" in caplog.text


def test_post_without_webhook_configured_raises(env, monkeypatch):
    from config import ConfigError

    monkeypatch.setattr(lunchbot, "CONFIG", Config())
    with pytest.raises(ConfigError, match="LUNCHBOT_WEBHOOK_URL"):
        post_to_hipchat("Rogue One", "hi")
    assert env.posts == []


def test_bundled_data_files_parse():
    # The seed lists shipped in data/ must load with the default config.
    defaults = Config()
    assert get_random_item(str(defaults.data_dir / "restaurants.txt"))
    assert get_random_item(str(defaults.data_dir / "drivers.txt"))
