"""
Regression tests for Contextual Intent Classification in FraudShield Stage 5.
Validates:
1. Awareness warnings and scam debunking in English and Hinglish are correctly
   classified as awareness_warning with is_scam_likely=False and 0% composite risk.
2. Genuine scam promotions in English and Hinglish are detected with is_scam_likely=True.
3. Wolf-in-sheep's-clothing scams (active promotions with token disclaimers) are flagged.
4. Neutral financial education remains Safe.
5. Ambiguous financial discussions are routed to Suspicious (Review Recommended) without false scam warnings.
6. Decoupling of media authenticity from semantic fraud intent.
7. Both heuristic fallback and live Ollama execution paths.
"""
import pytest
import requests
from unittest.mock import patch

from src.stages.stage5_llm import (
    heuristic_sebi_analysis,
    run_stage5_llm,
    determine_content_intent,
    is_clause_prohibitive_or_attributed,
)
from app import calculate_calibrated_verdict, build_evidence_breakdown


# ── 1. Financial Awareness Warnings (English) ────────────────────────────────

def test_awareness_warnings_english_paraphrases_heuristic():
    """Varied English paraphrases of awareness warnings must not be flagged as scams."""
    awareness_samples = [
        (
            "Scam alert: Beware of fraudsters on Telegram promising 50% guaranteed returns or pakka jackpot. "
            "Never transfer money, pay advance fees, or share your OTP with anyone. Report such scams immediately to SEBI."
        ),
        (
            "Advisory to all retail investors: Fraudulent operators are contacting people claiming 40% assured monthly profit. "
            "Do not transfer margin money or deposit funds into personal UPI accounts. Legitimate advisors never ask for your Demat password."
        ),
        (
            "Watch out for fake WhatsApp groups claiming to be SEBI registered and asking for advance fees to unlock profits. "
            "These are fraudulent schemes designed to steal your savings. File a complaint on SCORES portal or call cybercrime helpline 1930."
        ),
        (
            "Never share your OTP, MPIN, or login credentials with anyone claiming to represent a broker or regulator. "
            "Avoid joining unauthorized VIP tip channels that demand payment to access insider stock calls."
        ),
    ]

    for text in awareness_samples:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["content_intent"] == "awareness_warning", f"Expected awareness_warning intent for: {text[:60]}"
        assert res["speaker_stance"] == "warning"
        assert res["awareness_context_detected"] is True
        assert res["is_scam_likely"] is False, f"Awareness flagged as scam: {text[:60]}"
        assert res["composite_risk_score"] == 0.0
        assert len(res["specific_return_promises"]) == 0
        assert len(res["fee_or_transfer_requests"]) == 0
        assert len(res["credential_or_otp_requests"]) == 0


# ── 2. Financial Awareness Warnings (Hinglish) ───────────────────────────────

def test_awareness_warnings_hinglish_paraphrases_heuristic():
    """Varied Hinglish paraphrases warning against fraud must not be flagged."""
    hinglish_awareness_samples = [
        (
            "Dosto, aaj kal telegram par bohot fraud chal raha hai. Log bolte hain 'rocket call', "
            "'guaranteed profit', 'paisa double in 10 days'. Yeh sab scam hai! Kabhi bhi apna OTP kisi ke "
            "sath share mat karna, aur koi advance fee mat dena. Cyber crime portal par complaint darj karein."
        ),
        (
            "Satark rahein: Fake advisors se bachein jo pakka jackpot aur sure-shot profit ka vaada karte hain. "
            "Kisi ko bhi apna password ya Demat details mat bhejo. 1930 par turant call karein."
        ),
        (
            "Dhokhadhadi se bachein! WhatsApp par unregistered groups join mat karo jo 100% loss recovery "
            "ka jhaansa dete hain. SEBI registered advisors kabhi aisi guarantee nahi dete."
        ),
    ]

    for text in hinglish_awareness_samples:
        slang_found = ["rocket call", "pakka jackpot"] if "jackpot" in text or "rocket" in text else []
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=slang_found, injection_found=False, injection_match=None)
        assert res["content_intent"] == "awareness_warning", f"Expected awareness_warning for Hinglish: {text[:60]}"
        assert res["speaker_stance"] == "warning"
        assert res["awareness_context_detected"] is True
        assert res["is_scam_likely"] is False
        assert res["composite_risk_score"] == 0.0


# ── 3. Genuine Scam Promotions (English & Hinglish) ─────────────────────────

