"""/medical/summary must read the real lab_results / medical_reports columns."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medical_records_intelligence import extract_questions, summarize  # noqa: E402


def test_flags_from_stored_abnormal_flag_and_from_the_entered_range():
    labs = [
        {"test_name": "Ferritin", "value": 8, "unit": "ng/mL", "reference_min": 15, "reference_max": 150, "tested_at": "2026-09-30"},
        {"test_name": "TSH", "value": 6.1, "unit": "mIU/L", "abnormal_flag": "high", "tested_at": "2026-10-01"},
        {"test_name": "Hb", "value": 13, "unit": "g/dL", "reference_min": 12, "reference_max": 16},
        {"test_name": "Glucose", "value": "n/a", "reference_min": 70, "reference_max": 99},
    ]
    summary = summarize([], labs, [])
    flagged = {f["label"]: f["flag"] for f in summary["flagged_labs"]}
    assert flagged == {"Ferritin": "low", "TSH": "high"}
    assert summary["lab_count"] == 4 and summary["flagged_labs"][0]["date"] == "2026-09-30"
    assert any("Ferritin" in q for q in extract_questions([], labs)) and not any("Hb" in q for q in extract_questions([], labs))


def test_report_types_are_counted_and_empty_input_is_safe():
    reports = [{"report_name": "CBC", "report_type": "blood test"}, {"report_name": "Scan", "report_type": "imaging"}, {"report_name": "CBC2", "report_type": "blood test"}]
    assert summarize(reports, [], reports)["record_categories"] == {"blood test": 2, "imaging": 1}
    empty = summarize([], None, None)
    assert empty["flagged_labs"] == [] and empty["record_count"] == 0
