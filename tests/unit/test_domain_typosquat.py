"""
Unit tests for Levenshtein edit distance and domain typosquatting in stage9_apk_domain.py.
"""
import pytest
from src.stages.stage9_apk_domain import (
    _levenshtein,
    scan_domain,
    extract_urls_from_text,
)


def test_levenshtein_distance_cases():
    assert _levenshtein("", "") == 0
    assert _levenshtein("a", "a") == 0
    assert _levenshtein("kitten", "sitting") == 3
    assert _levenshtein("groww.in", "grow.in") == 1
    assert _levenshtein("zerodha.com", "zerodhaa.com") == 1


def test_scan_domain_legitimate():
    res = scan_domain("https://zerodha.com/kite", job_id="test-legit")
    assert res["is_phishing"] is False
    assert res["risk_level"] == "clean"


def test_scan_domain_typosquat():
    # 1 edit distance from zerodha.com
    res = scan_domain("https://zerodhaa.com/login", job_id="test-typo")
    assert res["is_phishing"] is True
    assert res["risk_level"] in ["high", "medium"]
    assert res["legitimate_broker"] == "Zerodha"


def test_scan_domain_brand_keyword():
    res = scan_domain("https://groww-bonus-login.xyz/claim", job_id="test-keyword")
    assert res["is_phishing"] is True
    assert res["risk_level"] == "high"
    assert "groww" in res["reason"].lower()


def test_extract_urls_from_text():
    sample = "Visit https://groww.in/stocks or check www.zerodha.com for details."
    urls = extract_urls_from_text(sample)
    assert any("groww.in" in u for u in urls)
    assert any("zerodha.com" in u for u in urls)
