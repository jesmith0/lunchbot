import os
import stat

import pytest

from lunchbot.config import DEFAULT_DATA_DIR
from lunchbot.storage import Entry, Store


@pytest.mark.parametrize(
    "line, entry",
    [
        ("CHIPOTLE, 5", Entry("CHIPOTLE", 5)),
        ("Jeremy, 1\n", Entry("JEREMY", 1)),
        ("THE PUB , 2", Entry("THE PUB", 2)),
        ("taco  bus", Entry("TACO BUS", 1)),
        ("JEREMY, 1, slack:U0123ABC", Entry("JEREMY", 1, {"slack": "U0123ABC"})),
        ("", None),
        ("   ", None),
    ],
)
def test_parse(line, entry):
    assert Entry.parse(line) == entry


@pytest.mark.parametrize("line", ["EVOS, lots", "EVOS, 1, U0123"])
def test_parse_rejects_malformed(line):
    with pytest.raises(ValueError):
        Entry.parse(line)


def test_platform_ids_round_trip(store, data_dir):
    store.add("drivers", Entry("MASON", 1, {"slack": "U9"}))
    assert store.find("drivers", "mason") == Entry("MASON", 1, {"slack": "U9"})
    store.update("drivers", Entry("MASON", 4, {"slack": "U9"}))
    assert (data_dir / "drivers.txt").read_text() == "JEREMY, 1\nMASON, 4, slack:U9\n"


def test_malformed_lines_are_skipped_and_logged(store, data_dir, caplog):
    (data_dir / "restaurants.txt").write_text("CHIPOTLE, 5\nEVOS, lots\n")
    assert store.entries("restaurants") == [Entry("CHIPOTLE", 5)]
    assert "restaurants.txt:2" in caplog.text


def test_missing_files_are_empty(tmp_path):
    store = Store(tmp_path / "new")
    assert store.entries("restaurants") == []
    assert store.voting_enabled()
    assert store.add("restaurants", Entry("EVOS"))
    assert (tmp_path / "new" / "restaurants.txt").read_text() == "EVOS, 1\n"


def test_failed_read_never_rewrites_the_file(store, data_dir, monkeypatch):
    # The old code treated a failed read as an empty list, then wrote that back.
    def fail(self, *args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(type(data_dir), "read_text", fail)
    with pytest.raises(PermissionError):
        store.remove("restaurants", "chipotle")
    monkeypatch.undo()
    assert (data_dir / "restaurants.txt").read_text() == "CHIPOTLE, 5\nEVOS, 1\n"


def test_writes_keep_file_permissions(store, data_dir):
    path = data_dir / "restaurants.txt"
    os.chmod(path, 0o664)
    store.add("restaurants", Entry("WAWA"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o664
    assert [p.name for p in data_dir.iterdir() if p.name.startswith(".")] == []


def test_vetoes(store, data_dir):
    assert store.add_veto("a") == 1
    assert store.add_veto("a") == 2
    store.set_voting(False)
    assert not store.voting_enabled()
    store.set_voting(True)
    assert store.voting_enabled()
    assert (data_dir / "vetos.txt").read_text() == ""


def test_bundled_data_files_parse():
    # The seed lists shipped in data/ must load cleanly.
    store = Store(DEFAULT_DATA_DIR)
    assert len(store.entries("restaurants")) > 10
    assert len(store.entries("drivers")) > 1
