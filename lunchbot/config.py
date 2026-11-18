"""Runtime configuration, read from environment variables.

See `.env.example` for every setting. Secrets (tokens, signing secrets) must
only ever come from the environment, never from files in the repo.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

Platform = Literal["console", "slack"]
PLATFORMS: tuple[Platform, ...] = ("console", "slack")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class SlackConfig:
    # xoxb-... token: posts messages and looks up users
    bot_token: str | None = None
    # Verifies that HTTP requests really come from Slack (HTTP mode)
    signing_secret: str | None = None
    # xapp-... token with connections:write (Socket Mode)
    app_token: str | None = None
    # Channel ID the daily lunch is posted to, e.g. C0123ABC
    channel: str | None = None

    def require(self, *names: str) -> None:
        """Raise ConfigError naming every missing setting. Never includes values."""
        missing = [ENV_NAMES[n] for n in names if not getattr(self, n)]
        if missing:
            raise ConfigError("Slack needs these environment variables: " + ", ".join(missing))


ENV_NAMES = {
    "bot_token": "SLACK_BOT_TOKEN",
    "signing_secret": "SLACK_SIGNING_SECRET",
    "app_token": "SLACK_APP_TOKEN",
    "channel": "LUNCHBOT_SLACK_CHANNEL",
}


@dataclass(frozen=True)
class Config:
    # Directory holding restaurants.txt, drivers.txt and vetos.txt
    data_dir: Path = DEFAULT_DATA_DIR
    # Where `lunchbot post-lunch` and `close-voting` post
    platform: Platform = "console"
    slack: SlackConfig = field(default_factory=SlackConfig)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> "Config":
        data_dir = environ.get("LUNCHBOT_DATA_DIR")
        platform = environ.get("LUNCHBOT_PLATFORM") or "console"
        if platform not in PLATFORMS:
            raise ConfigError(f"LUNCHBOT_PLATFORM must be one of: {', '.join(PLATFORMS)}")
        slack = SlackConfig(**{k: environ.get(v) or None for k, v in ENV_NAMES.items()})
        return cls(
            data_dir=Path(data_dir) if data_dir else DEFAULT_DATA_DIR,
            platform=platform,
            slack=slack,
        )
