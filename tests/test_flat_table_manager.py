"""
Basic sanity tests. Run with: python -m pytest tests/ -v
(or just: python tests/test_flat_table_manager.py)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import flat_table_manager as ftm

SAMPLE_M1 = {
    "profile": {
        "abha_address": "91717251383336@abdm",
        "abha_number": "91-7172-5138-3336",
        "full_name": "Test Patient",
        "gender": "M",
        "year_of_birth": 1998,
        "mobile": "7483976167",
    },
    "eka": {"oid": "178766278389527"},
}


def test_identity_extraction():
    row = ftm.add_or_update_identity_from_m1("TEST001", SAMPLE_M1)
    assert row["abha_address"] == "91717251383336@abdm"
    assert row["eka_patient_id"] == "178766278389527"
    print("test_identity_extraction: PASS")


def test_care_context_is_deterministic():
    ftm.add_or_update_identity_from_m1("TEST002", SAMPLE_M1)
    row1 = ftm.generate_care_context(
        "TEST002", hi_type="OPConsultation", partner_patient_id="P999",
        hip_id="HIP-TEST", encounter_id="ENC-999", encounter_date="2026-08-27",
    )
    cc_id_1 = row1["care_context_id"]

    row2 = ftm.generate_care_context(
        "TEST002", hi_type="OPConsultation", partner_patient_id="P999",
        hip_id="HIP-TEST", encounter_id="ENC-999", encounter_date="2026-08-27",
    )
    cc_id_2 = row2["care_context_id"]

    assert cc_id_1 == cc_id_2, "care_context_id must be identical on rerun (idempotency)"
    print("test_care_context_is_deterministic: PASS")


def test_missing_identity_raises():
    try:
        ftm.set_clinical_data("NONEXISTENT_ROW", symptoms_text="x")
        raise AssertionError("Expected ValueError for missing row")
    except ValueError:
        print("test_missing_identity_raises: PASS")


def test_incomplete_m1_raises():
    try:
        ftm.add_or_update_identity_from_m1("TEST003", {"profile": {}})
        raise AssertionError("Expected ValueError for incomplete M1 response")
    except ValueError:
        print("test_incomplete_m1_raises: PASS")


if __name__ == "__main__":
    # clean slate for repeatable test runs
    if os.path.exists(ftm.CSV_PATH):
        os.remove(ftm.CSV_PATH)
    test_identity_extraction()
    test_care_context_is_deterministic()
    test_missing_identity_raises()
    test_incomplete_m1_raises()
    print("\nAll tests passed.")
    os.remove(ftm.CSV_PATH)  # don't leave test data behind
