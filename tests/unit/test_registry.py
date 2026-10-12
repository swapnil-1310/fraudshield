"""
Unit tests for SEBI registry matching logic and verdict categories in stage6_registry.py.
Tests against the actual implementation as it behaves TODAY.
"""
import pytest
import re
from src.stages.stage6_registry import run_stage6_registry

# Actual regex used in stage6_registry.py line 74:
ACTUAL_SEBI_REG_REGEX = re.compile(r"^IN[A-Z]{1,3}[0-9]{4,12}$")


@pytest.mark.parametrize(
    "reg_num,is_valid",
    [
        ("INA000012345", True),       # IN + 1 letter + 9 digits = valid
        ("INZ000031633", True),       # IN + 1 letter + 8 digits = valid
        ("INH12345678", True),        # IN + 1 letter + 8 digits = valid
        ("INABC1234", True),          # IN + 3 letters + 4 digits = valid
        ("1234567890", False),        # No IN prefix = invalid
        ("IN12345678", False),        # Missing category letter after IN
        ("INA123", False),            # Too few digits (< 4 digits)
        ("INVALID-REG", False),       # Hyphens / invalid chars
        ("", False),
    ],
)
def test_sebi_registration_number_regex_actual(reg_num, is_valid):
    clean = reg_num.upper().replace(" ", "").replace("-", "").strip()
    matched = bool(ACTUAL_SEBI_REG_REGEX.match(clean))
    assert matched == is_valid


def test_registry_not_claimed():
    payload = {"claimed_advisor_name": None, "claimed_registration_number": None}
    res = run_stage6_registry(payload, job_id="test-not-claimed")
    assert res["verdict"] == "not claimed"
    assert res["matched_entity"] is None


def test_registry_malformed_number():
    payload = {
        "claimed_advisor_name": "Some Advisor",
        "claimed_registration_number": "BAD_REG_123",
    }
    res = run_stage6_registry(payload, job_id="test-malformed")
    assert res["verdict"] == "malformed number"
    assert res["matched_entity"] is None


def test_registry_not_found():
    payload = {
        "claimed_advisor_name": "Completely Unregistered Fake Entity",
        "claimed_registration_number": "INA999999999",
    }
    res = run_stage6_registry(payload, job_id="test-not-found")
    assert res["verdict"] == "not found"
    assert res["matched_entity"] is None


def test_registry_verified_real_broker():
    """Zerodha Broking Limited is in static_data/sebi_registry.json."""
    payload = {
        "claimed_advisor_name": "Zerodha",
        "claimed_registration_number": "INZ000031633",
    }
    res = run_stage6_registry(payload, job_id="test-zerodha")
    assert res["verdict"] == "verified"
    assert res["matched_entity"] is not None
    assert "Zerodha" in res["matched_entity"]["name"]


def test_registry_name_number_mismatch():
    """Real registration number of Zerodha, but claimed name is an imposter."""
    payload = {
        "claimed_advisor_name": "Shady Rocket Calls Group",
        "claimed_registration_number": "INZ000031633",
    }
    res = run_stage6_registry(payload, job_id="test-mismatch")
    assert res["verdict"] == "name-number mismatch"
    # In stage6_registry.py:110, matched_entity is not populated on mismatch
    assert res["matched_entity"] is None
