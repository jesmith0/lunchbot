<p align="center"><img src="static/lunchbot.png" alt="lunchbot" width="200"></p>

# lunchbot

[![CI](https://github.com/jesmith0/lunchbot/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jesmith0/lunchbot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue?logo=python&logoColor=white)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Tested with pytest](https://img.shields.io/badge/tested%20with-pytest-0A9EDC?logo=pytest&logoColor=white)
![Flask](https://img.shields.io/badge/flask-backend-000000?logo=flask&logoColor=white)
![Last commit](https://img.shields.io/github/last-commit/jesmith0/lunchbot)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A HipChat bot that picks where the team goes for lunch and who drives. Picks are weighted, and the team can vote restaurants up or down or veto a pick.

## Commands

Send these in a HipChat room with the bot installed:

| Command | What it does |
| --- | --- |
| `/lunchbot list restaurants` / `/lunchbot list drivers` | Show a list with its weights |
| `/lunchbot add restaurant <name>` / `/lunchbot add driver <name>` | Add an entry with weight 1 |
| `/lunchbot remove restaurant <name>` / `/lunchbot remove driver <name>` | Remove an entry |
| `/lunchbot upvote <restaurant>` | Raise a restaurant's weight by 1 (max 10) |
| `/lunchbot downvote <restaurant>` | Lower a restaurant's weight by 1 (min 1) |
| `/lunchbot gross` | Vote to veto today's pick. Three votes re-roll it. |

## Schedule

`python lunchbot.py` posts the day's lunch. Run it on a schedule, for example with cron.

- **Mon / Wed / Fri:** a weighted random restaurant and driver. On Fridays it sometimes picks the tech talk instead.
- **Tue:** knowledge lunch. **Thu:** logic puzzle group.

`python disable_veto.py` closes voting and announces the final pick.

## Layout

| File | Purpose |
| --- | --- |
| `lunchbot.py` | Command handling, weighted picks, HipChat posting |
| `backend.py` | Flask app that receives HipChat webhooks at `/lunchbot` |
| `lunchbot.wsgi` | mod_wsgi entry point |
| `restaurants.txt`, `drivers.txt` | Lists in `NAME, WEIGHT` format |
| `vetos.txt` | Current veto votes, or `DISABLED` |

The code reads data files from `/var/www/html/lunchbot/`. It reads the room notification URLs from the `*_URL.txt` files listed at the top of `lunchbot.py`.

## Development

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev        # create .venv from uv.lock
uv run pytest              # tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # type check (strict)
```

After changing dependencies in `pyproject.toml`, run `uv lock` and commit `uv.lock`.

On every push and pull request, CI fails if merge conflict markers are present, runs ruff lint and format checks and strict mypy, and runs the tests on Python 3.12, 3.13 and 3.14.

## License

[MIT](LICENSE)
