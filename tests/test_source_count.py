from app.db import SCHEMA
from app.pipeline.openings import distinct_source_count, opening_key, unit_of
from app.web.queries import opening_filters


def _signals(*types):
    return [{"type": source_type} for source_type in types]


def test_repeated_permits_are_one_source_category():
    assert distinct_source_count(_signals("permit", "permit")) == 1


def test_repeated_licences_are_one_source_category():
    assert distinct_source_count(_signals("licence", "licence")) == 1


def test_permit_and_licence_are_cross_source():
    assert distinct_source_count(_signals("permit", "licence")) == 2


def test_missing_or_malformed_signal_types_do_not_inflate_sources():
    signals = [{"type": "permit"}, {"type": ""}, {}, None]
    assert distinct_source_count(signals) == 1


def test_multi_unit_addresses_remain_separate():
    assert unit_of("10 King St, Unit 101") == "101"
    assert unit_of("10 King St, Unit 202") == "202"
    assert opening_key("10", "King St", "101") != opening_key("10", "King St", "202")


def test_missing_unit_does_not_claim_a_tenant_unit():
    assert unit_of("10 King St") is None
    assert opening_key("10", "King St") != opening_key("10", "King St", "101")


def test_opening_filter_requires_distinct_sources():
    sql, params, active = opening_filters({"minsig": "2", "days": "90"}, True)
    assert "source_count >= ?" in sql
    assert "signal_count >= ?" not in sql
    assert params[0] == 2
    assert active["minsig"] == 2


def test_openings_schema_persists_both_metrics():
    assert "signal_count INTEGER, source_count INTEGER" in SCHEMA
