"""
Unit tests for DPDP Act 2023 PII scrubbing shield in stage5_llm.py.
Tests positive pattern matches for all 7 PII types and negative non-PII safety.
"""
import pytest
from src.stages.stage5_llm import scrub_pii_dpdp


def test_scrub_indian_phone_number():
    text = "Call me at +91 9876543210 or 8765432109 for urgent tips."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_PHONE_DPDP]" in scrubbed
    assert "+91 9876543210" not in scrubbed
    assert "8765432109" not in scrubbed
    assert count == 2


def test_scrub_pan_card():
    text = "My official tax PAN is ABCDE1234F for verification."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_PAN_DPDP]" in scrubbed
    assert "ABCDE1234F" not in scrubbed
    assert count == 1


def test_scrub_aadhaar_number():
    text = "Aadhaar number: 1234 5678 9012 registered."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_AADHAAR_DPDP]" in scrubbed
    assert "1234 5678 9012" not in scrubbed
    assert count == 1


def test_scrub_upi_id():
    text = "Send subscription fee to trader@okhdfcbank or vip@paytm."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_UPI_ID_DPDP]" in scrubbed
    assert "trader@okhdfcbank" not in scrubbed
    assert "vip@paytm" not in scrubbed
    assert count == 2


def test_scrub_bank_account_account_no_keyword():
    text = "Deposit money into account no: 123456789012 today."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_BANK_ACCOUNT_DPDP]" in scrubbed
    assert "123456789012" not in scrubbed
    assert count >= 1


@pytest.mark.xfail(
    reason="Known issue in stage5_llm.py regex: (?:a/c|acc(?:ount)?(?:\s+no)?[:\s]+) separates a/c from [:\s]+ without grouping, failing on 'a/c <digits>'"
)
def test_scrub_bank_account_spaced_a_c():
    """Fails today due to regex precedence in stage5_llm.py."""
    text = "Send fee to a/c 123456789012."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_BANK_ACCOUNT_DPDP]" in scrubbed
    assert count >= 1


def test_scrub_email_address():
    text = "Contact support at advisor.wealth@domain.co.in for help."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_EMAIL_DPDP]" in scrubbed
    assert "advisor.wealth@domain.co.in" not in scrubbed
    assert count == 1


def test_scrub_private_channel_links():
    text = "Join our group https://t.me/rocket_calls_vip or chat.whatsapp.com/AbCdEf123"
    scrubbed, count = scrub_pii_dpdp(text)
    assert "[MASKED_PRIVATE_CHANNEL_LINK_DPDP]" in scrubbed
    assert "https://t.me/rocket_calls_vip" not in scrubbed
    assert "chat.whatsapp.com/AbCdEf123" not in scrubbed
    assert count == 2


def test_non_pii_negatives_preserved():
    """Ensures normal financial text, stock prices, quantities, and dates are not falsely masked."""
    text = "Bought 100 shares of Reliance at 2950.50 on 2026-08-25. Target is 3100 in 3 months."
    scrubbed, count = scrub_pii_dpdp(text)
    assert count == 0
    assert scrubbed == text
    assert "2950.50" in scrubbed
    assert "100" in scrubbed


def test_sebi_reg_number_not_masked_as_pan():
    """SEBI numbers like INA000012345 or INZ000012345 should not match PAN regex."""
    text = "Registered under SEBI registration number INA000012345."
    scrubbed, count = scrub_pii_dpdp(text)
    assert "INA000012345" in scrubbed
    assert "[MASKED_PAN_DPDP]" not in scrubbed
