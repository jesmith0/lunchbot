"""Runtime configuration, read from environment variables.

See `.env.example` for every setting. Secrets (tokens, signing secrets) must
only ever come from the environment, never from files in the repo.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    # Directory holding restaurants.txt, drivers.txt and vetos.txt
    data_dir: Path = DEFAULT_DATA_DIR

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> "Config":
        data_dir = environ.get("LUNCHBOT_DATA_DIR")
        return cls(data_dir=Path(data_dir) if data_dir else DEFAULT_DATA_DIR)
