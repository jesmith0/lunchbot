import datetime
import logging
import random
from pathlib import Path
from typing import TypedDict

import requests

logger = logging.getLogger(__name__)

REST_PATH = "/var/www/html/lunchbot/restaurants.txt"
DRIVER_PATH = "/var/www/html/lunchbot/drivers.txt"
VETO_PATH = "/var/www/html/lunchbot/vetos.txt"
LAST_DRIVER_PATH = "/var/www/html/lunchbot/driver_last.txt"
RESTAURANT_HISTORY_SIZE = 1
LAST_REST_PATH = "/var/www/html/lunchbot/restaurant_last.txt"
SANDBOX_URL_PATH = "/var/www/html/lunchbot/SANDBOX_URL.txt"
TFA_URL_PATH = "/home/ubuntu/PRIVATE/TFA_URL.txt"
RO_URL_PATH = "/home/ubuntu/PRIVATE/RO_URL.txt"

# Command reference
# list command requires 1 argument (list name)
# add command requires 2 arguments (list name, list item)
# remove command requires 2 arguments (list name, list item)
# up/downvote command requires 2 arguments (list item, value)
# gross command requires 0 arguments


class CommandInfo(TypedDict):
    args: int
    help: str


commandinfo: dict[str, CommandInfo] = {
    "add": {"args": 2, "help": "[restaurant, driver] [name of restaurant/driver]"},
    "remove": {"args": 2, "help": "[restaurant, driver] [name of restaurant/driver]"},
    "upvote": {"args": 1, "help": "[name of restaurant/driver]"},
    "downvote": {"args": 1, "help": "[name of restaurant/driver]"},
    "list": {"args": 1, "help": "[restaurants, drivers]"},
    "gross": {"args": 0, "help": "[no arguments]"},
}


# Used to handle not enough arguments and invalid input
class InvalidCommandError(Exception):
    pass


# ---------------------------------------------------------------------------- #


### PROCESS COMMAND FROM HIPCHAT
def process_message(msg: str, user: str, room: str) -> str:
    msg_arr = msg.split(" ")
    if len(msg_arr) < 2:
        return _print_help(room)
    command = msg_arr[1]

    try:
        # Validate command and argument length
        if command not in commandinfo:
            raise InvalidCommandError
        if len(msg_arr) < commandinfo[command]["args"] + 2:
            raise InvalidCommandError

        if command == "list":
            return _print_list(msg_arr[2], room)
        elif command == "add":
            return _add_command(msg_arr[2], " ".join(msg_arr[3:]), room)
        elif command == "remove":
            return _remove_command(msg_arr[2], " ".join(msg_arr[3:]), room)
        elif command in ["upvote", "downvote"]:
            vote_value = 1 if command == "upvote" else -1
            return _vote_command(" ".join(msg_arr[2:]), vote_value, room)
        elif command == "gross":
            return _gross_command(user, room)

    except InvalidCommandError:
        pass

    return _print_help(room, command)


def _get_path(name: str) -> str:
    if name.lower() == "restaurant":
        return REST_PATH
    elif name.lower() == "driver":
        return DRIVER_PATH
    elif name.lower() == "veto":
        return VETO_PATH
    else:
        return ""


def _get_vote_enable() -> bool:
    lines = _get_lines(_get_path("veto"))
    if lines is None:
        raise OSError("could not read veto file")
    return not any("DISABLED" in line for line in lines)


def _set_vote_enable(en: bool) -> None:
    path = _get_path("veto")

    # no need to call _clear_file
    with open(path, "w") as f:
        if not en:
            f.write("DISABLED")


def _vote_command(item: str, value: int, room: str) -> str:
    msg = ""
    val = int(value)
    path = _get_path("restaurant")
    if (not path) or ((val != 1) and (val != -1)):
        raise InvalidCommandError

    if _search_for_item(path, item):
        _update_item(path, item, val)
        msg = ("(upvote) " if (val == 1) else "(downvote) ") + str(item).upper()
    else:
        msg = str(item).upper() + " does not exist in restaurants list..."

    return _post_to_hipchat(room, msg, "purple")


