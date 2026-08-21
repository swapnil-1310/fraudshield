"""
FraudShield-SEBI Pro — High Accuracy SEBI Compliance Engine v2
==============================================================
Multi-layer forensic detection:
  Layer 1 — Structural Pre-scan (24+ regex signals with calibrated weights)
  Layer 2 — Gemini 1.5 Pro Deep Chain-of-Thought Forensic Analysis
  Layer 3 — Ensemble Confidence Calibration & Evidence Assembly
"""

import os
import json
import re
import sys
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

HAS_GEMINI = False
_gemini_client = None

try:
    from google import genai as google_genai
    if config.GEMINI_API_KEY:
        _gemini_client = google_genai.Client(api_key=config.GEMINI_API_KEY)
        HAS_GEMINI = True
except Exception:
    # Fallback to old SDK if new not available
    try:
        import google.generativeai as genai_legacy
        if config.GEMINI_API_KEY:
            genai_legacy.configure(api_key=config.GEMINI_API_KEY)
            HAS_GEMINI = True
            _gemini_client = "legacy"
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — Forensic Signal Library
# Tuple: (regex pattern, weight, label, SEBI rule)
# Weights are calibrated. Negative weights = compliance markers.
# ─────────────────────────────────────────────────────────────────────────────
FORENSIC_SIGNALS: List[Tuple[str, float, str, str]] = [

    # ── TIER A: Definitive Violations (weight 0.75–1.00) ─────────────────────
    (
        r"\b(guarante[ed]{1,2}|assured?)\b.{0,50}\b(return|profit|gain|yield|income|money|\d+\s*%)\b",
        0.90, "Guaranteed/assured returns — core SEBI fraud indicator",
        "SEBI (Investment Advisers) Regulations 2013 — Reg 7A; SEBI FUTP 2003 — Reg 3"
    ),
    (
        r"\b100\s*%\s*(safe|profit|return|guaranteed|sure|certain|accurate|success|accurate)\b",
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
        "SEBI FUTP Regulations 2003 — Reg 3 & 4"
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
        r"\b(fixed\s*return|monthly\s*return|weekly\s*return|daily\s*profit)\b.{0,30}\b(\d+\s*%|rs\.?|₹|\d+\s*rupee)\b",
        0.80, "Periodic fixed return promise with specific figures — Ponzi structure",
        "SEBI (Collective Investment Schemes) Regulations 1999; SEBI FUTP 2003"
    ),
    (
        r"\b(operator\s*backed|operator\s*stock|operator\s*tip|operator\s*target|operator\s*call)\b",
        0.82, "Reference to stock market operators — implies price manipulation",
        "SEBI FUTP Regulations 2003 — Reg 4(2)(a)(b)"
    ),
    (
        r"\b(pay after profit|profit sharing fee|success fee|commission after gain|pay after returns)\b",
        0.75, "Illegal profit-linked fee structure",
        "SEBI IA Regulations 2013 — Reg 13(d)"
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
        r"\b(subscribe|subscription|paid plan|premium plan|membership fee)\b.{0,50}\b(stock|tip|call|alert|signal|profit|return)\b",
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
        r"\b(breakout\s*alert|urgent\s*buy|hot\s*tip|target\s*\d+|strong\s*buy)\b.{0,60}\b(limited|hurry|fast|now|today|seats|slots)\b",
        0.58, "Urgent advisory with scarcity pressure without regulatory disclaimers",
        "SEBI RA Regulations 2014 — Reg 23"
    ),
    (
        r"\bcircuit\b.{0,30}\b(buy|sell|before|tomorrow|target|alert)\b",
        0.60, "Circuit limit exploitation — possible front-running or circular trading signals",
        "SEBI FUTP Regulations 2003 — Reg 4(1)"
    ),
    (
        r"\b(limited\s*(seats?|slots?|members?|spots?))\b.{0,50}\b(join|subscribe|register|enrol)\b",
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

    # Short messages with any positive signal are more likely to be forwarded scam tips
    word_count = len(text.split())
    if word_count < 25 and score > 0.1:
        score *= 1.20

    score = min(max(round(score, 4), 0.0), 1.0)
    return score, reasons, list(rules)


def _call_gemini(prompt: str) -> str:
    """Call Gemini API, preferring new google-genai SDK, falling back to old package."""
    global _gemini_client

    if _gemini_client and _gemini_client != "legacy":
        # New google-genai SDK
        response = _gemini_client.models.generate_content(
            model="gemini-1.5-pro",
            contents=prompt,
            config={
                "temperature": 0.1,
                "top_p": 0.95,
                "max_output_tokens": 1024,
            }
        )
        return response.text.strip()

    if _gemini_client == "legacy":
        # Fallback to old SDK
        import google.generativeai as genai_legacy
        model = genai_legacy.GenerativeModel(
            "gemini-1.5-pro",
            generation_config={"temperature": 0.1, "top_p": 0.95, "max_output_tokens": 1024}
        )
        response = model.generate_content(prompt)
        return response.text.strip()

    raise RuntimeError("No Gemini API client available")


def _build_forensic_prompt(transcript: str, advisor_reg_no: str, pre_score: float, pre_reasons: List[str]) -> str:
    signals_block = "\n".join(f"  • {r}" for r in pre_reasons[:12]) if pre_reasons else "  None detected"

    return f"""You are Dr. Ananya Sharma, Senior Director of Market Intelligence and Investor Protection at SEBI, with 18 years of forensic enforcement experience. You have reviewed hundreds of real fraud cases.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMUNICATION UNDER FORENSIC AUDIT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"{transcript}"

CLAIMED ADVISOR REGISTRATION: "{advisor_reg_no or 'NOT PROVIDED'}"
PRE-SCAN FORENSIC SCORE: {pre_score:.2f} / 1.00
PRE-SCAN SIGNALS DETECTED:
{signals_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORENSIC EVALUATION MANDATE — Check ALL categories, including subtle ones:

1. GUARANTEED/ASSURED RETURNS: Explicit (\"guaranteed 80%\") OR implicit (\"our team delivers consistent 40% monthly\") return promises.
2. MISLEADING ACCURACY STATS: Claiming \"95% accuracy\" or \"3-year track record\" without SEBI-verified audit certificate.
3. UNREGISTERED ADVISORY: Providing investment advice, stock tips, or research calls without citing valid SEBI RA/IA Registration Number.
4. PAID SUBSCRIPTION WITHOUT SEBI REGISTRATION: Charging subscription fees for tip services without SEBI Research Analyst (RA) authorisation.
5. OPERATOR/INSIDER SIGNALS: References to \"operator-backed\", confidential price targets, or non-public information.
6. URGENCY & SCARCITY PRESSURE: \"Limited seats\", \"only today\", \"act now\" language to force decisions.
7. PUMP-AND-DUMP SIGNALS: Viral/forward chain distribution, operator target prices, coordinated buy calls.
8. FEE STRUCTURE VIOLATIONS: Profit-sharing, pay-after-profit, undisclosed commissions.
9. LEGITIMATE MARKERS: Proper SEBI registration number cited, risk disclaimers, educational framing, referral to qualified advisors.

IMPORTANT PRECISION NOTES:
- \"Our research team identified a breakout in ZOMATO, 93% accuracy over 3 years\" → This IS a violation: unverified accuracy claim + unregistered tip = SEBI RA Reg 16(a) + Reg 3.
- \"I think TCS will outperform based on Q3 results\" → This is NOT a violation: personal opinion without paid service.
- \"Join our premium Telegram for real-time alerts\" without SEBI RA number → Definitive violation.
- Saying \"this is for educational purposes only\" while giving specific buy/sell calls simultaneously does NOT cancel the violation.

RISK_SCORE CALIBRATION:
- 0.85-1.00 → Multiple clear violations. High confidence scam.
- 0.65-0.84 → Strong violation. Even sophisticated/evasive phrasing.
- 0.45-0.64 → Suspicious. Borderline. Would escalate for regulatory review.
- 0.25-0.44 → Questionable but insufficient alone. Low risk.
- 0.05-0.24 → Legitimate. Well-disclosed. Compliant.

Respond with ONLY valid JSON (no markdown fences, no extra text):
{{"is_violation": true_or_false, "risk_score": 0.00_to_1.00, "verdict": "SEBI_VIOLATION" or "WATCH" or "COMPLIANT", "confidence": "HIGH" or "MEDIUM" or "LOW", "summary": "Precise 1-2 sentence forensic summary citing exact phrases", "reasons": ["Finding 1 with quoted text evidence", "Finding 2", "Finding 3"], "sebi_rules": ["SEBI (Research Analysts) Regulations 2014 — Reg X", "SEBI FUTP 2003 — Reg Y"], "detected_schemes": ["pump_dump", "paid_group", "ponzi", "insider_tip", "impersonation", "none"], "compliance_signals": ["any legitimate marker found or none"]}}"""


def _extract_json(raw: str) -> dict:
    """Robustly extract JSON from Gemini response."""
    # Try: bare JSON object
    m = re.search(r"(\{[\s\S]*?\})\s*$", raw.strip())
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Try: JSON in code block
    m2 = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    # Try full string
    try:
        return json.loads(raw)
    except Exception:
        pass
    return {}


def analyze_sebi_compliance(transcript: str, advisor_reg_no: str = "") -> Dict[str, Any]:
    """Multi-layer forensic SEBI compliance analysis."""

    if not transcript or not transcript.strip():
        return {
            "is_violation": False, "risk_score": 0.05, "verdict": "COMPLIANT",
            "confidence": "HIGH", "summary": "No speech or text content detected to analyze.",
            "reasons": ["No financial content present in submission."],
            "sebi_rules": [], "detected_schemes": ["none"], "compliance_signals": []
        }

    # ── Layer 1: Structural Pre-scan ─────────────────────────────────────────
    pre_score, pre_reasons, pre_rules = _run_forensic_scan(transcript)

    # ── Layer 2: Gemini Pro Deep Forensic Analysis ────────────────────────────
    if HAS_GEMINI and config.GEMINI_API_KEY:
        try:
            prompt = _build_forensic_prompt(transcript, advisor_reg_no, pre_score, pre_reasons)
            raw_text = _call_gemini(prompt)
            result_data = _extract_json(raw_text)

            if result_data:
                gemini_score = float(result_data.get("risk_score", pre_score))
                confidence = result_data.get("confidence", "MEDIUM")

                # ── Layer 3: Ensemble Calibration ─────────────────────────
                # Weight Gemini higher when it's confident, blend with structural scan for robustness
                if confidence == "HIGH":
                    final_score = 0.90 * gemini_score + 0.10 * pre_score
                elif confidence == "MEDIUM":
                    final_score = 0.75 * gemini_score + 0.25 * pre_score
                else:
                    final_score = 0.60 * gemini_score + 0.40 * pre_score

                # Unregistered or malformed advisor reg penalty
                if advisor_reg_no and advisor_reg_no.strip():
                    valid_fmt = bool(re.match(r"^in[ahz]\d{9}$", advisor_reg_no.strip().lower()))
                    if not valid_fmt:
                        final_score = min(1.0, final_score + 0.10)
                        reasons = result_data.get("reasons", [])
                        if not any("registration" in r.lower() for r in reasons):
                            reasons.append(f"Invalid/malformed SEBI registration format: '{advisor_reg_no}' — valid format is INH/INA/INZ + 9 digits")
                        result_data["reasons"] = reasons

                final_score = min(1.0, round(final_score, 4))
                is_violation = final_score >= config.SEBI_RISK_THRESHOLD
                verdict = result_data.get("verdict", "SEBI_VIOLATION" if is_violation else "COMPLIANT")
                if verdict == "WATCH" and is_violation:
                    verdict = "SEBI_VIOLATION"
                elif verdict == "WATCH" and not is_violation:
                    pass  # keep WATCH for borderline

                return {
                    "is_violation": is_violation,
                    "risk_score": final_score,
                    "verdict": verdict,
                    "confidence": confidence,
                    "summary": result_data.get("summary", "Forensic analysis completed."),
                    "reasons": result_data.get("reasons", pre_reasons),
                    "sebi_rules": result_data.get("sebi_rules", pre_rules),
                    "detected_schemes": result_data.get("detected_schemes", ["none"]),
                    "compliance_signals": result_data.get("compliance_signals", [])
                }
        except Exception as e:
            print(f"[SEBI Engine] Gemini error, using forensic rule engine: {e}")

    # ── Pure Rule Engine Fallback ─────────────────────────────────────────────
    is_violation = pre_score >= config.SEBI_RISK_THRESHOLD
    text_lower = transcript.lower()
    detected_schemes = []
    if re.search(r"\b(ponzi|pyramid|chain)\b", text_lower): detected_schemes.append("ponzi")
    if re.search(r"\b(pump|dump|operator)\b", text_lower): detected_schemes.append("pump_dump")
    if re.search(r"\b(insider|inside information)\b", text_lower): detected_schemes.append("insider_tip")
    if re.search(r"\b(telegram|whatsapp).{0,30}(vip|paid|premium)\b", text_lower): detected_schemes.append("paid_group")
    if not detected_schemes: detected_schemes = ["none"]

    verdict_label = "SEBI_VIOLATION" if is_violation else ("WATCH" if pre_score > 0.35 else "COMPLIANT")
    summary = (
        f"SEBI Violation Detected (Forensic Score: {pre_score:.0%}) — {', '.join(detected_schemes)} scheme patterns identified."
        if is_violation else
        f"Risk assessment: {pre_score:.0%}. {'Monitoring recommended.' if pre_score > 0.35 else 'Content appears compliant.'}"
    )

    return {
        "is_violation": is_violation,
        "risk_score": pre_score,
        "verdict": verdict_label,
        "confidence": "MEDIUM",
        "summary": summary,
        "reasons": pre_reasons or ["No explicit SEBI violation signals detected."],
        "sebi_rules": pre_rules,
        "detected_schemes": detected_schemes,
        "compliance_signals": []
    }
