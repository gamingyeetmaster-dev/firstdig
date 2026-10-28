import csv
import os
import time

import httpx
import pytest

from app import config
from app.pipeline import fetch


def _write_permits(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["_id", "description"])
        for i in range(rows):
            writer.writerow([i, "interior alterations"])


class _Response:
    def __init__(self, status, payload=b"x" * 1200, headers=None):
        request = httpx.Request("GET", "https://example.test/source.csv")
        self.response = httpx.Response(
            status, request=request, headers=headers or {}
        )
        self.headers = self.response.headers
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        self.response.raise_for_status()

    def iter_bytes(self, _):
        yield self.payload


def test_active_permit_url_requests_complete_dump():
    assert "limit=500000" in config.SOURCES["permits_active"]


def test_active_permit_snapshot_rejects_site_row_cap(tmp_path, monkeypatch):
    path = tmp_path / "permits.csv"
    monkeypatch.setattr(fetch, "MIN_ACTIVE_PERMIT_ROWS", 4)
    _write_permits(path, 3)

    with pytest.raises(RuntimeError, match="partial snapshot"):
        fetch._validate_snapshot("permits_active", path)


def test_active_permit_snapshot_accepts_complete_page(tmp_path, monkeypatch):
    path = tmp_path / "permits.csv"
    monkeypatch.setattr(fetch, "MIN_ACTIVE_PERMIT_ROWS", 4)
    _write_permits(path, 4)

    fetch._validate_snapshot("permits_active", path)


def test_other_sources_do_not_use_permit_row_floor(tmp_path):
    path = tmp_path / "licences.csv"
    path.write_text("header\n", encoding="utf-8")

    fetch._validate_snapshot("business_licences", path)


def test_transient_502_retries_then_publishes_atomically(tmp_path, monkeypatch):
    responses = iter([_Response(502), _Response(200)])
    calls = []
    sleeps = []
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fetch.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(fetch.time, "sleep", sleeps.append)

    def stream(*args, **kwargs):
        calls.append((args, kwargs))
        return next(responses)

    monkeypatch.setattr(fetch.httpx, "stream", stream)
    dest = fetch.fetch("address_points", force=True, log=lambda *_: None)

    assert len(calls) == 2
    assert sleeps == [2]
    assert dest.read_bytes() == b"x" * 1200
    assert not dest.with_suffix(".csv.part").exists()


def test_retry_after_is_honoured_within_cap(tmp_path, monkeypatch):
    responses = iter([_Response(503, headers={"Retry-After": "7"}), _Response(200)])
    sleeps = []
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fetch.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(fetch.time, "sleep", sleeps.append)
    monkeypatch.setattr(fetch.httpx, "stream", lambda *a, **k: next(responses))

    fetch.fetch("address_points", force=True, log=lambda *_: None)

    assert sleeps == [7]


def test_repeated_502_without_cache_fails_closed(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fetch, "DOWNLOAD_ATTEMPTS", 3)
    monkeypatch.setattr(fetch.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(fetch.time, "sleep", lambda *_: None)

    def stream(*args, **kwargs):
        calls.append(1)
        return _Response(502)

    monkeypatch.setattr(fetch.httpx, "stream", stream)

    with pytest.raises(httpx.HTTPStatusError):
        fetch.fetch("address_points", force=True, log=lambda *_: None)

    assert len(calls) == 3
    assert not fetch.path_for("address_points").exists()
    assert not fetch.path_for("address_points").with_suffix(".csv.part").exists()


def test_fetch_all_falls_back_only_to_in_window_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    monkeypatch.setattr(
        fetch, "FILES", {"address_points": "address-points.csv"}
    )
    monkeypatch.setattr(fetch, "DOWNLOAD_ATTEMPTS", 1)
    monkeypatch.setattr(
        fetch.httpx, "stream", lambda *a, **k: _Response(502)
    )
    cached = fetch.path_for("address_points")
    cached.write_bytes(b"v" * 1200)

    result = fetch.fetch_all(force=True, log=lambda *_: None)
    assert result["address_points"] == cached

    expired = time.time() - (
        fetch.MAX_AGE_HOURS["address_points"] + 1
    ) * 3600
    os.utime(cached, (expired, expired))

    with pytest.raises(httpx.HTTPStatusError):
        fetch.fetch_all(force=True, log=lambda *_: None)


def test_non_transient_404_is_not_retried(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)

    def stream(*args, **kwargs):
        calls.append(1)
        return _Response(404)

    monkeypatch.setattr(fetch.httpx, "stream", stream)

    with pytest.raises(httpx.HTTPStatusError):
        fetch.fetch("address_points", force=True, log=lambda *_: None)

    assert calls == [1]