def _update_item(path: str, item: str, val: int) -> None:
    with open(path) as f:
        rest_list = f.readlines()

    with open(path, "w") as f:
        for rest in rest_list:
            restaurant = (rest.split(","))[0]
            if item.upper() == restaurant.upper():
                weight = int((rest.split(","))[1]) + val
                if (weight > 0) and (weight < 11):
                    f.write((restaurant + ", " + str(weight) + "\n").upper())
                    continue
            f.write(rest.upper())


# Return all lines from a file in a list, or None if it can't be read
def _get_lines(path: str) -> list[str] | None:
    try:
        with open(path) as f:
            return f.readlines()
    except Exception:
        logger.exception("Could not read file %s", path)
        return None


# Write a list of lines to a file
def _write_lines(path: str, lines: list[str]) -> None:
    try:
        with open(path, "w") as f:
            f.writelines(lines)
    except Exception:
        logger.exception("Could not write %d lines to %s", len(lines), path)


### RETURNS TRUE IF FOUND, FALSE IF NOT OR ERROR
def _search_for_item(path: str, item: str) -> bool:
    try:
        with open(path) as f:
            for line in f:
                restaurant = (line.split(","))[0]
                if item.upper() == restaurant.upper():
                    return True
    except Exception:
        logger.exception("Could not search %s for %r", path, item)
    return False


### ADD ITEM TO LIST
def _add_command(name: str, item: str, room: str) -> str:
    msg = ""
    path = _get_path(name)
    if not path:
        raise InvalidCommandError

    if not _search_for_item(path, item):
        _add_item(path, item)
        msg = str(item).upper() + " added to " + str(name).upper() + " list!"
    else:
        msg = str(item).upper() + " already exists in " + str(name).upper() + " list!"

    return _post_to_hipchat(room, msg, "purple")


def _add_item(path: str, item: str) -> None:
    try:
        with open(path, "a") as f:
            f.write((str(item) + ", 1").upper() + "\n")
    except Exception:
        logger.exception("Could not append %r to %s", item, path)


def _remove_item(path: str, item: str) -> None:
    item = item.lower().strip()
    lines = _get_lines(path)
    if lines is None:
        # never rewrite the file after a failed read; that would wipe it
        return
    kept = [line for line in lines if line.split(",")[0].strip().lower() != item]
    _write_lines(path, kept)


### REMOVE ITEM FROM LIST
def _remove_command(name: str, item: str, room: str) -> str:
    path = _get_path(name)
    if not path:
        raise InvalidCommandError

    if _search_for_item(path, item):
        _remove_item(path, item)
        msg = str(item).upper() + " removed from " + str(name).upper() + " list!"
    else:
        msg = str(item).upper() + " doesn't exists in " + str(name).upper() + " list!"

    return _post_to_hipchat(room, msg, "purple")


### ADD USER TO VETO LIST
def _gross_command(user: str, room: str) -> str:
    msg = ""
    path = _get_path("veto")

    if not _get_vote_enable():
        return _post_to_hipchat(room, "Voting disabled", "purple")

    # add user to list
    # duplicate-vote check intentionally disabled (see 1ce9aa7)
    _add_item(path, user)
    msg = "Every vote counts!"

    # check if 3 or more people in list
    if len(_get_lines(path) or []) >= 3:
        _clear_file(path)
        logger.info("3 or more votes to skip; rerolling lunch")
        return _post_lunch(room)

    return _post_to_hipchat(room, msg, "purple")


def _clear_file(path: str) -> None:
    try:
        open(path, "w").close()
    except Exception:
        logger.exception("Could not clear file %s", path)


### POSTS PROPER USAGE MESSAGE TO HIPCHAT
def _print_help(room: str, command: str | None = None) -> str:
    if command in commandinfo:
        msg = "Proper usage: /lunchbot {} {}".format(command, commandinfo[command]["help"])
    else:
        commandList = ", ".join(commandinfo.keys())
        msg = f"Proper usage: /lunchbot [command ({commandList})] [option 1] [option 2] ..."
    return _post_to_hipchat(room, msg, "gray")


