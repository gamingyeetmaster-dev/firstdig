import datetime as dt
import importlib.util
from pathlib import Path
from zoneinfo import ZoneInfo

from app.pipeline import run as pipeline_run
from app.web import scheduler


TORONTO = ZoneInfo("America/Toronto")


def local(year, month, day, hour, minute=0):
    return dt.datetime(year, month, day, hour, minute, tzinfo=TORONTO)


def test_ready_and_fresh_are_separate_before_daily_boundary():
    now = local(2026, 10, 13, 5)
    yesterday = "2026-10-12T10:05:00+00:00"  # 06:05 Toronto
    assert scheduler._data_ready(now, yesterday, 100) is True
    assert scheduler._data_fresh(now, yesterday, 100) is True


def test_empty_cache_recovers_immediately_even_before_six():
    now = local(2026, 10, 13, 2)
    assert scheduler._should_refresh(now, None, 0) is True


def test_late_wake_recovers_stale_data_and_honours_backoff():
    now = local(2026, 10, 13, 15, 45)
    yesterday = "2026-10-12T10:05:00+00:00"
    assert scheduler._should_refresh(now, yesterday, 100) is True
    assert scheduler._should_refresh(
        now, yesterday, 100, retry_at=now + dt.timedelta(minutes=30)
    ) is False


def test_data_only_recovery_never_invokes_email(monkeypatch):
    calls = []

    def fake_run(*, log):
        calls.append(log)

    monkeypatch.setattr(pipeline_run, "run", fake_run)
    scheduler._refresh_data_only()
    assert calls == [scheduler.log.info]


def test_wake_monitor_rejects_empty_and_accepts_fresh_data():
    script = Path(__file__).parents[1] / "scripts" / "check_health.py"
    spec = importlib.util.spec_from_file_location("check_health", script)
    monitor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    now = dt.datetime(2026, 10, 13, 20, tzinfo=dt.timezone.utc)
    ok, reason = monitor.assess({"ok": True, "projects": 0, "last_run": None}, now)
    assert ok is False and "no project data" in reason
    ok, reason = monitor.assess(
        {"ok": True, "projects": 6676, "last_run": "2026-10-13T19:55:00+00:00"},
        now,
    )
    assert ok is True and "fresh nonempty dataset" in reason
