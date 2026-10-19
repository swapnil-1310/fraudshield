"""
Unit and regression tests for Timestamp-Aware Mixed-Intent Semantic Analysis in FraudShield Stage 5.
Validates:
1. Scam-like quoted dialogue followed by an explicit awareness warning (Malini video pattern).
2. Genuine scam promotion throughout.
3. Awareness content throughout.
4. A warning that quotes suspicious claims.
5. A disclaimer attached to suspicious promotion (token disclaimer cannot erase active scam).
6. Ambiguous content requiring review (preserving 35% review floor).
7. Segment classifications, timestamps, extracted claims, and final verdict consistency.
"""
import pytest
from unittest.mock import patch

from src.stages.stage5_llm import (
    group_transcript_segments,
    analyze_segment_heuristics,
    aggregate_temporal_segments,
    run_stage5_llm,
)


# ── 1. Quoted Scam Bait Followed by Awareness Warning (Malini Skit Scenario) ─

def test_quoted_bait_followed_by_awareness_warning():
    """
    Scenario 1: Quoting a stock tip / triple returns in an opening skit,
    followed by satirical rebuttal and statutory investor awareness disclaimers.
    Must resolve to awareness_warning (0.0 risk, is_scam_likely=False).
    """
    segments = [
        {"start": 0.0, "end": 12.0, "text": "Malini ji, multibagger stock video dekha maine. Triple returns in three months, shall I invest?"},
        {"start": 12.0, "end": 26.0, "text": "Oscar movie nahi, Loscar movie banaoge tum. Multibagger ke chakkar mein beggar ban jaoge, blockbuster scam hai ye!"},
        {"start": 26.0, "end": 42.0, "text": "Soch kar, samajh kar invest kar. Issued in public interest by NSE."}
    ]

    res = run_stage5_llm(
        transcript=" ".join(s["text"] for s in segments),
        job_id="TEST-SCENARIO-1-MALINI",
        segments=segments
    )

    assert res["content_intent"] == "awareness_warning"
    assert res["speaker_stance"] == "warning"
    assert res["awareness_context_detected"] is True
    assert res["is_scam_likely"] is False
    assert res["composite_risk_score"] == 0.0
    assert len(res["specific_return_promises"]) == 0

    # Verify segment-level analysis is preserved
    segs = res.get("segments_analysis", [])
    assert len(segs) >= 2
    assert segs[0]["intent"] in ("quoted_claim", "ambiguous")
    assert any(s["intent"] == "awareness_warning" for s in segs)
    assert any("triple returns" in c.lower() for s in segs for c in s.get("extracted_claims", []))


# ── 2. Genuine Scam Promotion Throughout ────────────────────────────────────

def test_genuine_scam_promotion_throughout():
    """
    Scenario 2: Active scam promotion across all segments.
    Must resolve to scam_promotion (is_scam_likely=True, risk >= 0.50).
    """
    segments = [
        {"start": 0.0, "end": 15.0, "text": "Join our exclusive VIP channel now for guaranteed 40% monthly profit on intraday calls."},
        {"start": 15.0, "end": 30.0, "text": "Only 3 seats left! Transfer advance margin of 5000 rupees to our official UPI account right now."}
    ]

    res = run_stage5_llm(
        transcript=" ".join(s["text"] for s in segments),
        job_id="TEST-SCENARIO-2-SCAM",
        segments=segments
    )

    assert res["content_intent"] == "scam_promotion"
    assert res["speaker_stance"] in ("promoting", "endorsing")
    assert res["is_scam_likely"] is True
    assert res["composite_risk_score"] >= 0.50
    assert len(res["specific_return_promises"]) > 0 or len(res["fee_or_transfer_requests"]) > 0

    segs = res.get("segments_analysis", [])
    assert len(segs) >= 1
    assert any(s["intent"] == "scam_promotion" for s in segs)
    assert any(s["segment_risk"] >= 0.50 for s in segs)


# ── 3. Pure Awareness Content Throughout ────────────────────────────────────

def test_pure_awareness_content_throughout():
    """
    Scenario 3: Video containing purely educational anti-fraud messaging.
    Must resolve to awareness_warning (0.0 risk, is_scam_likely=False).
    """
    segments = [
        {"start": 0.0, "end": 20.0, "text": "Investor advisory: Fraudulent operators on Telegram are scamming retail investors with fake stock tips."},
        {"start": 20.0, "end": 40.0, "text": "Never share your Demat password or OTP. Always verify advisor registration on the SEBI portal."}
    ]

    res = run_stage5_llm(
        transcript=" ".join(s["text"] for s in segments),
        job_id="TEST-SCENARIO-3-AWARENESS",
        segments=segments
    )

    assert res["content_intent"] == "awareness_warning"
    assert res["speaker_stance"] == "warning"
    assert res["awareness_context_detected"] is True
    assert res["is_scam_likely"] is False
    assert res["composite_risk_score"] == 0.0
    assert len(res["specific_return_promises"]) == 0
    assert len(res["credential_or_otp_requests"]) == 0