def test_genuine_scam_promotions_detected_with_intent():
    """Real scam promotions must be identified with content_intent='scam_promotion' and is_scam_likely=True."""
    scam_samples = [
        (
            "Join our VIP channel! We offer 100% loss recovery with 40% guaranteed returns every month. "
            "Transfer 5000 rupees to my UPI now, only 5 slots left!",
            ["explicit_returns", "paywall_push"]
        ),
        (
            "Please share your OTP and Demat password with our executive right now so we can activate automated trading bot.",
            ["credential_misrep"]
        ),
        (
            "Your account earned 5 Lakh profit. Transfer 10% advance fee to our account to release your locked gains.",
            ["paywall_push"]
        ),
        (
            "Pakka jackpot setup hai, kal subah 9:15 pe rocket call milega. 100% loss recovery guarantee. "
            "Premium group join karo aur paise kamao! DM me on Telegram.",
            ["implied_returns", "paywall_push"]
        ),
    ]

    for text, expected_signals in scam_samples:
        slang = ["rocket call", "pakka jackpot"] if "jackpot" in text else []
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=slang, injection_found=False, injection_match=None)
        assert res["content_intent"] == "scam_promotion", f"Failed to classify scam promotion: {text[:60]}"
        assert res["speaker_stance"] == "promoting"
        assert res["is_scam_likely"] is True
        assert res["composite_risk_score"] >= 0.35

        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=res["is_scam_likely"],
            composite_risk=res["composite_risk_score"],
            registry_verdict="not claimed"
        )
        assert verdict == "Warning: SEBI Violation / Scam"


# ── 4. Wolf in Sheep's Clothing (Active Scam with Token Disclaimers) ────────

def test_scam_with_token_disclaimer_not_exempted():
    """A scammer including a token 'for educational purposes' disclaimer must STILL be flagged."""
    deceptive_samples = [
        (
            "This video is strictly for educational purposes only and not financial advice. "
            "Join my VIP Telegram channel today! I guarantee 50% profit every week without loss. "
            "Transfer Rs 2000 to my UPI account immediately to secure your spot."
        ),
        (
            "Educational commentary only: DM me right now to join our private trading syndicate. "
            "We offer 100% loss recovery and sure-shot jackpot returns."
        ),
    ]

    for text in deceptive_samples:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["content_intent"] == "scam_promotion", f"Scam slipped through via token disclaimer: {text[:60]}"
        assert res["speaker_stance"] == "promoting"
        assert res["is_scam_likely"] is True
        assert res["composite_risk_score"] >= 0.35

        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=res["is_scam_likely"],
            composite_risk=res["composite_risk_score"],
            registry_verdict="not claimed"
        )
        assert verdict == "Warning: SEBI Violation / Scam"


# ── 5. Neutral Financial Discussion ─────────────────────────────────────────

