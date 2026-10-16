import csv

import pytest

from app import config
from app.pipeline import fetch


def _write_permits(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["_id", "description"])
        for i in range(rows):
            writer.writerow([i, "interior alterations"])


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
