"""
Unit tests for normalize_phonetic_financial_speech in stage4_transcription.py.
"""
import pytest
from src.stages.stage4_transcription import normalize_phonetic_financial_speech


def test_normalize_empty_text():
    assert normalize_phonetic_financial_speech("") == ""
    assert normalize_phonetic_financial_speech(None) == ""


def test_normalize_sebi_variations():
    assert normalize_phonetic_financial_speech("We are say bee registered") == "We are SEBI registered"
    assert normalize_phonetic_financial_speech("Licensed by saybi advisor") == "Licensed by SEBI advisor"
    assert normalize_phonetic_financial_speech("Check sebee portal") == "Check SEBI portal"
    # Word boundary \b matches before the trailing period, preserving the period in the output
    assert normalize_phonetic_financial_speech("Approved by s.e.b.i.") == "Approved by SEBI."


def test_normalize_spoken_registration_digits_english():
    text = "My advisor code is INA zero zero one two three and call me"
    normalized = normalize_phonetic_financial_speech(text)
    assert "INA00123" in normalized


def test_normalize_spoken_registration_digits_hindi():
    text = "Mera registration INA shunya ek do teen hai"
    normalized = normalize_phonetic_financial_speech(text)
    assert "INA0123" in normalized
