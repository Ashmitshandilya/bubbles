from ai_telemetry import record, snapshot


def test_telemetry_excludes_content_and_keys():
    record(provider="Test", model="model", latency_ms=12.3, outcome="success",
           usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
    row = snapshot()["recent"][-1]
    assert row["total_tokens"] == 15
    assert "prompt" not in row
    assert "response" not in row
    assert "api_key" not in row
