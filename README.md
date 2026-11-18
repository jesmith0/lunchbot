<p align="center"><img src="lunchbot/static/lunchbot.png" alt="lunchbot" width="200"></p>

# lunchbot

[![CI](https://github.com/jesmith0/lunchbot/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jesmith0/lunchbot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue?logo=python&logoColor=white)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Tested with pytest](https://img.shields.io/badge/tested%20with-pytest-0A9EDC?logo=pytest&logoColor=white)
![Flask](https://img.shields.io/badge/flask-backend-000000?logo=flask&logoColor=white)
![Last commit](https://img.shields.io/github/last-commit/jesmith0/lunchbot)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A chat bot that picks where the team goes for lunch and who drives. Picks are weighted, and the team can vote restaurants up or down or veto a pick.

lunchbot was built for HipChat, which shut down in 2019. The bot logic is now platform-neutral; Slack support is in progress ([#12](https://github.com/jesmith0/lunchbot/issues/12)). Until then you can try it in your terminal with `uv run lunchbot chat`.

## Commands

Send these to the bot (`/lunchbot <command>` in chat, or just `<command>` in `lunchbot chat`):

| Command | What it does |
| --- | --- |
| `/lunchbot list restaurants` / `/lunchbot list drivers` | Show a list with its weights |
| `/lunchbot add restaurant <name>` / `/lunchbot add driver <name>` | Add an entry with weight 1 |
| `/lunchbot remove restaurant <name>` / `/lunchbot remove driver <name>` | Remove an entry |
| `/lunchbot upvote <restaurant>` | Raise a restaurant's weight by 1 (max 10) |
| `/lunchbot downvote <restaurant>` | Lower a restaurant's weight by 1 (min 1) |
| `/lunchbot gross` | Vote to veto today's pick. Three votes re-roll it. |

## Schedule

`lunchbot post-lunch` posts the day's lunch. Run it on a schedule, for example with cron.

- **Mon / Wed / Fri:** a weighted random restaurant and driver, with buttons to vote or veto. On Fridays it sometimes picks the tech talk instead.
- **Tue:** knowledge lunch. **Thu:** logic puzzle group. Nothing on weekends.

`lunchbot close-voting` closes voting and announces the final pick.

## Layout

| File | Purpose |
| --- | --- |
| `lunchbot/core.py` | Bot logic: commands, weighted picks, veto voting. Returns messages and never talks to a chat service. |
| `lunchbot/messages.py` | Platform-neutral `Message`: text, mentions, an icon and buttons |
| `lunchbot/storage.py` | Reads and writes the list files |
| `lunchbot/adapters/` | One module per chat platform, rendering messages for it. `console.py` is the terminal. |
| `lunchbot/cli.py` | The `lunchbot` command |
| `lunchbot/config.py` | Settings read from environment variables |
| `lunchbot/web.py`, `lunchbot.wsgi` | Flask app and its mod_wsgi entry point |
| `data/restaurants.txt`, `data/drivers.txt` | Lists in `NAME, WEIGHT` format |
| `data/vetos.txt` | Current veto votes, or `DISABLED` |

## Configuration

All settings come from environment variables. Copy `.env.example` to `.env`, fill it in, and run with `uv run --env-file .env ...`. Never commit `.env`: it holds chat tokens.

| Variable | Purpose |
| --- | --- |
| `LUNCHBOT_DATA_DIR` | Folder holding the list files. Defaults to `data/` in this repo. |

## History

lunchbot started in July 2016 as a side project at work. Every day the same two questions came up: where are we eating, and who's driving? [@jesmith0](https://github.com/jesmith0) wrote the first version in a day, and coworkers [@jamesrwaugh](https://github.com/jamesrwaugh) and [@masonjeffers](https://github.com/masonjeffers) helped shape it from there.

It was a humble project, but it was fun, it gave us something to build together, and it solved a problem we all actually had. Over the next few months it picked up:

- **Weighted picks and voting.** Favorite restaurants came up more often, and anyone could vote a restaurant up or down.
- **A remove command and simpler command parsing,** from @jamesrwaugh in the project's first pull requests.
- **The "gross" veto.** Three votes and lunch gets rerolled.
- **A weekly rhythm.** Tuesdays were for "knowledge", Thursdays for the logic puzzle group, and some Fridays the bot sent everyone to the tech talk instead.
- **A request for @mentions** from @masonjeffers ([#3](https://github.com/jesmith0/lunchbot/issues/3)), so the day's driver would have "no excuse not to drive me to lunch".

The bot lived in HipChat, in rooms named *The Force Awakens* and *Rogue One*, until HipChat was shut down in 2019. In 2026 the repo was dusted off: leftover merge conflicts resolved, tests and CI added, and the code moved to modern Python.

## Development

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev        # create .venv from uv.lock
uv run lunchbot chat       # talk to the bot in your terminal
uv run pytest              # tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # type check (strict)
```

To add a chat platform, write an adapter in `lunchbot/adapters/` that sends `Message`s and passes incoming command text to `Bot.handle`. The core shouldn't need to change; a test fails if it imports HTTP or chat libraries.

After changing dependencies in `pyproject.toml`, run `uv lock` and commit `uv.lock`.

On every push and pull request, CI fails if merge conflict markers are present, runs ruff lint and format checks and strict mypy, and runs the tests on Python 3.12, 3.13 and 3.14.

## License

[MIT](LICENSE)
