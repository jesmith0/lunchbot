import datetime
import io

import pytest

from lunchbot import cli, core


@pytest.fixture
def run(data_dir, monkeypatch, capsys):
    monkeypatch.setenv("LUNCHBOT_DATA_DIR", str(data_dir))

    def run(*argv, day=None):
        if day is not None:
            monkeypatch.setattr(core.datetime, "date", FakeDate.on(day))
        cli.main(list(argv))
        return capsys.readouterr().out

    return run


class FakeDate(datetime.date):
    @classmethod
    def on(cls, day):
        # 2026-11-16 is a Monday
        fixed = datetime.date(2026, 11, 16 + day)
        return type("FixedDate", (cls,), {"today": classmethod(lambda cls: fixed)})


def test_post_lunch(run):
    assert "KNOWLEDGE" in run("post-lunch", day=core.TUESDAY)


def test_post_lunch_on_weekend_posts_nothing(run):
    assert run("post-lunch", day=5) == ""


def test_close_voting(run, data_dir):
    assert "It has been decided!" in run("close-voting", day=core.MONDAY)
    assert (data_dir / "vetos.txt").read_text() == "DISABLED\n"


def test_chat(run, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("list drivers\n"))
    assert "JEREMY, 1" in run("chat", "--user", "alice")