def test_neutral_financial_discussion():
    """Standard financial literacy without return guarantees or pressure is classified as neutral_discussion."""
    neutral_texts = [
        "Dollar cost averaging in broad market index funds over a 15-year horizon has historically beaten inflation.",
        "Today we review the quarterly earnings of major IT companies. Disclaimers: investments are subject to market risks.",
    ]
    for text in neutral_texts:
        res = heuristic_sebi_analysis(text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
        assert res["content_intent"] == "neutral_discussion"
        assert res["speaker_stance"] == "neutral"
        assert res["is_scam_likely"] is False
        assert res["composite_risk_score"] == 0.0

        verdict = calculate_calibrated_verdict(
            is_deepfake=False,
            is_scam=res["is_scam_likely"],
            composite_risk=res["composite_risk_score"],
            registry_verdict="not claimed"
        )
        assert verdict == "Safe"


# ── 6. Ambiguous Financial Discussion ───────────────────────────────────────

def test_ambiguous_content_routes_to_review():
    """Unverified claims discussed neutrally without clear solicitation or warning route to Suspicious (Review)."""
    ambiguous_text = (
        "Some proprietary trading syndicates claim consistent 35% annual returns through volatility arbitrage. "
        "In this video we review how their profit-sharing structure is documented without recommending any provider."
    )
    res = heuristic_sebi_analysis(ambiguous_text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)
    assert res["content_intent"] == "ambiguous"
    assert res["speaker_stance"] == "ambiguous"
    assert res["is_scam_likely"] is False  # Not a confirmed scam
    assert res["composite_risk_score"] == 0.35

    verdict = calculate_calibrated_verdict(
        is_deepfake=False,
        is_scam=res["is_scam_likely"],
        composite_risk=res["composite_risk_score"],
        registry_verdict="not claimed"
    )
    assert verdict == "Suspicious: Review Recommended"
    assert verdict != "Warning: SEBI Violation / Scam"
    assert verdict != "Safe"


# ── 7. Decoupled Media Authenticity & Evidence Breakdown ───────────────────

def test_awareness_warning_with_deepfake_voice():
    """A deepfake voice reading an awareness warning must flag the deepfake without falsely claiming scam."""
    awareness_text = (
        "Fraud alert from regulatory watchdogs: Beware of fake social media groups promising 50% returns. "
        "Never transfer money to personal UPI accounts. File complaints on the SCORES portal."
    )
    res = heuristic_sebi_analysis(awareness_text, pii_count=0, slang_found=[], injection_found=False, injection_match=None)

    # Simulated pipeline: Deepfake audio detected (score: 0.91), but semantic content is awareness
    verdict = calculate_calibrated_verdict(
        is_deepfake=True,
        is_scam=res["is_scam_likely"],
        composite_risk=res["composite_risk_score"],
        registry_verdict="not claimed"
    )
    assert verdict == "Warning: Deepfake Detected"
    assert verdict != "Critical: Deepfake + Scam"

    # 1. Normal online pipeline test (Stage 5 LLM active)
    res_online = dict(res)
    res_online["fallback_used"] = False
    breakdown_online = build_evidence_breakdown(
        is_deepfake=True,
        is_scam=res_online["is_scam_likely"],
        composite_risk=res_online["composite_risk_score"],
        registry_check={"verdict": "not claimed"},
        sebi_analysis=res_online,
        audio_score=0.91,
        vision_score=0.0
    )
    assert breakdown_online["media_authenticity"]["is_deepfake"] is True
    assert breakdown_online["financial_fraud"]["is_scam"] is False
    assert breakdown_online["financial_fraud"]["assessment"] == "No financial fraud detected"
    assert any("awareness" in s.lower() for s in breakdown_online["contributing_signals"])

    # 2. Fallback execution test (Stage 5 LLM offline flag)
    breakdown_fallback = build_evidence_breakdown(
        is_deepfake=True,
        is_scam=res["is_scam_likely"],
        composite_risk=res["composite_risk_score"],
        registry_check={"verdict": "not claimed"},
        sebi_analysis=res,
        audio_score=0.91,
        vision_score=0.0
    )
    assert breakdown_fallback["media_authenticity"]["is_deepfake"] is True
    assert breakdown_fallback["financial_fraud"]["is_scam"] is False
    assert "Review recommended" in breakdown_fallback["financial_fraud"]["assessment"]


# ── 8. Stage 5 Integration (Mocked & Fallback Paths) ───────────────────────

def test_run_stage5_awareness_warning_under_fallback():
    """When Ollama is unreachable, heuristic fallback correctly identifies awareness warnings."""
    awareness_sample = (
        "Scam alert: Beware of fraudsters on Telegram promising 50% guaranteed returns or pakka jackpot. "
        "Never transfer money, pay advance fees, or share your OTP with anyone. Report such scams immediately to SEBI."
    )
    with patch("requests.post", side_effect=requests.RequestException("Simulated offline")):
        res = run_stage5_llm(awareness_sample, "TEST-FALLBACK-AWARENESS")

    assert res["llm_used"] is False
    assert res["fallback_used"] is True
    assert res["content_intent"] == "awareness_warning"
    assert res["speaker_stance"] == "warning"
    assert res["awareness_context_detected"] is True
    assert res["is_scam_likely"] is False
    assert res["composite_risk_score"] == 0.0


# ── 9. Live Ollama Stage 5 Integration ─────────────────────────────────────

def _is_ollama_reachable():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _is_ollama_reachable(), reason="Local Ollama instance not reachable on port 11434")
def test_live_ollama_stage5_awareness_warning():
    """Live execution path: Ollama llama3.1 must classify awareness warning without false positive."""
    awareness_text = (
        "Scam alert: Beware of fraudsters on Telegram promising 50% guaranteed returns or pakka jackpot. "
        "Never transfer money, pay advance fees, or share your OTP with anyone. Report such scams immediately to SEBI."
    )
    with patch("src.stages.stage5_llm.get_stage_config", return_value={"model_id": "llama3.1:latest", "api_url": "http://localhost:11434/api/chat", "timeout_short_sec": 90.0, "timeout_long_sec": 90.0}):
        res = run_stage5_llm(awareness_text, "LIVE-TEST-AWARENESS")

    assert res["llm_used"] is True
    assert res["fallback_used"] is False
    assert res["analysis_status"] == "success"
    assert res["content_intent"] == "awareness_warning"
    assert res["is_scam_likely"] is False
    assert res["composite_risk_score"] == 0.0
    assert len(res["specific_return_promises"]) == 0
    assert len(res["fee_or_transfer_requests"]) == 0
    assert len(res["credential_or_otp_requests"]) == 0
