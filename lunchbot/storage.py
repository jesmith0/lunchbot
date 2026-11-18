"""Flat-file storage for the restaurant and driver lists and the veto votes.

List files hold one entry per line: `NAME, WEIGHT[, platform:user_id ...]`.
Names are stored uppercase. Extra `platform:user_id` fields (e.g. `slack:U0123`)
let adapters mention a driver; they are kept as-is when the file is rewritten.
"""

import logging
import os
import shutil
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

ListName = Literal["restaurants", "drivers"]

LIST_FILES: dict[ListName, str] = {"restaurants": "restaurants.txt", "drivers": "drivers.txt"}
VETO_FILE = "vetos.txt"
VOTING_DISABLED = "DISABLED"


def normalize(name: str) -> str:
    return " ".join(name.split()).upper()


@dataclass(frozen=True)
class Entry:
    name: str
    weight: int = 1
    ids: dict[str, str] = field(default_factory=dict)

    def with_weight(self, weight: int) -> "Entry":
        return replace(self, weight=weight)

    def to_line(self) -> str:
        fields = [self.name, str(self.weight), *(f"{p}:{i}" for p, i in self.ids.items())]
        return ", ".join(fields) + "\n"

    @classmethod
    def parse(cls, line: str) -> "Entry | None":
        """Parse one line, or return None for a blank line. Raises ValueError if malformed."""
        fields = [f.strip() for f in line.split(",")]
        if not fields[0]:
            return None
        weight = int(fields[1]) if len(fields) > 1 and fields[1] else 1
        ids = {}
        for extra in fields[2:]:
            platform, sep, user_id = extra.partition(":")
            if not sep or not platform or not user_id:
                raise ValueError(f"expected platform:user_id, got {extra!r}")
            ids[platform] = user_id
        return cls(normalize(fields[0]), weight, ids)


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    # -- lists ---------------------------------------------------------------

    def entries(self, list_name: ListName) -> list[Entry]:
        path = self._path(LIST_FILES[list_name])
        entries = []
        for lineno, line in enumerate(self._read_lines(path), 1):
            try:
                entry = Entry.parse(line)
            except ValueError as e:
                logger.warning("Skipping malformed line %s:%d: %s", path, lineno, e)
                continue
            if entry is not None:
                entries.append(entry)
        return entries

    def find(self, list_name: ListName, name: str) -> Entry | None:
        name = normalize(name)
        return next((e for e in self.entries(list_name) if e.name == name), None)

    def add(self, list_name: ListName, entry: Entry) -> bool:
        """Add an entry. Returns False if one with that name already exists."""
        entries = self.entries(list_name)
        if any(e.name == entry.name for e in entries):
            return False
        self._save(list_name, [*entries, entry])
        return True

    def remove(self, list_name: ListName, name: str) -> bool:
        """Remove the entry with exactly this name. Returns False if there was none."""
        name = normalize(name)
        entries = self.entries(list_name)
        kept = [e for e in entries if e.name != name]
        if len(kept) == len(entries):
            return False
        self._save(list_name, kept)
        return True

    def update(self, list_name: ListName, entry: Entry) -> None:
        """Replace the entry with the same name."""
        entries = [entry if e.name == entry.name else e for e in self.entries(list_name)]
        self._save(list_name, entries)

    def _save(self, list_name: ListName, entries: list[Entry]) -> None:
        self._write(self._path(LIST_FILES[list_name]), "".join(e.to_line() for e in entries))

    # -- vetoes --------------------------------------------------------------

    def voting_enabled(self) -> bool:
        return VOTING_DISABLED not in self._veto_lines()

    def set_voting(self, enabled: bool) -> None:
        """Enable (and clear the vetoes) or disable voting."""
        self._write(self._path(VETO_FILE), "" if enabled else VOTING_DISABLED + "\n")

    def add_veto(self, user: str) -> int:
        """Record a veto and return how many there are now."""
        votes = [*self._veto_lines(), user]
        self._write(self._path(VETO_FILE), "".join(f"{v}\n" for v in votes))
        return len(votes)

    def _veto_lines(self) -> list[str]:
        return [ln.strip() for ln in self._read_lines(self._path(VETO_FILE)) if ln.strip()]

    # -- files ---------------------------------------------------------------

    def _path(self, filename: str) -> Path:
        return self.data_dir / filename

    @staticmethod
    def _read_lines(path: Path) -> list[str]:
        # A missing file is an empty list (fresh data dir). Any other error propagates,
        # so a failed read can never be followed by a write that wipes the file.
        try:
            return path.read_text().splitlines()
        except FileNotFoundError:
            return []

    @staticmethod
    def _write(path: Path, content: str) -> None:
        # Write to a temp file and rename, so a crash never leaves a half-written list.
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            # mkstemp creates the file 0600; keep the original file's permissions
            if path.exists():
                shutil.copymode(path, tmp)
            else:
                os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