# ── 4. A Warning That Quotes Suspicious Claims ──────────────────────────────

def test_warning_quoting_suspicious_claims():
    """
    Scenario 4: Educational warning explaining scam tactics by quoting them.
    Must resolve to awareness_warning (0.0 risk).
    """
    segments = [
        {"start": 0.0, "end": 22.0, "text": "Scammers often message people claiming they can provide guaranteed 100% loss recovery in 7 days."},
        {"start": 22.0, "end": 45.0, "text": "Beware of such claims! Real market investments involve risk. Report fraudulent channels to cybercrime helpline 1930."}
    ]

    res = run_stage5_llm(
        transcript=" ".join(s["text"] for s in segments),
        job_id="TEST-SCENARIO-4-QUOTE-WARNING",
        segments=segments
    )

    assert res["content_intent"] == "awareness_warning"
    assert res["speaker_stance"] == "warning"
    assert res["is_scam_likely"] is False
    assert res["composite_risk_score"] == 0.0
    assert len(res["specific_return_promises"]) == 0


# ── 5. Token Disclaimer Attached to Active Scam Promotion ───────────────────

def test_token_disclaimer_attached_to_scam_promotion():
    """
    Scenario 5: Active scam promotion hiding behind an attached token disclaimer.
    A later disclaimer MUST NOT erase earlier suspicious promotional behavior!
    Must resolve to scam_promotion (is_scam_likely=True, risk >= 0.50).
    """
    segments = [
        {"start": 0.0, "end": 25.0, "text": "I promise guaranteed 50% profit every month. DM me on Telegram to join our VIP jackpot stock group."},
        {"start": 25.0, "end": 40.0, "text": "This video is for educational purposes only and not financial advice. Invest at your own risk."}
    ]

    res = run_stage5_llm(
        transcript=" ".join(s["text"] for s in segments),
        job_id="TEST-SCENARIO-5-TOKEN-DISCLAIMER",
        segments=segments
    )

    assert res["content_intent"] == "scam_promotion"
    assert res["is_scam_likely"] is True
    assert res["composite_risk_score"] >= 0.50
    assert len(res["specific_return_promises"]) > 0 or len(res["paywall_push"]) > 0

    segs = res.get("segments_analysis", [])
    assert len(segs) >= 1
    assert any(s["intent"] == "scam_promotion" for s in segs)


# ── 6. Ambiguous Content Requiring Review ───────────────────────────────────

def test_ambiguous_content_requiring_review():
    """
    Scenario 6: Discussion of extreme yields or suspicious claims without
    clear endorsement and without clear cautionary warning.
    Must route to ambiguous with 35% review floor.
    """
    segments = [
        {"start": 0.0, "end": 20.0, "text": "Some proprietary trading syndicates claim consistent 35% annual returns through volatility arbitrage."},
        {"start": 20.0, "end": 40.0, "text": "In this video we review how their profit-sharing structure is documented without recommending any provider."}
    ]

    res = run_stage5_llm(
        transcript=" ".join(s["text"] for s in segments),
        job_id="TEST-SCENARIO-6-AMBIGUOUS",
        segments=segments
    )

    assert res["content_intent"] == "ambiguous"
    assert res["is_scam_likely"] is False
    assert res["composite_risk_score"] >= 0.35
    assert res["analysis_status"] == "success"


# ── 7. Segment Grouping & Chunking Boundaries ───────────────────────────────

def test_segment_grouping_logic():
    """
    Tests that group_transcript_segments properly groups 2-second fragments
    into ~15-30s discourse units while respecting natural pauses.
    """
    raw_segments = [
        {"start": 0.0, "end": 3.0, "text": "Part one of topic."},
        {"start": 3.0, "end": 7.0, "text": "Part two continuing the point."},
        {"start": 7.0, "end": 12.0, "text": "Part three concluding first argument."},
        # 5 second pause here -> scene break
        {"start": 17.0, "end": 22.0, "text": "Now moving to the second topic."},
        {"start": 22.0, "end": 28.0, "text": "Explaining the second topic."}
    ]

    chunks = group_transcript_segments(raw_segments, max_pause=2.0)
    assert len(chunks) == 2
    assert chunks[0]["start"] == 0.0
    assert chunks[0]["end"] == 12.0
    assert chunks[1]["start"] == 17.0
    assert chunks[1]["end"] == 28.0
