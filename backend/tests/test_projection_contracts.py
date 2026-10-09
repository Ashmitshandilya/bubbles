from health_event_projection import PROJECTION_CONTRACTS, validate_projection_row


def test_projection_contracts_have_required_user_ownership():
    assert len(PROJECTION_CONTRACTS) >= 13
    for table, contract in PROJECTION_CONTRACTS.items():
        assert "user_id" in contract["allowed"]
        assert "user_id" in contract["required"]


def test_projection_contract_rejects_unknown_columns():
    try:
        validate_projection_row("sleep_logs", {"user_id": "u", "sleep_date": "2026-09-19", "evil": "x"})
    except ValueError as exc:
        assert "unsupported columns" in str(exc)
    else:
        raise AssertionError("unknown projection column was accepted")


def test_projection_contract_normalizes_integer_values():
    row = validate_projection_row("sleep_logs", {"user_id": "u", "sleep_date": "2026-09-19", "duration_minutes": 420.7})
    assert row["duration_minutes"] == 421