### POSTS LIST TO HIPCHAT
def _print_list(name: str, room: str) -> str:
    msg = _get_list_msg(name)
    return _post_to_hipchat(room, msg, "gray")


### RETURNS LIST AS A MESSAGE FORMATTED FOR HIPCHAT
def _get_list_msg(name: str) -> str:
    if name.lower() == "restaurants":
        header, path = "RESTAURANTS, WEIGHT\n", REST_PATH
    elif name.lower() == "drivers":
        header, path = "DRIVERS, WEIGHT\n", DRIVER_PATH
    else:
        raise InvalidCommandError

    with open(path) as f:
        return header + f.read()


### RETURNS A RANDOM ITEM FROM A LIST
def _get_random_item(path: str, last_item_file: str | None = None) -> str:
    candidates = []
    with open(path) as source:
        for line in source:
            restaurant, weight = line.split(",")[:2]
            candidates.extend([restaurant.strip().upper()] * int(weight))

    history = []
    if last_item_file is not None and RESTAURANT_HISTORY_SIZE > 0:
        history_path = Path(last_item_file)
        try:
            history = [
                name.strip().upper()
                for name in history_path.read_text().splitlines()
                if name.strip()
            ][-RESTAURANT_HISTORY_SIZE:]
        except FileNotFoundError:
            pass

        recent = set(history)
        eligible = [item for item in candidates if item not in recent]
        choice = random.choice(eligible or candidates)
        history_path.write_text("\n".join((history + [choice])[-RESTAURANT_HISTORY_SIZE:]) + "\n")
        return choice

    return random.choice(candidates)


### POSTS MESSAGE TO HIPCHAT
def _post_to_hipchat(
    room: str,
    message: str,
    color: str = "green",
    notify: bool = False,
    message_format: str = "text",
) -> str:
    room_paths = {
        "The Force Awakens": TFA_URL_PATH,
        "sandy lunchbox": SANDBOX_URL_PATH,
        "Rogue One": RO_URL_PATH,
    }
    url_path = room_paths.get(room, RO_URL_PATH)
    lines = _get_lines(url_path)
    if not lines:
        raise OSError(f"no HipChat URL configured in {url_path}")
    url = lines[0].rstrip()

    requests.post(
        url,
        json={
            "color": color,
            "message": message,
            "notify": notify,
            "message_format": message_format,
        },
    )

    return message


### POSTS LUNCH RECOMMENDATION
def _post_lunch(
    room: str, day: int | None = None, rest: str | None = None, driver: str | None = None
) -> str:
    # defaults are resolved per call; as default args they were evaluated once at import
    if day is None:
        day = datetime.datetime.today().weekday()
    if rest is None:
        rest = _get_random_item(REST_PATH, LAST_REST_PATH)
    if driver is None:
        driver = _get_random_item(DRIVER_PATH)
    msg = ""

    # monday, wednesday, friday
    if day in [0, 2, 4]:
        if day == 4 and random.random() > 0.4:
            msg = (
                "(chef) Hello there children! Today we're going to the TECH TALK and "
                + driver
                + " is driving! (sourcetree)"
            )
        else:
            msg = (
                "(chef) Hello there children! Today we're going on a field trip to "
                + rest
                + " and "
                + driver
                + " is driving!"
            )
        _set_vote_enable(True)

    elif day == 1:  # tuesday
        msg = "Today for lunch is KNOWLEDGE (mindblown)"

    elif day == 3:  # thursday
        msg = "Today we're having food for thought at the LOGIC PUZZLE GROUP (philosoraptor)"

    # make post request
    return _post_to_hipchat(room, msg, "green", True, "text")


### POSTS LUNCH SUGGESTION TO HIPCHAT
def main(room: str) -> None:
    _post_lunch(room)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main("Rogue One")
