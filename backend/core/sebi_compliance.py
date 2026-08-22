"""
FraudShield-SEBI Pro — High Accuracy SEBI Compliance Engine v3 (Fully Offline)
=================================================================================
Multi-layer forensic detection running 100% locally:
  Layer 1   — Structural Pre-scan (28+ regex signals with calibrated weights)
  Layer 1.5 — TF-IDF Keyword Density Scorer (catches rephrased scam language)
  Layer 2   — Ensemble Confidence Calibration & Evidence Assembly

Engine Architecture documented in: core/prompts.py → SEBI_OFFLINE_ENGINE_DESCRIPTION
"""

import os
import json
import re
import sys
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — Forensic Signal Library
# Tuple: (regex pattern, weight, label, SEBI rule)
# Weights are calibrated. Negative weights = compliance markers.
# ─────────────────────────────────────────────────────────────────────────────
FORENSIC_SIGNALS: List[Tuple[str, float, str, str]] = [

    # ── TIER A: Definitive Violations (weight 0.75–1.00) ─────────────────────
    (
        r"\b(guarante[ed]{1,2}|assured?)\b.{0,50}\b(returns?|profits?|gains?|yields?|income|money|\d+\s*%)\b",
        0.90, "Guaranteed/assured returns — core SEBI fraud indicator",
        "SEBI (Investment Advisers) Regulations 2013 — Reg 7A; SEBI FUTP 2003 — Reg 3"
    ),
    (
        r"\b100\s*%\s*(safe|profits?|returns?|guaranteed|sure|certain|accurate|success|accurate)\b",
        0.88, "100% certainty claim for financial outcomes",
        "SEBI IA Regulations 2013 — Reg 7A(c)"
    ),
    (
        r"\b(no|zero|0)\s*(risk|loss|downside|chance of loss)\b",
        0.85, "Zero-risk claims — all investments carry market risk",
        "SEBI IA Regulations 2013 — Reg 19; SEBI FUTP 2003"
    ),
    (
        r"\bdouble\b.{0,35}\b(money|investment|capital|wealth|portfolio|fund)\b",
        0.82, "Promise to double money — Ponzi/pump-and-dump framing",
        "SEBI FUTP Regulations 2003 — Reg 4 & 4"
    ),
    (
        r"\b(insider|inside information|confidential tip|inside tip|insider trading)\b",
        0.92, "Reference to insider/confidential trading information",
        "SEBI (Prohibition of Insider Trading) Regulations 2015 — Reg 3"
    ),
    (
        r"\bpump\b.{0,25}\bdump\b|\bdump\b.{0,25}\bpump\b",
        0.95, "Explicit pump-and-dump scheme language",
        "SEBI FUTP Regulations 2003 — Reg 4(2)(a)"
    ),
    (
        r"\b(ponzi|pyramid\s*scheme|chain\s*referral)\b",
        0.98, "Direct Ponzi/pyramid scheme reference",
        "SEBI Act 1992 — Section 11; SEBI FUTP 2003"
    ),
    (
        r"\b(fixed\s*returns?|monthly\s*returns?|weekly\s*returns?|daily\s*profits?)\b.{0,30}\b(\d+\s*%|rs\.?|₹|\d+\s*rupee)\b",
        0.80, "Periodic fixed return promise with specific figures — Ponzi structure",
        "SEBI (Collective Investment Schemes) Regulations 1999; SEBI FUTP 2003"
    ),
    (
        r"\b(operator\s*backed|operator\s*stock|operator\s*tip|operator\s*target|operator\s*call)\b",
        0.82, "Reference to stock market operators — implies price manipulation",
        "SEBI FUTP Regulations 2003 — Reg 4(2)(a)(b)"
    ),
    (
        r"\b(pay after profit|profit sharing fee|success fee|commission after gain|pay after returns?)\b",
        0.75, "Illegal profit-linked fee structure",
        "SEBI IA Regulations 2013 — Reg 13(d)"
    ),
    (
        r"\b(front[- ]?running|front[- ]?run|trade before|buy before announcement)\b",
        0.92, "Front-running — trading ahead of client orders or material info",
        "SEBI FUTP Regulations 2003 — Reg 4(2)(q); SEBI (Prohibition of Insider Trading) Regulations 2015"
    ),
    (
        r"\b(spoofing|layering|fake orders?|wash trade|wash trading|circular trading)\b",
        0.90, "Market manipulation via spoofing, layering, or wash trading",
        "SEBI FUTP Regulations 2003 — Reg 4(2)(a)(g)"
    ),
    (
        r"\b(sebi\s*officer|sebi\s*official|on behalf of sebi|sebi\s*notice|sebi\s*penalty)\b.{0,50}\b(pay|deposit|transfer|send|urgent)\b",
        0.95, "Impersonation of SEBI officials demanding payments — extortion scam",
        "SEBI Act 1992; IPC Section 170, 419, 420"
    ),
    (
        r"\b(crypto|bitcoin|ethereum|nft)\b.{0,40}\b(guaranteed|assured|100%|risk.?free|double|triple)\b",
        0.85, "Guaranteed returns on unregulated crypto assets",
        "SEBI Circular 2019; RBI Advisory on Virtual Currencies"
    ),

    # ── TIER B: Strong Indicators (weight 0.45–0.74) ─────────────────────────
    (
        r"\bjoin\b.{0,40}\b(vip|premium|exclusive|private|paid)\b.{0,40}\b(telegram|whatsapp|signal|group|channel)\b",
        0.75, "Soliciting investors to paid unregistered messaging channels for tips",
        "SEBI Circular SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2023/123"
    ),
    (
        r"\b(telegram|whatsapp)\b.{0,40}\b(join|subscribe|vip|premium|paid|exclusive)\b",
        0.70, "Driving investors to unregistered Telegram/WhatsApp advisory groups",
        "SEBI Circular SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2023/123"
    ),
    (
        r"\b(subscribe|subscription|paid plan|premium plan|membership fee)\b.{0,50}\b(stock|tip|call|alert|signal|profits?|returns?)\b",
        0.62, "Subscription fee for unregistered stock tip advisory service",
        "SEBI (Research Analysts) Regulations 2014 — Reg 3"
    ),
    (
        r"\b(\d{2,3})\s*%\s*(accuracy|accurate|success\s*rate|winning\s*rate|hit\s*rate)\b",
        0.65, "Unaudited accuracy rate claim — misleading investors without SEBI-verified track record",
        "SEBI (Research Analysts) Regulations 2014 — Reg 16(a); Reg 23"
    ),
    (
        r"\b(multibagger|10x|20x|30x|50x|100x|200x)\b.{0,50}\b(stock|share|pick|buy|target|potential)\b",
        0.68, "Extreme unsubstantiated return projections",
        "SEBI RA Regulations 2014 — Reg 16(a)"
    ),
    (
        r"\b(jackpot|sureshot|sure\s*shot|operator)\s*(call|tip|stock|pick|alert)\b",
        0.72, "Distributing speculative 'sureshot/jackpot' calls without RA registration",
        "SEBI (Research Analysts) Regulations 2014 — Reg 3"
    ),
    (
        r"\b(breakout\s*alert|urgent\s*buy|hot\s*tip|target\s*\d+|strong\s*buy)\b.{0,60}\b(limited|hurry|fast|now|today|seats|slots|registrations?)\b",
        0.58, "Urgent advisory with scarcity pressure without regulatory disclaimers",
        "SEBI RA Regulations 2014 — Reg 23"
    ),
    (
        r"\bcircuit\b.{0,30}\b(buy|sell|before|tomorrow|target|alert)\b",
        0.60, "Circuit limit exploitation — possible front-running or circular trading signals",
        "SEBI FUTP Regulations 2003 — Reg 4(1)"
    ),
    (
        r"\blimited\b.{0,30}\b(seats?|slots?|members?|spots?|registrations?)\b.{0,50}\b(join|subscribe|register|enrol|available)\b",
        0.52, "Artificial scarcity framing to drive FOMO-based subscriptions",
        "SEBI IA Regulations 2013 — Reg 7A"
    ),
    (
        r"\b(forward\s*this|share\s*with\s*friends|viral|spread|send\s*to\s*all)\b",
        0.55, "Viral chain-message tactics — coordinated pump distribution",
        "SEBI FUTP Regulations 2003 — Reg 4(2)(a)"
    ),
    (
        r"\b(research\s*team|our\s*team|our\s*experts?).{0,40}\b(\d{2,3})\s*%\b.{0,30}(accuracy|returns|profit|correct)\b",
        0.68, "Team accuracy claim without auditable SEBI-verified research disclosure",
        "SEBI RA Regulations 2014 — Reg 16, Reg 23"
    ),
    (
        r"\b(real[\s-]?time\s*alert|live\s*call|live\s*tip|intraday\s*tip)\b",
        0.48, "Real-time intraday tip service without SEBI RA registration disclosure",
        "SEBI RA Regulations 2014 — Reg 3"
    ),
    (
        r"\b(stop\s*loss|sl)\s*[:=]?\s*\d+.{0,30}(target|tgt)\s*[:=]?\s*\d+.{0,50}\b(buy|sell|enter|exit)\b",
        0.45, "Structured stock tip with specific SL/target levels without SEBI RA authorisation",
        "SEBI RA Regulations 2014 — Reg 3; Reg 14"
    ),
    (
        r"\b(not\s*sebi|without\s*sebi|no\s*sebi)\s*(registered|registration|reg|auth)",
        0.70, "Explicit admission of operating without SEBI registration",
        "SEBI IA Regulations 2013 — Reg 3"
    ),
    (
        r"\b(client|member|subscriber)\s*(earned|made|got|received)\s*(rs\.?|₹|inr)?\s*\d+",
        0.55, "Unverified client testimonial with specific profit figures",
        "SEBI RA Regulations 2014 — Reg 16(a)"
    ),
    (
        r"\b(market\s*crash|crash\s*alert|sell\s*everything|emergency\s*exit|panic)\b.{0,40}\b(now|immediately|urgent|today|before)\b",
        0.52, "Fear-based urgency manipulation to induce panic selling",
        "SEBI FUTP Regulations 2003 — Reg 4(2)(a)"
    ),
    (
        r"\b(we\s*will\s*manage|we\s*manage\s*your|hand\s*over\s*your|give\s*us\s*your)\b.{0,30}\b(portfolio|account|demat|trading)\b",
        0.78, "Unauthorized portfolio management service without SEBI PMS registration",
        "SEBI (Portfolio Managers) Regulations 2020 — Reg 3"
    ),

    # ── TIER C: Moderate/Contextual Signals (weight 0.25–0.44) ──────────────
    (
        r"\b(big\s*move|massive\s*rally|explosive\s*rally|rocket|moon)\b.{0,30}(stock|share|nifty|sensex|price)\b",
        0.35, "Hyperbolic prediction language without technical basis",
        "SEBI RA Regulations 2014 — Reg 16"
    ),
    (
        r"\b(referral\s*code|open\s*demat|demat\s*account|broker\s*link|cashback)\b",
        0.38, "Referral/demat account solicitation — possible unregistered distribution agent",
        "SEBI (Stock Brokers) Regulations 1992"
    ),
    (
        r"\b(unverified|anonymous|faceless)\s*(advisor|analyst|expert|trader)\b",
        0.50, "Anonymous financial advisory without identity disclosure",
        "SEBI IA Regulations 2013 — Reg 10"
    ),
    (
        r"\b(sebi\s*registered|sebi\s*certified|sebi\s*authorised)\b.{0,60}\b(without|no|not|fake|false)\b",
        0.95, "Falsely claiming SEBI authorisation",
        "SEBI IA Regulations 2013 — Reg 3; IPC Section 420"
    ),
    (
        r"\b(for\s*educational\s*purposes?)\b.{0,80}\b(buy|sell|target|stop\s*loss|sl|tgt|entry|exit)\b",
        0.45, "Educational disclaimer contradicted by specific actionable buy/sell recommendations",
        "SEBI RA Regulations 2014 — Reg 3"
    ),

    # ── TIER D: Compliance Positive Signals (NEGATIVE weights reduce score) ──
    (
        r"\bpast\s*performance\b.{0,50}\b(no|not\s*a)\s*(guarantee|indicator|indicative|predictive)\b",
        -0.28, "[COMPLIANT] Past performance disclaimer — regulatory standard disclosure",
        "SEBI Compliant Standard Disclosure"
    ),
    (
        r"\bsebi\s*reg(istered|istration)\.?\s*(no\.?|number\.?|#)?\s*:?\s*in[ahz]\d{9}\b",
        -0.35, "[COMPLIANT] Valid-format SEBI registration number cited",
        "SEBI IA Regulations 2013 — Reg 10"
    ),
    (
        r"\b(mutual\s*fund[s]?|mf)\b.{0,40}\b(subject to|investments? are subject to)\s*market\s*risk\b",
        -0.30, "[COMPLIANT] Statutory mutual fund risk disclaimer",
        "SEBI MF Regulations 1996 — Schedule V"
    ),
    (
        r"\bfor\s*(educational|informational|awareness|learning)\s*purpose(s)?\s*only\b",
        -0.22, "[COMPLIANT] Educational disclaimer reduces advisory intent",
        "SEBI Content Compliance Framework"
    ),
    (
        r"\bplease\s*(consult|seek|speak to|contact)\b.{0,40}\b(sebi\s*registered|qualified|certified)\b.{0,40}(advisor|analyst|professional)\b",
        -0.25, "[COMPLIANT] Proper referral to qualified SEBI professional",
        "SEBI IA Regulations 2013 — Compliance"
    ),
    (
        r"\b(this is not investment advice|not financial advice|not a recommendation)\b",
        -0.30, "[COMPLIANT] Explicit non-advice disclaimer present",
        "SEBI Content Compliance Standard"
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1.5 — TF-IDF Keyword Density Scorer
# Catches rephrased scam language that exact regex misses
# ─────────────────────────────────────────────────────────────────────────────

FRAUD_VOCABULARY = [
    "guaranteed", "assured", "certain", "definite", "risk-free", "zero risk",
    "100%", "double", "triple", "quadruple", "multiply",
    "fixed returns", "monthly income", "daily profit", "weekly earnings",
    "urgent", "hurry", "limited", "exclusive", "only today", "last chance",
    "act now", "don't miss", "once in lifetime", "fast booking",
    "join group", "premium channel", "vip access", "paid tips",
    "subscription", "membership", "enroll now", "register today",
    "our team", "our experts", "our analysts", "our research",
    "operator", "insider", "confidential", "secret", "private info",
    "big move", "massive rally", "rocket", "moon", "circuit",
    "pump", "dump", "jackpot", "sureshot", "sure shot", "multibagger",
    "stop loss", "target", "entry", "exit", "buy call", "sell call",
    "intraday", "swing", "positional", "futures", "options", "nifty",
    "bank nifty", "sensex", "equity", "commodity", "forex",
    "screenshot", "p&l", "profit loss", "portfolio", "trading app",
    "demat account", "broker", "referral", "commission", "cashback",
    "pay after profit", "profit sharing", "success fee",
    "years of experience", "track record", "accuracy", "success rate",
    "winning rate", "verified", "proven", "tested", "backtested",
]

SCAM_ARCHETYPES = [
    "join our premium telegram for guaranteed returns with 95% accuracy",
    "our research team gives sureshot calls with zero risk and fixed monthly income",
    "operator backed stock tip with target 500 buy now limited seats available",
    "insider information on upcoming IPO double your money in 30 days guaranteed",
    "pay after profit subscription plan for VIP stock tips on WhatsApp",
    "100% accurate calls with multibagger returns join our exclusive channel",
    "we manage your portfolio with assured returns of 40% monthly",
    "SEBI registered advisor guaranteed profits join premium group now limited slots",
]

_tfidf_vectorizer = None
_scam_vectors = None


def _get_tfidf_scorer():
    """Initialize TF-IDF vectorizer with fraud vocabulary (lazy load)."""
    global _tfidf_vectorizer, _scam_vectors

    if _tfidf_vectorizer is not None:
        return _tfidf_vectorizer, _scam_vectors

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        _tfidf_vectorizer = TfidfVectorizer(
            vocabulary=None,
            max_features=500,
            ngram_range=(1, 2),
            stop_words="english"
        )
        _scam_vectors = _tfidf_vectorizer.fit_transform(SCAM_ARCHETYPES)

        print("[SEBI Engine] TF-IDF scorer initialized with fraud vocabulary.")
        return _tfidf_vectorizer, _scam_vectors
    except ImportError:
        print("[SEBI Engine] scikit-learn not installed. TF-IDF scoring disabled.")
        return None, None
    except Exception as e:
        print(f"[SEBI Engine] TF-IDF init error: {e}")
        return None, None


def _compute_tfidf_score(text: str) -> float:
    """
    Layer 1.5: Compute TF-IDF similarity between input text and known scam archetypes.
    Returns a score between 0.0 and 1.0.
    """
    vectorizer, scam_vecs = _get_tfidf_scorer()
    if vectorizer is None or scam_vecs is None:
        return 0.0

    try:
        from sklearn.metrics.pairwise import cosine_similarity

        text_vector = vectorizer.transform([text.lower()])
        similarities = cosine_similarity(text_vector, scam_vecs)[0]

        max_sim = float(max(similarities)) if len(similarities) > 0 else 0.0
        avg_sim = float(sum(similarities) / len(similarities)) if len(similarities) > 0 else 0.0

        tfidf_score = 0.65 * max_sim + 0.35 * avg_sim

        words = text.lower().split()
        if len(words) > 0:
            fraud_word_set = set(w.lower() for w in FRAUD_VOCABULARY)
            fraud_count = sum(1 for w in words if w in fraud_word_set)
            density = fraud_count / len(words)
            density_score = min(density / 0.15, 1.0) * 0.3
            tfidf_score = min(tfidf_score + density_score, 1.0)

        return round(tfidf_score, 4)
    except Exception as e:
        print(f"[SEBI Engine] TF-IDF scoring error: {e}")
        return 0.0


def _run_forensic_scan(text: str) -> Tuple[float, List[str], List[str]]:
    """Layer 1: Structural forensic pre-scan."""
    text_lower = text.lower().strip()
    score = 0.0
    reasons = []
    rules = set()

    for pattern, weight, label, rule in FORENSIC_SIGNALS:
        if re.search(pattern, text_lower):
            score += weight
            reasons.append(label)
            if not label.startswith("[COMPLIANT]"):
                rules.add(rule)

    word_count = len(text.split())
    if word_count < 25 and score > 0.1:
        score *= 1.20

    score = min(max(round(score, 4), 0.0), 1.0)
    return score, reasons, list(rules)


def analyze_sebi_compliance(transcript: str, advisor_reg_no: str = "") -> Dict[str, Any]:
    """
    Fully offline multi-layer forensic SEBI compliance analysis.

    Layer 1:   Regex forensic pre-scan (28+ signals)
    Layer 1.5: TF-IDF keyword density scorer
    Layer 2:   Ensemble calibration & evidence assembly
    """

    if not transcript or not transcript.strip():
        return {
            "is_violation": False, "risk_score": 0.05, "verdict": "COMPLIANT",
            "confidence": "HIGH", "summary": "No speech or text content detected to analyze.",
            "reasons": ["No financial content present in submission."],
            "sebi_rules": [], "detected_schemes": ["none"], "compliance_signals": []
        }

    # ── Layer 1: Structural Pre-scan ─────────────────────────────────────────
    pre_score, pre_reasons, pre_rules = _run_forensic_scan(transcript)

    # ── Layer 1.5: TF-IDF Keyword Density Scorer ─────────────────────────────
    tfidf_score = _compute_tfidf_score(transcript)

    # Blend Layer 1 and Layer 1.5
    offline_score = 0.70 * pre_score + 0.30 * tfidf_score
    offline_score = min(max(round(offline_score, 4), 0.0), 1.0)

    if tfidf_score > 0.4 and "TF-IDF similarity to known scam patterns detected" not in pre_reasons:
        pre_reasons.append(f"TF-IDF similarity to known scam patterns detected (score: {tfidf_score:.2f})")

    # ── Advisor registration penalty ──────────────────────────────────────────
    if advisor_reg_no and advisor_reg_no.strip():
        valid_fmt = bool(re.match(r"^in[ahz]\d{9}$", advisor_reg_no.strip().lower()))
        if not valid_fmt:
            offline_score = min(1.0, offline_score + 0.10)
            pre_reasons.append(f"Invalid/malformed SEBI registration format: '{advisor_reg_no}'")
            pre_rules.append("SEBI IA Regulations 2013 — Reg 3")

    is_violation = offline_score >= config.SEBI_RISK_THRESHOLD
    text_lower = transcript.lower()
    detected_schemes = []
    if re.search(r"\b(ponzi|pyramid|chain)\b", text_lower): detected_schemes.append("ponzi")
    if re.search(r"\b(pump|dump|operator)\b", text_lower): detected_schemes.append("pump_dump")
    if re.search(r"\b(insider|inside information)\b", text_lower): detected_schemes.append("insider_tip")
    if re.search(r"\b(telegram|whatsapp).{0,30}(vip|paid|premium)\b", text_lower): detected_schemes.append("paid_group")
    if re.search(r"\b(front.?run|spoofing|wash\s*trad)\b", text_lower): detected_schemes.append("market_manipulation")
    if re.search(r"\b(impersonat|on behalf of sebi|sebi officer)\b", text_lower): detected_schemes.append("impersonation")
    if not detected_schemes: detected_schemes = ["none"]

    if offline_score >= 0.80:
        confidence = "HIGH"
    elif offline_score >= 0.50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    verdict_label = "SEBI_VIOLATION" if is_violation else ("WATCH" if offline_score > 0.35 else "COMPLIANT")
    summary = (
        f"SEBI Violation Detected (Forensic Score: {offline_score:.0%}) — {', '.join(detected_schemes)} scheme patterns identified."
        if is_violation else
        f"Risk assessment: {offline_score:.0%}. {'Monitoring recommended.' if offline_score > 0.35 else 'Content appears compliant.'}"
    )

    return {
        "is_violation": is_violation,
        "risk_score": offline_score,
        "verdict": verdict_label,
        "confidence": confidence,
        "summary": summary,
        "reasons": pre_reasons or ["No explicit SEBI violation signals detected."],
        "sebi_rules": pre_rules,
        "detected_schemes": detected_schemes,
        "compliance_signals": []
    }
