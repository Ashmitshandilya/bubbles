"""A malformed CSV is a plain, user-safe error and never an unhandled exception."""
from __future__ import annotations

import csv

import pytest

import import_api


def test_an_oversized_field_is_reported_as_a_value_error(monkeypatch):
    monkeypatch.setattr(csv, "field_size_limit", csv.field_size_limit)  # leave the real limit alone after the test
    previous = csv.field_size_limit(10)
    try:
        with pytest.raises(ValueError) as refused:
            import_api.parse_rows("weight", "date,weight\n2026-10-01," + "9" * 50 + "\n")
        assert "plain CSV" in str(refused.value)
    finally:
        csv.field_size_limit(previous)


def test_a_normal_file_still_parses():
    rows, skipped = import_api.parse_rows("weight", "date,weight\n2026-10-01,61.5\n2026-10-02,61.2\n")
    assert len(rows) == 2 and skipped == []
