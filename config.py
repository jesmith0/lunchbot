"""Runtime configuration, read from environment variables.

See `.env.example` for every setting. Secrets (webhook URLs carry auth tokens)
must only ever come from the environment, never from files in the repo.
"""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    # Directory holding restaurants.txt, drivers.txt, vetos.txt, ...
    data_dir: Path = DEFAULT_DATA_DIR
    # Webhook the bot posts to when a room has no override
    webhook_url: str | None = None
    # Optional per-room webhook overrides: room name -> URL
    room_webhooks: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> "Config":
        data_dir = environ.get("LUNCHBOT_DATA_DIR")
        raw_rooms = environ.get("LUNCHBOT_ROOM_WEBHOOKS", "").strip()
        return cls(
            data_dir=Path(data_dir) if data_dir else DEFAULT_DATA_DIR,
            webhook_url=environ.get("LUNCHBOT_WEBHOOK_URL") or None,
            room_webhooks=_parse_room_webhooks(raw_rooms) if raw_rooms else {},
        )

    def webhook_for(self, room: str) -> str:
        url = self.room_webhooks.get(room) or self.webhook_url
        if not url:
            raise ConfigError(
                f"No webhook configured for room {room!r}: set LUNCHBOT_WEBHOOK_URL "
                "or add the room to LUNCHBOT_ROOM_WEBHOOKS"
            )
        return url


def _parse_room_webhooks(raw: str) -> dict[str, str]:
    try:
        rooms = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"LUNCHBOT_ROOM_WEBHOOKS is not valid JSON: {e}") from e
    if not isinstance(rooms, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in rooms.items()
    ):
        raise ConfigError('LUNCHBOT_ROOM_WEBHOOKS must be a JSON object like {"room": "url"}')
    return rooms
