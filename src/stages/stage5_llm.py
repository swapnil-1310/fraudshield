import json
import re
import requests
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List, Dict, Any

from src.config import get_stage_config, get_threshold

class SEBIAnalysis(BaseModel):
    claimed_advisor_name: Optional[str] = Field(default=None, description="The name of the investment advisor or entity mentioned in the transcript. Null if none found.")
    claimed_registration_number: Optional[str] = Field(default=None, description="The SEBI registration number mentioned, e.g. INA000000000. Null if none found.")
    specific_return_promises: Optional[List[str]] = Field(default_factory=list, description="Exact quotes of guaranteed or unrealistic returns promised.")
    urgency_scarcity_language: Optional[List[str]] = Field(default_factory=list, description="Exact quotes of pressure tactics, urgency, or scarcity.")
    social_proof_inflation: Optional[List[str]] = Field(default_factory=list, description="Exact quotes inflating credibility, e.g. '50,000+ members', 'trusted by top traders'.")
    paywall_push: Optional[List[str]] = Field(default_factory=list, description="Exact quotes pushing paid channels/groups, e.g. 'join premium telegram', 'DM for VIP tips'.")
    implied_returns: Optional[List[str]] = Field(default_factory=list, description="Exact quotes implying returns without explicit guarantees, e.g. 'consistent 3x outperformance', 'rocket call'.")
    credential_misrepresentation: Optional[List[str]] = Field(default_factory=list, description="Exact quotes where credentials or authority are exaggerated or fabricated.")
    fee_or_transfer_requests: Optional[List[str]] = Field(default_factory=list, description="Exact quotes requesting fund transfers, advance fees, margin, or withdrawal charges.")
    credential_or_otp_requests: Optional[List[str]] = Field(default_factory=list, description="Exact quotes requesting OTPs, passwords, MPIN, Demat credentials, or screen sharing.")
    unsupported_regulatory_claims: Optional[List[str]] = Field(default_factory=list, description="Exact quotes claiming SEBI/RBI approval or impersonating regulatory/financial institutions.")
    signal_scores: Optional[Dict[str, float]] = Field(default_factory=dict, description="Individual confidence scores (0.0-1.0) for each signal category.")
    composite_risk_score: float = Field(default=0.0, description="Weighted aggregate risk score (0.0-1.0). Higher means more likely scam.")
    prompt_injection_detected: bool = Field(default=False, description="True if an adversarial attempt to manipulate the compliance LLM was detected.")
    dpdp_pii_scrubbed_count: int = Field(default=0, description="Count of sensitive PII entities masked under the DPDP Act 2023.")
    hinglish_slang_detected: Optional[List[str]] = Field(default_factory=list, description="Indian financial scam slang terms detected (e.g. 'rocket call', 'pakka jackpot').")
    is_scam_likely: bool = Field(default=False, description="True if the content contains unregistered advice, guaranteed returns, pressure tactics, or adversarial tampering.")
    reasoning: str = Field(default="", description="A short explanation of why the content is flagged or not.")
    content_intent: str = Field(default="neutral_discussion", description="Contextual intent: 'scam_promotion', 'awareness_warning', 'neutral_discussion', or 'ambiguous'.")
    speaker_stance: str = Field(default="neutral", description="Speaker's stance towards mentioned claims: 'promoting', 'warning', 'neutral', or 'ambiguous'.")
    awareness_context_detected: bool = Field(default=False, description="True if the content is identified as scam warning, financial awareness, or fraud debunking.")
    intent_confidence: float = Field(default=1.0, description="Confidence in intent classification (0.0 - 1.0).")
    llm_used: bool = Field(default=True, description="True if LLM inference was executed; False if fallback heuristic engine was used.")
    fallback_used: bool = Field(default=False, description="True if fallback heuristic engine was used instead of primary LLM.")
    error: Optional[str] = Field(default=None, description="Underlying error message if LLM inference, connection, or parsing failed.")
    analysis_status: str = Field(default="success", description="Status of analysis: 'success', 'fallback_timeout', 'fallback_unavailable', 'fallback_parse_error', etc.")
    segments_analysis: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Timestamped segment-level semantic intent analysis.")

# Signal weights for composite scoring
SIGNAL_WEIGHTS = {
    "explicit_returns": 0.30,
    "implied_returns": 0.20,
    "urgency_scarcity": 0.15,
    "social_proof": 0.10,
    "paywall_push": 0.10,
    "credential_misrep": 0.15,
}

# Explicit mapping between LLM output signal variations and internal canonical keys
LLM_SIGNAL_KEY_MAP = {
    # explicit_returns aliases
    "explicit_returns": "explicit_returns",
    "specific_return_promises": "explicit_returns",
    "return_promises": "explicit_returns",
    "guaranteed_returns": "explicit_returns",
    "guaranteed_return": "explicit_returns",
    "explicit_return_promises": "explicit_returns",

    # implied_returns aliases
    "implied_returns": "implied_returns",
    "implied_return": "implied_returns",

    # urgency_scarcity aliases
    "urgency_scarcity": "urgency_scarcity",
    "urgency_scarcity_language": "urgency_scarcity",
    "urgency": "urgency_scarcity",
    "scarcity": "urgency_scarcity",
    "pressure_tactics": "urgency_scarcity",

    # social_proof aliases
    "social_proof": "social_proof",
    "social_proof_inflation": "social_proof",

    # paywall_push aliases (and fee/transfer requests)
    "paywall_push": "paywall_push",
    "paywall": "paywall_push",
    "fee_or_transfer_requests": "paywall_push",
    "fee_requests": "paywall_push",
    "transfer_requests": "paywall_push",
    "advance_fees": "paywall_push",

    # credential_misrep aliases (and OTP requests, regulatory impersonation)
    "credential_misrep": "credential_misrep",
    "credential_misrepresentation": "credential_misrep",
    "credentials": "credential_misrep",
    "credential_or_otp_requests": "credential_misrep",
    "otp_requests": "credential_misrep",
    "unsupported_regulatory_claims": "credential_misrep",
    "regulatory_impersonation": "credential_misrep",
}

def normalize_signal_scores(raw_scores: Any, default_all_zero: bool = True) -> Dict[str, float]:
    """
    Normalizes, maps, and validates raw LLM signal scores to canonical SIGNAL_WEIGHTS keys.
    Guarantees:
      - Valid float values clamped to [0.0, 1.0]
      - Explicit mapping from descriptive LLM keys (e.g. 'specific_return_promises') to canonical keys ('explicit_returns')
      - Safe handling of missing, unknown, malformed, non-numeric, or NaN values
      - Preservation of highest score without double-counting when multiple aliases are supplied
    """
    normalized: Dict[str, float] = {}
    if default_all_zero:
        for k in SIGNAL_WEIGHTS:
            normalized[k] = 0.0

    if not isinstance(raw_scores, dict):
        return normalized

    for key, value in raw_scores.items():
        if not isinstance(key, str):
            continue
        cleaned_key = key.strip().lower()
        canonical_key = LLM_SIGNAL_KEY_MAP.get(cleaned_key)
        if not canonical_key:
            continue

        try:
            val_float = float(value)
            if val_float != val_float:  # NaN check
                val_float = 0.0
        except (ValueError, TypeError):
            continue

        val_clamped = max(0.0, min(1.0, val_float))

        if canonical_key in normalized:
            normalized[canonical_key] = max(normalized[canonical_key], val_clamped)
        else:
            normalized[canonical_key] = val_clamped

    return normalized

# ── DPDP Act 2023 Enterprise Data Shield (Local PII Scrubbing) ───────────
PII_PATTERNS = [
    # Indian Mobile Numbers (+91 or 10-digit starting with 6, 7, 8, 9)
    (r"(?:\+91[\s-]?)?[6-9]\d{9}\b", "[MASKED_PHONE_DPDP]"),
    # Indian PAN Card (5 letters, 4 digits, 1 letter)
    (r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", "[MASKED_PAN_DPDP]"),
    # Indian Aadhaar Number (12 digits with spaces or hyphens)
    (r"\b\d{4}[\s-]\d{4}[\s-]\d{4}\b", "[MASKED_AADHAAR_DPDP]"),
    # UPI IDs (e.g. name@okhdfcbank, user@paytm, etc.)
    (r"\b[\w.-]+@(?:okaxis|okhdfcbank|oksbi|okicici|paytm|ybl|ibl|axl|apl|upi)\b", "[MASKED_UPI_ID_DPDP]"),
    # Bank Account Numbers (9-18 digits following account keywords)
    (r"(?i)(?:a/c|acc(?:ount)?(?:\s+no)?[:\s]+)(\d{9,18})", r"a/c [MASKED_BANK_ACCOUNT_DPDP]"),
    # Email Addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[MASKED_EMAIL_DPDP]"),
    # Telegram / WhatsApp Direct Invite Links
    (r"(?:https?://)?(?:t\.me|chat\.whatsapp\.com)/\S+", "[MASKED_PRIVATE_CHANNEL_LINK_DPDP]")
]

def scrub_pii_dpdp(text: str) -> tuple[str, int]:
    """
    Local Enterprise Data Shield for Digital Personal Data Protection (DPDP) Act 2023 compliance.
    Masks PII before sending transcribed text to LLMs or external processing.
    Returns (scrubbed_text, masked_entities_count).
    """
    scrubbed = text
    masked_count = 0
    for pattern, replacement in PII_PATTERNS:
        matches = len(re.findall(pattern, scrubbed))
        if matches > 0:
            masked_count += matches
            scrubbed = re.sub(pattern, replacement, scrubbed)
    return scrubbed, masked_count

# ── Adversarial "Hinglish" Slang & Coded Fraud NLP ────────────────────────
HINGLISH_SCAM_SLANG = [
    r"(?i)\brocket\s+calls?\b",
    r"(?i)\bpakka\s+jackpot\b",
    r"(?i)\bzero[\s-]loss\s+(?:setup|strategy|call)\b",
    r"(?i)\b(?:100%|hundred\s+percent)\s+(?:loss\s+)?recovery\b",
    r"(?i)\bsure[\s-]shot\s+(?:jackpot|multibagger|profit|gain)\b",
    r"(?i)\bnifty\s+blast\b",
    r"(?i)\bbanknifty\s+jackpot\b",
    r"(?i)\bkal\s+subah\s+9:?15\b",
    r"(?i)\b(?:dm|inbox|telegram)\s+(?:me\s+)?for\s+(?:vip|entry|signals|calls)\b",
    r"(?i)\b(?:10x|5x|2x|double)\s+(?:guaranteed|paisa\s+double)\b",
    r"(?i)\bloss\s+cover\s+(?:karenge|hoga)\b",
    r"(?i)\bpremium\s+(?:group|calls?|tips?)\s+join\s+karo\b",
]

def detect_hinglish_slang(text: str) -> list[str]:
    """Scans for coded Indian financial colloquialisms designed to bypass keyword filters."""
    flagged = []
    for pattern in HINGLISH_SCAM_SLANG:
        matches = re.findall(pattern, text)
        if matches:
            flagged.extend(matches)
    return list(set(flagged))

# ── Adversarial Prompt Injection Detection ───────────────────────────────
INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(?:all\s+)?(?:prior|previous|above|system)\s+(?:instructions|prompts|rules|commands)",
    r"(?i)\bdisregard\s+(?:all\s+)?(?:prior|previous|above|system|guidelines)",
    r"(?i)\byou\s+are\s+now\s+(?:in|acting\s+as|a)\s+(?:maintenance|developer|compliance|safe|unrestricted)\s+mode",
    r"(?i)\boutput\s+(?:only\s+)?\{\s*[\"']is_scam_likely[\"']\s*:\s*false",
    r"(?i)\bmark\s+(?:this|me|content)\s+as\s+(?:compliant|safe|verified|not\s+a\s+scam)",
    r"(?i)\bsystem\s+prompt\s*:\s*override",
    r"(?i)\bdo\s+not\s+flag\s+(?:this|as\s+scam)",
    r"(?i)\bDAN\s+mode\b|\bjailbreak\b",
]

def scan_for_prompt_injection(text: str) -> tuple[bool, Optional[str]]:
    """Detects adversarial jailbreak phrases designed to manipulate compliance checks."""
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return True, match.group(0)
    return False, None

def compute_composite_score(signal_scores: dict, normalize: bool = True) -> float:
    """
    Weighted aggregate of all signal scores.
    If normalize=True, signal_scores is first mapped through normalize_signal_scores (without zeroing missing keys),
    allowing callers to pass raw LLM keys or canonical keys interchangeably.
    """
    if not isinstance(signal_scores, dict):
        return 0.0

    if normalize:
        scores = normalize_signal_scores(signal_scores, default_all_zero=False)
    else:
        scores = signal_scores

    total = 0.0
    weight_sum = 0.0
    for key, weight in SIGNAL_WEIGHTS.items():
        if key in scores:
            total += scores[key] * weight
            weight_sum += weight
    if weight_sum > 0:
        return round(min(1.0, total / weight_sum), 4)
    return 0.0


def clean_and_repair_json_str(text: str) -> str:
    """Performs deterministic syntax cleanups on malformed LLM JSON strings."""
    # 1. Replace smart/curly quotes
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    # 2. Fix trailing commas before } or ]
    text = re.sub(r",\s*([\}\]])", r"\1", text)
    # 3. Replace unquoted python literals
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b", "null", text)
    return text


def extract_json_payload(content: str) -> dict:
    """
    Extracts and parses JSON from text, robustly handling:
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Surrounding commentary or explanatory text
    - Trailing commas, smart quotes, and Python literals
    - Truncated closing braces / brackets
    """
    if not content or not isinstance(content, str):
        raise json.JSONDecodeError("Empty or non-string content", str(content), 0)

    raw_text = content.strip()

    # Step 1: If markdown fences exist, extract the fenced block containing JSON
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    fence_matches = re.findall(fence_pattern, raw_text)
    candidate_text = raw_text
    if fence_matches:
        for block in fence_matches:
            if "{" in block and "}" in block:
                candidate_text = block.strip()
                break
        else:
            candidate_text = fence_matches[0].strip()
    else:
        # Strip unclosed opening fence if truncated
        candidate_text = re.sub(r"^```(?:json)?\s*", "", candidate_text).strip()

    # Step 2: Slice from first '{' to last '}'
    start_brace = candidate_text.find("{")
    end_brace = candidate_text.rfind("}")
    if start_brace != -1:
        if end_brace != -1 and end_brace > start_brace:
            open_count = candidate_text[start_brace:].count("{")
            close_count = candidate_text[start_brace:].count("}")
            if open_count <= close_count:
                candidate_text = candidate_text[start_brace:end_brace + 1]
            else:
                # JSON is truncated with unclosed braces; preserve full content for repair
                candidate_text = candidate_text[start_brace:]
        else:
            candidate_text = candidate_text[start_brace:]

    # Step 3: Try standard json.loads
    try:
        return json.loads(candidate_text)
    except json.JSONDecodeError:
        pass

    # Step 4: Apply deterministic string repairs
    repaired = clean_and_repair_json_str(candidate_text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Step 5: Handle truncated JSON: if missing closing braces/brackets/quotes
    if repaired.startswith("{"):
        trial = repaired
        quotes_count = len(re.findall(r'(?<!\\)"', trial))
        if quotes_count % 2 != 0:
            trial += '"'
        open_curly = trial.count("{") - trial.count("}")
        open_square = trial.count("[") - trial.count("]")
        if open_square > 0:
            trial += "]" * open_square
        if open_curly > 0:
            trial += "}" * open_curly
        trial = clean_and_repair_json_str(trial)
        try:
            return json.loads(trial)
        except json.JSONDecodeError:
            pass

    # Step 6: If local repairs fail, raise original JSONDecodeError for repair prompt or fallback
    return json.loads(candidate_text)



# ── Contextual Intent & Discourse Stance NLP ──────────────────────────────
AWARENESS_WARNING_PATTERNS = [
    # English warning frames
    r"(?i)\b(?:scam|fraud|phishing|cyber|investor|security|regulatory|fraudulent)\s+(?:alerts?|warnings?|advisories|advisory)\b",
    r"(?i)\b(?:alert|warning|advisory)\s*:\s*(?:beware|caution|do\s+not|never|fake|scam|fraud|unregistered)\b",
    r"(?i)\b(?:beware|caution|be\s+careful|stay\s+safe|protect\s+yourself)\b",
    r"(?i)\b(?:don'?t|do\s+not|never)\s+fall\s+for\b",
    r"(?i)\bwatch\s+out\s+for\s+(?:fake|fraudulent|unauthorized|illegal|scam)\b",
    r"(?i)\b(?:investor\s+(?:warning|advisory|awareness)|public\s+advisory)\b",
    r"(?i)\b(?:fake|fraudulent|unauthorized|illegal|unregistered)\s+(?:schemes?|operators?|advisors?|channels?|groups?|apps?|entities)\b",
    r"(?i)\b(?:scammers?|fraudsters?|cheaters?|thugs?|cyber\s+criminals?)\b",
    r"(?i)\b(?:report|complain|file\s+a\s+complaint)\s+(?:to|against|on)\s+(?:sebi|cyber\s*crime|police|scores|authorities)\b",
    r"(?i)\b(?:cyber\s*crime\s*(?:helpline|portal)|1930|scores\s+portal|sebi\s+advisory)\b",
    r"(?i)\b(?:debunk|debunking|exposed|reality\s+of|truth\s+behind)\b",
    # Sarcastic / ironic / satirical scam debunking frames
    r"(?i)\bwhat\s+could\s+(?:possibly\s+)?go\s+wrong\b",
    r"(?i)\b(?:totally|definitely)\s+(?:legit|not\s+a\s+scam|safe|foolproof)\b",
    r"(?i)\byeah\s*,\s*right\b",
    r"(?i)\bbecause\s+(?:strangers|telegram\s+traders)\s+love\s+giving\s+free\s+money\b",
    r"(?i)\b(?:loscar\s+movie|लोस्कर\s*मूवी|लोस्कर)\b",
    r"(?i)\b(?:beggar\s+ban\s+ja|बगर\s*बन\s*जा|भिखारी\s*बन\s*जा)\b",
    r"(?i)\b(?:blockbuster\s+scam|ब्लोक\s*बस्टर\s*स्क[ा|ै]म|ब्लॉक\s*बस्टर\s*स्क[ा|ै]म)\b",
    r"(?i)\b(?:the\s+villain|याने\s+की\s+दे?\s*विलन|दे\s*विलन|द\s*विलन)\b",
    r"(?i)\b(?:bakra\s+investors?|भकरा\s+इन्वेस्टर्स|बकरा\s+इन्वेस्टर)\b",
    r"(?i)\b(?:artificially\s+create\s+demand|misleading\s+advertisements?)\b",
    r"(?i)\b(?:registered\s+financial\s+advisors?|advice\s+only\s+from\s+registered)\b",
    # Hinglish & Hindi awareness & statutory warning frames
    r"(?i)\b(?:savdhaan|satark|bachke)\s+rahein?\b",
    r"(?i)\b(?:dhokhadhadi|thagi|froud|scam)\s+se\s+bache(?:in)?\b",
    r"(?i)\b(?:yeh|ye)\s+(?:sab\s+)?(?:scam|fraud|dhokha)\s+hai\b",
    r"(?i)\b(?:स्क[ा|ै]म|धोखा|फ्रॉड)\s+है\s+ये\b",
    r"(?i)\b(?:kisi\s+ke\s+)?jhaanse\s+mein\s+na\s+aaye(?:in)?\b",
    r"(?i)\b(?:cyber\s*crime|sebi)\s+ko\s+report\s+kare(?:in)?\b",
    r"(?i)\bpaise\s+mat\s+do\b",
    r"(?i)\bkabhi\s+mat\s+dena\b",
    r"(?i)\b(?:loot|thag)\s+rahe\s+hain\b",
    r"(?i)\bfree\s+mein\s+paisa\s+kaun\s+deta\s+hai\b",
    r"(?i)\bkoi\s+(?:bhi\s+)?free\s+mein\s+crorepati\s+nahi\s+banata\b",
    r"(?i)\b(?:soch\s*kar\s*samajh\s*kar|सोच\s*कर\s*समझ\s*कर|सोचकर[,\s]+समझकर|क्सकर[,\s]+समच्कर)\b",
    r"(?i)\b(?:niveshako\s+ke\s+hit\s+mein\s+jaari|निवेश[ि|क]*कों\s*के\s*हित\s*में\s*जारी|हित्मचारी|हित\s*में\s*जारी)\b",
    r"(?i)\b(?:nse\s+dwara|अनेसी\s+द्वारा|एनएसई\s+द्वारा|bse\s+dwara|sebi\s+dwara)\b",
]

PROHIBITION_PATTERNS = [
    # English prohibitive markers
    r"(?i)\b(?:never|do\s+not|don'?t|avoid|refuse\s+to|beware\s+of|stop)\s+(?:ever\s+)?(?:share|transfer|send|pay|deposit|give|provide|install|click|trust)\b",
    r"(?i)\b(?:never|do\s+not|don'?t)\s+(?:share|give|disclose)\s+(?:your\s+)?(?:otp|password|mpin|pin|credentials)\b",
    r"(?i)\b(?:never|do\s+not|don'?t)\s+(?:transfer|send|pay)\s+(?:any\s+)?(?:money|funds|fees?|charges?|margin)\b",
    r"(?i)\b(?:will|should)\s+never\s+(?:ask|demand|promise|guarantee|share|transfer|pay)\b",
    # Hinglish prohibitive markers
    r"(?i)\b(?:kabhi\s+(?:bhi\s+)?|kisi\s+ko\s+)?(?:mat\s+|na\s+)(?:share|dena|bhejna|transfer|karna|karo)\b",
    r"(?i)\b(?:otp|password|paise|fees?)\s+(?:kisi\s+ko\s+)?mat\s+(?:do|bhejo|share\s+karo)\b",
    r"(?i)\bmat\s+(?:karna|karo|bhejo|do|dena|kariye)\b",
    r"(?i)\bkabhi\s+(?:bhi\s+)?(?:guarantee|otp|paise)\s+nahi\s+(?:mangte|dete)\b",
]

SCAM_ATTRIBUTION_PATTERNS = [
    r"(?i)\b(?:scammers?|fraudsters?|fake\s+\w+|thugs?|cheaters?)\s+(?:[\w\s]{0,30})?(?:promise|promising|offer|offering|ask|asking|demand|demanding|claim|claiming|lure|luring|tell|telling)\b",
    r"(?i)\b(?:promises?|claims?|tactics?|stories|tricks?)\s+(?:made\s+|used\s+)?by\s+(?:scammers?|fraudsters?|fake\s+\w+)\b",
    r"(?i)\bclaims?\s+like\s+.*?(?:are\s+fraud|is\s+a\s+scam)\b",
    r"(?i)\bthey\s+(?:claim|promise|say|lure|ask|demand)\b",
    r"(?i)\b(?:victim|victims|person|investors?|people)\s+(?:reported|complained|lost\s+money|were\s+asked|fell\s+for)\b",
    r"(?i)\b(?:reported|complained)\s+(?:to|against)\s+(?:sebi|police|cyber\s*crime|1930)\b",
    r"(?i)\bsomeone\s+tried\s+to\s+scam\b",
    # Quoted tip / third-party inquiry frames
    r"(?i)\b(?:i\s+seen|i\s+saw|अई\s+सीन|मैंने\s+देखा|dekha\s+hai)\b",
    r"(?i)\b(?:multibagger\s+stock\s+ka\s+video|मुल्टी\s+बागर\s+स्टोक\s+काव\s+भीटियो|स्टॉक\s*(?:का\s*)?वीडियो)\b",
    r"(?i)\b(?:triple\s+returns|प्रपल\s+रिटान्स|तीन\s+गुना)\b",
    r"(?i)\b(?:i'?ll\s+invest\s+no\?|आलिन्वेस\s+नो\?|invest\s+karu\?)\b",
    r"(?i)\b(?:saw\s+a\s+video|forwarded\s+(?:a\s+)?video|received\s+a\s+tip|got\s+a\s+message)\b",
    r"(?i)\b(?:should\s+i\s+invest|shall\s+i\s+invest|shall\s+i\s+buy|is\s+this\s+legit\??|is\s+this\s+safe\??)\b",
]

PROTECTIVE_URGENCY_PATTERNS = [
    r"(?i)\b(?:report|complain|file\s+a\s+complaint|block\s+(?:the\s+)?(?:account|number|caller|card)|change\s+password|call\s+(?:1930|helpline|police|cyber|sebi))\s+.*?\b(?:immediately|now|urgently?)\b",
    r"(?i)\b(?:immediately|urgently)\s+(?:report|call|contact\s+sebi|contact\s+cyber\s*crime|block|complain)\b",
    r"(?i)\bturant\s+(?:report|call|complaint)\b",
]

PROMOTIONAL_CTA_PATTERNS = [
    r"(?i)\b(?:join|enter)\s+(?:my|our)\s+(?:vip|premium|paid|exclusive)\s+(?:channel|group|telegram|whatsapp)\b",
    r"(?i)\b(?:dm|inbox|message)\s+(?:me|us)\s+(?:for|to\s+get)\s+(?:vip|entry|signals?|calls?|tips?|jackpot)\b",
    r"(?i)\b(?:send|transfer|pay|deposit)\s+(?:money|funds?|charges?|margin|fees?|advance)\s+to\s+(?:my|our|this)\s+(?:upi|account|wallet|number)\b",
    r"(?i)\b(?:i|we)\s+guarantee\s+(?:\d+%\s+|assured\s+|fixed\s+)?(?:returns?|profit|gains?)\b",
    r"(?i)\b(?:i|we)\s+(?:will\s+)?double\s+your\s+money\b",
    r"(?i)\b(?:i|we)\s+(?:am|are)\s+offering\s+100%\s+loss\s+recovery\b",
    r"(?i)\bshare\s+your\s+otp\s+with\s+(?:me|our\s+executive|us)\b",
    r"(?i)\b(?:install|download)\s+(?:anydesk|teamviewer)\s+(?:so|for)\s+(?:we|us|our\s+team)\b",
    r"(?i)\bpremium\s+(?:group|calls?|tips?)\s+join\s+karo\b",
    r"(?i)\b(?:dm|inbox|telegram)\s+(?:me\s+)?for\s+(?:vip|entry|signals|calls)\b",
]

def find_enclosing_clause(text: str, start_pos: int, end_pos: int) -> str:
    """Finds the sentence enclosing a specific match position."""
    before = text[:start_pos]
    boundary_before = max(
        before.rfind("."), before.rfind("!"), before.rfind("?"),
        before.rfind("\n"), before.rfind(";")
    )
    start = boundary_before + 1 if boundary_before != -1 else 0

    after = text[end_pos:]
    m_boundary_after = re.search(r"[.!?\n;]", after)
    if m_boundary_after:
        end = end_pos + m_boundary_after.start()
    else:
        end = len(text)

    return text[start:end].strip()

def is_clause_prohibitive_or_attributed(clause: str) -> bool:
    """Returns True if the sentence/clause contains a prohibitive warning, awareness alert, or attributes scam behavior to third parties."""
    for pat in PROHIBITION_PATTERNS + SCAM_ATTRIBUTION_PATTERNS + AWARENESS_WARNING_PATTERNS:
        if re.search(pat, clause):
            return True
    return False

def is_clause_protective_urgency(clause: str) -> bool:
    """Returns True if an urgency word is used in a protective/reporting context rather than investment pressure."""
    for pat in PROTECTIVE_URGENCY_PATTERNS:
        if re.search(pat, clause):
            return True
    return False

def determine_content_intent(
    text: str,
    promotional_cta_found: list,
    awareness_markers_found: list,
    prohibitions_found: list,
    active_quotes: dict,
    slang_found: list,
    awareness_examples: list
) -> tuple[str, str, bool, float]:
    """
    Classifies contextual intent and speaker stance.
    Returns: (content_intent, speaker_stance, awareness_context_detected, intent_confidence)
    Categories:
      - 'scam_promotion': Speaker actively solicits, offers, or promises scam schemes/services.
      - 'awareness_warning': Speaker warns against fraud, advises caution, or debunks scams.
      - 'neutral_discussion': Standard financial education, market review, fundamentals.
      - 'ambiguous': Discussion of suspicious claims without clear promotion or clear warning.
    """
    has_active_returns = bool(active_quotes.get("specific_return_promises"))
    has_active_fees = bool(active_quotes.get("fee_or_transfer_requests"))
    has_active_otps = bool(active_quotes.get("credential_or_otp_requests"))
    has_active_paywalls = bool(active_quotes.get("paywall_push"))
    has_active_reg = bool(active_quotes.get("unsupported_regulatory_claims"))
    has_active_urgency = bool(active_quotes.get("urgency_scarcity_language"))

    has_promotional_cta = bool(promotional_cta_found)
    has_awareness_signals = bool(awareness_markers_found or prohibitions_found or awareness_examples)

    # 1. Genuine scam promotion: direct promotional calls to action, or unmitigated scam demands/guarantees
    if has_promotional_cta or (has_active_returns and (has_active_fees or has_active_otps or has_active_paywalls or has_active_urgency)):
        return "scam_promotion", "promoting", False, 0.95

    if (has_active_fees or has_active_otps or has_active_reg) and not has_awareness_signals:
        return "scam_promotion", "promoting", False, 0.90

    # 2. Financial awareness warnings / educational caution (when not promoting a scheme)
    if has_awareness_signals and not has_promotional_cta:
        return "awareness_warning", "warning", True, 0.95

    # 3. Active return promises or claims
    if has_active_returns:
        is_third_party_discussion = bool(re.search(
            r"(?i)\b(?:some\s+\w+|certain\s+\w+|third[\s-]party|proprietary|syndicates?|firms?|desks?|platforms?|traders?)\s+(?:claim|advertise|report|allege)\b",
            text
        )) or bool(re.search(
            r"(?i)\b(?:without\s+recommending|for\s+review|reviewing\s+how|analyzing\s+how)\b",
            text
        ))
        has_direct_guarantee = bool(re.search(
            r"(?i)\b(?:guaranteed|assured|sure[\s-]shot|paisa\s*double|zero[\s-]risk|100%)\b",
            text
        ))
        if is_third_party_discussion and not has_direct_guarantee:
            return "ambiguous", "ambiguous", False, 0.75

        if not has_awareness_signals:
            return "scam_promotion", "promoting", False, 0.90

    # 4. Implied returns, urgency tactics, or ambiguous financial claims
    has_any_implied = bool(active_quotes.get("implied_returns") or slang_found or active_quotes.get("urgency_scarcity_language"))
    if has_any_implied and not has_awareness_signals and not has_promotional_cta:
        if active_quotes.get("urgency_scarcity_language"):
            return "scam_promotion", "promoting", False, 0.85
        return "ambiguous", "ambiguous", False, 0.70

    # 5. Neutral financial discussion
    return "neutral_discussion", "neutral", False, 0.95


def heuristic_sebi_analysis(text: str, pii_count: int, slang_found: list, injection_found: bool, injection_match: Optional[str]) -> dict:
    """Fast deterministic SEBI heuristic rule engine (sub-millisecond evaluation with contextual stance modeling)."""
    scores = {
        "explicit_returns": 0.0,
        "implied_returns": 0.0,
        "urgency_scarcity": 0.0,
        "social_proof": 0.0,
        "paywall_push": 0.0,
        "credential_misrep": 0.0
    }
    quotes = {
        "specific_return_promises": [],
        "urgency_scarcity_language": [],
        "social_proof_inflation": [],
        "paywall_push": [],
        "implied_returns": [],
        "credential_misrepresentation": [],
        "fee_or_transfer_requests": [],
        "credential_or_otp_requests": [],
        "unsupported_regulatory_claims": []
    }
    awareness_examples = []

    # 1. Detect awareness markers, prohibitions, and promotional CTAs across document
    awareness_markers = []
    for pat in AWARENESS_WARNING_PATTERNS:
        m = re.findall(pat, text)
        if m:
            awareness_markers.extend(m)

    prohibitions = []
    for pat in PROHIBITION_PATTERNS:
        m = re.findall(pat, text)
        if m:
            prohibitions.extend(m)

    promotional_ctas = []
    for pat in PROMOTIONAL_CTA_PATTERNS:
        m = re.findall(pat, text)
        if m:
            promotional_ctas.extend(m)

    # 2. Check explicit returns (including natural-language verb forms and assured return percentages)
    explicit_return_patterns = [
        r"(?i)\b\d+%\s*(?:guaranteed|assured|promised)\b",
        r"(?i)\b\d+%\s*(?:guaranteed|assured|promised)\s*(?:returns?|profit|monthly|daily|annual|yearly|weekly)\b",
        r"(?i)\b(?:guaranteed|assured|promised|consistent)\s+\d+%\s*(?:returns?|profit|gains?|annual|monthly|yearly|weekly)?\b",
        r"(?i)\b(?:claim(?:s|ing)?|promis(?:es|ing)|guarantee(?:s|d|ing)?|offer(?:s|ing)?)\s+(?:consistent\s+)?\d+%\s*(?:annual|yearly|monthly|daily|weekly)?\s*(?:returns?|profit|gains?)\b",
        r"(?i)\b100%\s*(?:guaranteed|sure|loss\s+recovery)\b",
        r"(?i)\bguarantee(?:s|d|ing)?\s+(?:a\s+)?(?:fixed\s+|assured\s+)?(?:return|returns|profit|gains?)\b",
        r"(?i)\bguarantee(?:s|d)?\s+returns?\s+(?:of\s+)?(?:more\s+than\s+|up\s+to\s+)?\d+%",
        r"(?i)\b(?:assured|guaranteed|guaranteeing|guarantees?)\s+(?:returns?|profit|gains?)\b",
        r"(?i)\bpaisa\s*double\b",
        r"(?i)\bsure[\s-]shot\s*profit\b",
        r"(?i)\b(?:triple\s+returns?|3x\s+returns?|प्रपल\s+रिटान्स|तीन\s+गुना|चार\s+गुना)\b",
    ]
    for pat in explicit_return_patterns:
        for m in re.finditer(pat, text):
            match_str = m.group(0)
            clause = find_enclosing_clause(text, m.start(), m.end())
            if is_clause_prohibitive_or_attributed(clause):
                awareness_examples.append(match_str)
            elif re.search(r"(?i)\b(?:generated|delivered|achieved|historical|over\s+the\s+past|past\s+\d+\s+years?|in\s+the\s+past|no\s+guarantee)\b", clause):
                # Historical performance disclosure or standard disclaimer, not a forward guarantee
                pass
            else:
                quotes["specific_return_promises"].append(match_str)
                scores["explicit_returns"] = max(scores["explicit_returns"], 0.95)

    # 3. Check fee demands / money transfer requests
    fee_transfer_patterns = [
        r"(?i)\b(?:pay|send|transfer|deposit)\s+(?:the\s+)?(?:fee|fees|charges?|margin|advance|registration\s+charges?|deposit|funds?|money|crypto|usdt)\b",
        r"(?i)\b(?:fee|charges?)\s+(?:to\s+)?(?:withdraw|unlock|release)\s+(?:profit|funds?|gains?|money)\b",
        r"(?i)\btransfer\s+(?:money|funds?)\s+to\s+(?:upi|account|wallet|our\s+account)\b",
        r"(?i)\badvance\s+(?:payment|fee|charges?|margin)\b",
        r"(?i)\bprocessing\s+fee\b",
    ]
    for pat in fee_transfer_patterns:
        for m in re.finditer(pat, text):
            match_str = m.group(0)
            clause = find_enclosing_clause(text, m.start(), m.end())
            if is_clause_prohibitive_or_attributed(clause):
                awareness_examples.append(match_str)
            else:
                quotes["fee_or_transfer_requests"].append(match_str)
                scores["paywall_push"] = max(scores["paywall_push"], 0.90)

    # 4. Check credential, OTP, or remote screen access requests
    credential_otp_patterns = [
        r"(?i)\b(?:share|send|tell|give|enter)\s+(?:your\s+)?(?:otp|one[\s-]time\s+password|mpin|pin|password|demat\s+password|login\s+credentials|login\s+details)\b",
        r"(?i)\b(?:install|download)\s+(?:anydesk|teamviewer|quicksupport|rustdesk|remote\s+desktop)\b",
        r"(?i)\bshare\s+(?:your\s+)?(?:screen|remote\s+access)\b",
    ]
    for pat in credential_otp_patterns:
        for m in re.finditer(pat, text):
            match_str = m.group(0)
            clause = find_enclosing_clause(text, m.start(), m.end())
            if is_clause_prohibitive_or_attributed(clause):
                awareness_examples.append(match_str)
            else:
                quotes["credential_or_otp_requests"].append(match_str)
                scores["credential_misrep"] = max(scores["credential_misrep"], 0.95)

    # 5. Check unsupported regulatory claims & impersonation of authorities
    regulatory_impersonation_patterns = [
        r"(?i)\b(?:calling|speaking)\s+from\s+(?:sebi|rbi|nse|bse|income\s+tax)\b",
        r"(?i)\b(?:sebi|rbi|government|govt)\s+(?:approved|guaranteed|certified|backed)\s+(?:returns?|profit|scheme|fund|plan)\b",
        r"(?i)\bauthorized\s+by\s+(?:sebi|rbi)\s+to\s+(?:guarantee|promise|manage)\b",
        r"(?i)\bofficial\s+(?:sebi|rbi)\s+(?:officer|regulator|representative)\b",
    ]
    for pat in regulatory_impersonation_patterns:
        for m in re.finditer(pat, text):
            match_str = m.group(0)
            clause = find_enclosing_clause(text, m.start(), m.end())
            if is_clause_prohibitive_or_attributed(clause):
                awareness_examples.append(match_str)
            else:
                quotes["unsupported_regulatory_claims"].append(match_str)
                scores["credential_misrep"] = max(scores["credential_misrep"], 0.90)

    # 6. Check urgency & scarcity pressure tactics
    urgency_patterns = [
        r"(?i)\bonly\s*\d+\s*(?:seats?|slots?|spots?|members?)\b",
        r"(?i)\bkal\s*subah\s*9:?15\b",
        r"(?i)\bclosing\s*soon\b",
        r"(?i)\blast\s*chance\b",
        r"(?i)\blimited\s*time\b",
        r"(?i)\bhurry\s*up\b",
        r"(?i)\burg(?:ent|ently)\b",
        r"(?i)\bcall\s+now\b",
        r"(?i)\bact\s+now\b",
        r"(?i)\bbuy\s+now\b",
        r"(?i)\bimmediate(?:ly)?\b",
        r"(?i)\bdon'?t\s+wait\b",
    ]
    for pat in urgency_patterns:
        for m in re.finditer(pat, text):
            match_str = m.group(0)
            clause = find_enclosing_clause(text, m.start(), m.end())
            if is_clause_protective_urgency(clause) or is_clause_prohibitive_or_attributed(clause):
                awareness_examples.append(match_str)
            else:
                quotes["urgency_scarcity_language"].append(match_str)
                scores["urgency_scarcity"] = max(scores["urgency_scarcity"], 0.85)

    # 7. Check paywall push
    paywall_patterns = [
        r"(?i)\b(?:join\s*(?:vip|premium|paid|free)?\s*(?:telegram|whatsapp|group|channel)|dm\s*for\s*(?:vip|entry|tips)|\[MASKED_PRIVATE_CHANNEL_LINK_DPDP\]|t\.me/\S+|chat\.whatsapp\.com/\S+)\b"
    ]
    for pat in paywall_patterns:
        for m in re.finditer(pat, text):
            match_str = m.group(0)
            clause = find_enclosing_clause(text, m.start(), m.end())
            if is_clause_prohibitive_or_attributed(clause):
                awareness_examples.append(match_str)
            else:
                quotes["paywall_push"].append(match_str)
                scores["paywall_push"] = max(scores["paywall_push"], 0.90)

    # 8. Check implied returns & slang
    active_slang = []
    if slang_found:
        for s in slang_found:
            is_slang_awareness = False
            for m in re.finditer(re.escape(s), text, re.IGNORECASE):
                clause = find_enclosing_clause(text, m.start(), m.end())
                if is_clause_prohibitive_or_attributed(clause) or bool(awareness_markers):
                    is_slang_awareness = True
                    break
            if is_slang_awareness:
                awareness_examples.append(f"[Hinglish Slang in Awareness Context]: '{s}'")
            else:
                active_slang.append(s)
                scores["implied_returns"] = max(scores["implied_returns"], 0.85)
                quotes["implied_returns"].append(f"[Hinglish Slang]: '{s}'")

    for m in re.finditer(r"(?i)\b(?:rocket\s*calls?|pakka\s*jackpot|zero-loss|multibagger|nifty\s*blast|10x|5x)\b", text):
        match_str = m.group(0)
        clause = find_enclosing_clause(text, m.start(), m.end())
        if is_clause_prohibitive_or_attributed(clause) or bool(awareness_markers):
            awareness_examples.append(match_str)
        else:
            quotes["implied_returns"].append(match_str)
            scores["implied_returns"] = max(scores["implied_returns"], 0.80)

    # 9. Check credentials
    for m in re.finditer(r"(?i)\b(?:sebi\s*(?:registered|approved|certified|advisor)|ina[0-9]{8,14}|inh[0-9]{8,14})\b", text):
        match_str = m.group(0)
        clause = find_enclosing_clause(text, m.start(), m.end())
        if is_clause_prohibitive_or_attributed(clause):
            awareness_examples.append(match_str)
        else:
            quotes["credential_misrepresentation"].append(match_str)
            scores["credential_misrep"] = max(scores["credential_misrep"], 0.70)

    claimed_advisor = None
    claimed_number = None
    m_num = re.search(r"\b(IN[A-Za-z]{1,3}[0-9]{4,12})\b", text)
    if m_num:
        claimed_number = m_num.group(1).upper()

    advisor_patterns = [
        r"(?i)\bI(?:'m| am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})[,\s]+(?:sebi|registered|certified|advisor|analyst)",
        r"(?i)\bmy\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})[,\s]+(?:and\s+I(?:'m| am)\s+(?:your\s+)?(?:sebi|certified|financial|investment|stock)?\s*(?:advisor|analyst|expert)|[,\s]+(?:sebi|registered|certified|advisor|analyst))",
        r"(?i)\bthis\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})[,\s]+(?:from\s+[A-Za-z\s]+[,\s]+)?(?:sebi|registered|certified|advisor|analyst)",
        r"(?i)\bnamskar[,\s]+(?:main|mera\s+naam)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:hoon|hun|hai)[,\s]+(?:sebi|certified|financial|advisor)",
    ]
    for pat in advisor_patterns:
        m_adv = re.search(pat, text)
        if m_adv:
            claimed_advisor = m_adv.group(1).strip()
            break

    # Clean & deduplicate evidence quotes
    for q_key in quotes:
        quotes[q_key] = list(dict.fromkeys(quotes[q_key]))
    awareness_examples = list(dict.fromkeys(awareness_examples))

    # 10. Classify Intent & Discourse Stance
    content_intent, speaker_stance, awareness_detected, confidence = determine_content_intent(
        text=text,
        promotional_cta_found=promotional_ctas,
        awareness_markers_found=awareness_markers,
        prohibitions_found=prohibitions,
        active_quotes=quotes,
        slang_found=active_slang,
        awareness_examples=awareness_examples
    )

    if injection_found:
        content_intent = "scam_promotion"
        speaker_stance = "promoting"
        awareness_detected = False

    # 11. Final Risk & Verdict Calibration based on intent
    if content_intent == "awareness_warning":
        scores = {k: 0.0 for k in scores}
        composite = 0.0
        is_scam = False
        reasoning = "Financial awareness advisory detected warning against fraudulent schemes, phishing, and scam tactics."
        # Clear quotes from speaker violations so downstream does not treat them as violations committed by the speaker
        quotes = {k: [] for k in quotes}

    elif content_intent == "neutral_discussion":
        scores = {k: 0.0 for k in scores}
        composite = 0.0
        is_scam = False
        reasoning = "General commentary or financial education with no high-risk SEBI violations flagged."
        quotes = {k: [] for k in quotes}

    elif content_intent == "ambiguous":
        composite = 0.35
        is_scam = False
        reasoning = "Financial claims discussed in an ambiguous or unverified context without explicit scam solicitation or clear regulatory warning."

    else:  # scam_promotion
        composite = compute_composite_score(scores, normalize=False)
        scam_thresh = get_threshold("scam_composite_threshold", 0.35)
        is_scam = (
            composite >= scam_thresh
            or bool(active_slang or injection_found)
            or bool(quotes["specific_return_promises"])
            or bool(quotes["paywall_push"])
            or bool(quotes["fee_or_transfer_requests"])
            or bool(quotes["credential_or_otp_requests"])
            or bool(quotes["unsupported_regulatory_claims"])
        )
        if is_scam:
            max_signal = max(scores.values()) if scores else 0.0
            composite = max(composite, scam_thresh, round(max_signal * 0.85, 4))

        reasoning_parts = []
        if quotes["specific_return_promises"]:
            reasoning_parts.append("Guaranteed return promises detected")
        if active_slang:
            reasoning_parts.append(f"Coded Hinglish fraud slang detected ({', '.join(active_slang)})")
        if quotes["paywall_push"]:
            reasoning_parts.append("Unregistered VIP group / paywall push detected")
        if quotes["fee_or_transfer_requests"]:
            reasoning_parts.append("Suspicious fee demand / money transfer request detected")
        if quotes["credential_or_otp_requests"]:
            reasoning_parts.append("Sensitive credential / OTP request detected")
        if quotes["unsupported_regulatory_claims"]:
            reasoning_parts.append("Unsupported regulatory claim or authority impersonation detected")
        if quotes["urgency_scarcity_language"]:
            reasoning_parts.append("Manufactured urgency tactics detected")
        if not reasoning_parts:
            reasoning_parts.append("Potential unverified financial promotion flagged")

        reasoning = "; ".join(reasoning_parts) + "."

    if injection_found:
        scores["credential_misrep"] = 1.0
        is_scam = True
        composite = 1.0
        reasoning = f"CRITICAL: Adversarial prompt injection attempt ('{injection_match}'). " + reasoning

    return {
        "claimed_advisor_name": claimed_advisor,
        "claimed_registration_number": claimed_number,
        "specific_return_promises": quotes["specific_return_promises"],
        "urgency_scarcity_language": quotes["urgency_scarcity_language"],
        "social_proof_inflation": quotes["social_proof_inflation"],
        "paywall_push": quotes["paywall_push"],
        "implied_returns": quotes["implied_returns"],
        "credential_misrepresentation": quotes["credential_misrepresentation"],
        "fee_or_transfer_requests": quotes["fee_or_transfer_requests"],
        "credential_or_otp_requests": quotes["credential_or_otp_requests"],
        "unsupported_regulatory_claims": quotes["unsupported_regulatory_claims"],
        "signal_scores": scores,
        "composite_risk_score": composite,
        "prompt_injection_detected": injection_found,
        "dpdp_pii_scrubbed_count": pii_count,
        "hinglish_slang_detected": active_slang if content_intent == "scam_promotion" else [],
        "is_scam_likely": is_scam,
        "reasoning": reasoning,
        "content_intent": content_intent,
        "speaker_stance": speaker_stance,
        "awareness_context_detected": awareness_detected,
        "intent_confidence": confidence,
        "llm_used": False,
        "fallback_used": True,
        "error": None,
        "analysis_status": "fallback",
    }


def group_transcript_segments(
    segments: Optional[List[Dict[str, Any]]],
    target_duration: float = 25.0,
    max_duration: float = 35.0,
    max_pause: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Groups granular Whisper speech segments into meaningful discourse units
    of approximately 15-30s, respecting natural speech pauses and scene transitions.
    """
    if not segments:
        return []

    sorted_segs = sorted(
        [s for s in segments if s.get("text", "").strip()],
        key=lambda x: float(x.get("start", 0.0))
    )
    if not sorted_segs:
        return []

    chunks = []
    curr_start = float(sorted_segs[0].get("start", 0.0))
    curr_end = float(sorted_segs[0].get("end", 0.0))
    curr_texts = [sorted_segs[0].get("text", "").strip()]

    for s in sorted_segs[1:]:
        s_start = float(s.get("start", 0.0))
        s_end = float(s.get("end", 0.0))
        s_text = s.get("text", "").strip()
        if not s_text:
            continue

        pause = s_start - curr_end
        duration_so_far = curr_end - curr_start
        duration_if_added = s_end - curr_start

        # Check if the preceding segment ends with sentence-ending punctuation or discourse markers
        prev_text = curr_texts[-1].rstrip()
        ends_sentence = prev_text.endswith((".", "!", "?", "।", "नो?", "no?"))

        should_split = (
            (pause >= max_pause and duration_so_far >= 4.0)
            or (duration_if_added > max_duration)
            or (duration_so_far >= target_duration and (pause >= 0.5 or ends_sentence))
        )

        if should_split:
            chunks.append({
                "start": round(curr_start, 2),
                "end": round(curr_end, 2),
                "text": " ".join(curr_texts).strip()
            })
            curr_start = s_start
            curr_end = s_end
            curr_texts = [s_text]
        else:
            curr_end = s_end
            curr_texts.append(s_text)

    if curr_texts:
        chunks.append({
            "start": round(curr_start, 2),
            "end": round(curr_end, 2),
            "text": " ".join(curr_texts).strip()
        })

    return chunks


def analyze_segment_heuristics(
    chunk: Dict[str, Any],
    pii_count: int = 0,
    slang_found: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Evaluates semantic intent and speaker stance for an individual timestamped segment.
    """
    text = chunk.get("text", "")
    start = round(float(chunk.get("start", 0.0)), 2)
    end = round(float(chunk.get("end", 0.0)), 2)

    h_res = heuristic_sebi_analysis(
        text,
        pii_count=pii_count,
        slang_found=slang_found or [],
        injection_found=False,
        injection_match=None
    )

    claims = []
    for k in [
        "specific_return_promises", "implied_returns", "urgency_scarcity_language",
        "paywall_push", "fee_or_transfer_requests", "credential_or_otp_requests",
        "unsupported_regulatory_claims", "social_proof_inflation", "credential_misrepresentation"
    ]:
        for item in h_res.get(k, []):
            if item not in claims:
                claims.append(item)

    # Also extract any explicit/implied return patterns or quoted return phrases from text
    claim_patterns = [
        r"(?i)\b\d+%\s*(?:guaranteed|assured|promised)\s*(?:returns?|profit|monthly|daily|annual|yearly|weekly)?\b",
        r"(?i)\b(?:guaranteed|assured|promised)\s+\d+%\s*(?:returns?|profit|gains?)?\b",
        r"(?i)\b(?:triple\s+returns?|3x\s+returns?|प्रपल\s+रिटान्स|तीन\s+गुना|चार\s+गुना)(?:\s+in\s+\w+\s+\w+)?\b",
        r"(?i)\bpaisa\s*double\b",
        r"(?i)\b\d+%\s*(?:monthly|daily|annual|yearly)\s+profit\b",
        r"(?i)\b(?:guaranteed\s+\d+%\s+monthly\s+profit)\b",
        r"(?i)\b(?:transfer\s+advance\s+margin(?:\s+of\s+\d+\s+rupees)?)\b",
        r"(?i)\b(?:advance\s+margin\s*(?:of\s+\d+\s+rupees)?)\b",
    ]
    for pat in claim_patterns:
        for m in re.finditer(pat, text):
            match_str = m.group(0).strip()
            if match_str and match_str not in claims:
                claims.append(match_str)

    is_quoted_framing = False
    for pat in SCAM_ATTRIBUTION_PATTERNS:
        if re.search(pat, text):
            is_quoted_framing = True
            break
    if not is_quoted_framing and ("?" in text or "no?" in text.lower()):
        if claims or re.search(r"(?i)\b(?:returns?|profit|stock|multibagger|tip|video|invest)\b", text):
            is_quoted_framing = True

    has_promo_cta = False
    for pat in PROMOTIONAL_CTA_PATTERNS:
        if re.search(pat, text):
            has_promo_cta = True
            break

    has_awareness = False
    for pat in AWARENESS_WARNING_PATTERNS + PROHIBITION_PATTERNS:
        if re.search(pat, text):
            has_awareness = True
            break

    intent = h_res.get("content_intent", "neutral_discussion")
    stance = h_res.get("speaker_stance", "neutral")
    risk = h_res.get("composite_risk_score", 0.0)
    evidence = ""

    is_third_party_attribution = bool(re.search(
        r"(?i)\b(?:some\s+\w+|certain\s+\w+|third[\s-]party|proprietary|syndicates?|firms?|desks?|platforms?|traders?)\s+(?:claim|advertise|report|allege)\b",
        text
    )) or is_quoted_framing

    if has_awareness:
        intent = "awareness_warning"
        stance = "warning"
        risk = 0.0
        evidence = "Segment contains explicit scam awareness warnings, satire/debunking, or regulatory cautions."
    elif has_promo_cta or (h_res.get("content_intent") == "scam_promotion" and h_res.get("speaker_stance") in ["promoting", "endorsing"]):
        intent = "scam_promotion"
        stance = "endorsing"
        risk = max(0.65, risk)
        evidence = "Segment actively solicits or endorses high-risk financial promises, urgency, or paid groups."
    elif is_third_party_attribution and claims:
        intent = "quoted_claim"
        stance = "quoting"
        risk = 0.10
        evidence = "Segment inquires about or quotes third-party financial claims or tip videos without endorsing them."
    elif claims:
        intent = "ambiguous"
        stance = "unclear"
        risk = 0.35
        evidence = "Segment discusses financial claims with unclear promotional or cautionary stance."
    else:
        intent = "neutral_discussion"
        stance = "neutral"
        risk = 0.0
        evidence = "General financial education, dialogue, or non-promotional discussion."

    return {
        "start": start,
        "end": end,
        "text": text,
        "intent": intent,
        "speaker_stance": stance,
        "extracted_claims": claims,
        "evidence": evidence,
        "segment_risk": round(risk, 2),
        "analysis_status": "heuristic"
    }


def aggregate_temporal_segments(
    segments_analysis: List[Dict[str, Any]],
    full_text: str,
    baseline: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Carefully aggregates temporal segment findings into a coherent overall verdict.
    Ensures:
      - Quoted claims followed by debunking/awareness warnings resolve to awareness_warning (0.0 risk).
      - Active scam promotions with token/post-hoc disclaimers remain scam_promotion (>= 0.50 risk).
      - Materially conflicting or unresolvable claims retain review-required ambiguous state (35% floor).
      - Unrelated financial education remains Safe (0.0 risk).
    """
    if not segments_analysis:
        return baseline

    has_endorsed_scam = any(
        s.get("intent") == "scam_promotion" and s.get("speaker_stance") in ["endorsing", "promoting"]
        for s in segments_analysis
    )
    has_awareness_warning = any(
        s.get("intent") == "awareness_warning" and s.get("speaker_stance") == "warning"
        for s in segments_analysis
    )
    has_quoted_claim = any(
        s.get("intent") == "quoted_claim" or s.get("speaker_stance") == "quoting"
        for s in segments_analysis
    )
    has_ambiguous = any(
        s.get("intent") == "ambiguous" or s.get("speaker_stance") in ["ambiguous", "unclear"]
        for s in segments_analysis
    )

    agg = dict(baseline)
    agg["segments_analysis"] = segments_analysis

    # Distinguish genuine active scam promotions with concrete violation claims
    # from initial quoted claims or inquiries that are subsequently debunked.
    has_substantive_promo_violations = False
    for s in segments_analysis:
        if s.get("intent") == "scam_promotion" and s.get("speaker_stance") in ["endorsing", "promoting"]:
            claims = s.get("extracted_claims", [])
            for c in claims:
                c_str = str(c).lower()
                if any(w in c_str for w in ["return", "%", "profit", "guarantee", "paisa double", "fee", "margin", "otp", "password", "telegram", "vip"]):
                    has_substantive_promo_violations = True
                    break
            if has_substantive_promo_violations:
                break

    baseline_has_violations = bool(
        agg.get("specific_return_promises")
        or agg.get("fee_or_transfer_requests")
        or agg.get("credential_or_otp_requests")
        or any(v >= 0.50 for v in agg.get("signal_scores", {}).values())
    )
    has_active_scam_solicitation = has_substantive_promo_violations or baseline_has_violations

    # 1. Quoted claims / inquiries followed by awareness warning / debunking (The Malini Pattern)
    if has_awareness_warning and (has_quoted_claim or not has_active_scam_solicitation):
        if not has_active_scam_solicitation:
            agg["content_intent"] = "awareness_warning"
            agg["speaker_stance"] = "warning"
            agg["awareness_context_detected"] = True
            agg["is_scam_likely"] = False
            agg["composite_risk_score"] = 0.0
            agg["signal_scores"] = {k: 0.0 for k in SIGNAL_WEIGHTS}
            for list_key in [
                "specific_return_promises", "urgency_scarcity_language",
                "social_proof_inflation", "paywall_push", "implied_returns",
                "credential_misrepresentation", "fee_or_transfer_requests",
                "credential_or_otp_requests", "unsupported_regulatory_claims",
            ]:
                agg[list_key] = []
            agg["reasoning"] = (
                "Educational / scam awareness context: Video quotes, portrays, or questions suspicious stock tips "
                "or return promises before explicitly debunking them as scams and providing investor protection advice."
            )
            agg["analysis_status"] = "success"
            return agg

    # 2. Genuine or endorsed scam promotion (token disclaimer cannot erase active promotion)
    if has_endorsed_scam:
        agg["content_intent"] = "scam_promotion"
        agg["speaker_stance"] = "promoting"
        agg["awareness_context_detected"] = False
        agg["is_scam_likely"] = True
        all_promo_claims = []
        for s in segments_analysis:
            if s.get("intent") == "scam_promotion":
                all_promo_claims.extend(s.get("extracted_claims", []))
        if all_promo_claims and not agg.get("specific_return_promises"):
            agg["specific_return_promises"] = [c for c in all_promo_claims if "return" in c.lower() or "%" in c or "profit" in c.lower()]

        comp = compute_composite_score(agg.get("signal_scores", {}), normalize=False)
        agg["composite_risk_score"] = max(0.50, comp)
        if has_awareness_warning:
            agg["reasoning"] = (
                "High risk: Video actively promotes high-risk financial schemes, guaranteed returns, or unregistered tips. "
                "Attached token disclaimers do not exempt fraudulent solicitations from SEBI compliance regulations."
            )
        else:
            agg["reasoning"] = (
                "High risk: Video actively promotes high-risk financial schemes or guaranteed returns."
            )
        agg["analysis_status"] = "success"
        return agg

    # 3. Materially conflicting or ambiguous segments requiring review
    if has_ambiguous or baseline.get("content_intent") == "ambiguous":
        agg["content_intent"] = "ambiguous"
        agg["speaker_stance"] = "ambiguous"
        agg["awareness_context_detected"] = False
        agg["is_scam_likely"] = False
        comp = compute_composite_score(agg.get("signal_scores", {}), normalize=False)
        agg["composite_risk_score"] = max(0.35, comp)
        agg["reasoning"] = (
            "Compliance review recommended: Content presents unverified financial claims or conflicting signals "
            "without clear promotional endorsement or definitive cautionary warning. Human verification recommended."
        )
        agg["analysis_status"] = "success"
        return agg

    # 4. Pure awareness content throughout
    if has_awareness_warning:
        agg["content_intent"] = "awareness_warning"
        agg["speaker_stance"] = "warning"
        agg["awareness_context_detected"] = True
        agg["is_scam_likely"] = False
        agg["composite_risk_score"] = 0.0
        agg["signal_scores"] = {k: 0.0 for k in SIGNAL_WEIGHTS}
        for list_key in [
            "specific_return_promises", "urgency_scarcity_language",
            "social_proof_inflation", "paywall_push", "implied_returns",
            "credential_misrepresentation", "fee_or_transfer_requests",
            "credential_or_otp_requests", "unsupported_regulatory_claims",
        ]:
            agg[list_key] = []
        agg["analysis_status"] = "success"
        return agg

    # 5. Default neutral discussion
    agg["content_intent"] = "neutral_discussion"
    agg["speaker_stance"] = "neutral"
    agg["is_scam_likely"] = False
    agg["composite_risk_score"] = 0.0
    agg["analysis_status"] = "success"
    return agg


def run_stage5_llm(
    transcript: str,
    job_id: str,
    ocr_text: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None
):
    """
    Calls local Ollama instance to perform timestamp-aware SEBI compliance analysis on the transcript
    and optional on-screen video OCR text.
    Includes:
      1. DPDP Act 2023 Local PII Scrubbing
      2. Adversarial Hinglish Financial Slang Detection
      3. Prompt Injection Security Envelope
      4. Structured Discourse Chunking & Timestamp-Aware Intent Analysis
      5. Multi-Signal Regulatory Scoring & Entity Extraction
      6. Temporal Mixed-Intent Aggregation & Fallback Preservation
    """
    print(f"[{job_id}] Running Stage 5: Timestamp-Aware SEBI Compliance Reasoning (with DPDP Shield & Hinglish NLP)")
    stage_config = get_stage_config("stage5_llm")
    model_id = stage_config.get("model_id", "llama3.1:latest")
    api_url = stage_config.get("api_url", "http://localhost:11434/api/chat")
    timeout_short = float(stage_config.get("timeout_short_sec", 45.0))
    timeout_long  = float(stage_config.get("timeout_long_sec", 90.0))
    llm_risk_thresh = get_threshold("llm_risk_auto_flag_threshold", 0.45)

    empty_result = SEBIAnalysis(
        llm_used=False,
        fallback_used=False,
        error=None,
        analysis_status="skipped_too_short"
    ).model_dump()

    has_transcript = bool(transcript and len(transcript.strip()) >= 10)
    has_ocr = bool(ocr_text and len(ocr_text.strip()) >= 10)

    if not has_transcript and not has_ocr:
        print(f"[{job_id}] Neither transcript nor on-screen text available. Skipping LLM stage.")
        return empty_result

    if has_transcript and has_ocr:
        analysis_content = f"{transcript.strip()}\n\n[On-Screen Video Text]:\n{ocr_text.strip()}"
    elif has_ocr:
        analysis_content = f"[On-Screen Video Text]:\n{ocr_text.strip()}"
    else:
        analysis_content = transcript

    # ── 1. DPDP Act 2023 Local PII Masking ───────────────────────────
    scrubbed_transcript, pii_count = scrub_pii_dpdp(analysis_content)
    if pii_count > 0:
        print(f"[{job_id}] [DPDP SHIELD] Masked {pii_count} sensitive PII entities (phone/PAN/UPI/Bank/Link) before analysis.")

    # ── 2. Adversarial Hinglish Slang Scan ───────────────────────────
    slang_found = detect_hinglish_slang(analysis_content)
    if slang_found:
        print(f"[{job_id}] [HINGLISH NLP] Detected coded fraud slang: {slang_found}")

    # ── 3. Prompt Injection Firewall ─────────────────────────────────
    injection_found, injection_match = scan_for_prompt_injection(analysis_content)
    if injection_found:
        print(f"[{job_id}] [ALERT] CRITICAL: Adversarial Prompt Injection detected: '{injection_match}'")

    # ── 4. Structured Discourse Chunking ─────────────────────────────
    chunks = group_transcript_segments(segments) if segments else []
    heuristic_segments = [analyze_segment_heuristics(c, pii_count, slang_found) for c in chunks] if chunks else []

    # Fast deterministic heuristic baseline
    heuristic_baseline = heuristic_sebi_analysis(
        scrubbed_transcript, pii_count, slang_found, injection_found, injection_match
    )
    if heuristic_segments:
        heuristic_baseline["segments_analysis"] = heuristic_segments
        heuristic_baseline = aggregate_temporal_segments(
            heuristic_segments, scrubbed_transcript, heuristic_baseline
        )
    else:
        heuristic_baseline["segments_analysis"] = []

    system_prompt = (
        "You are an expert SEBI compliance and financial fraud investigator analyzing financial text for scams, regulatory violations, and investor fraud.\n"
        "Your primary job is to perform AI-led semantic intent classification to determine the SPEAKER'S CONTEXTUAL INTENT and STANCE.\n\n"
        "CONTEXTUAL INTENT CATEGORIES:\n"
        "1. 'scam_promotion': The speaker actively promotes, endorses, offers, or solicits high-risk financial schemes, guaranteed returns, VIP/paid channels, advance fees, Demat credentials, or impersonates regulators. (Includes deceptive promotions hiding behind token disclaimers like 'for educational purposes only').\n"
        "2. 'awareness_warning': The speaker warns the public AGAINST scams, educates viewers on fraud prevention, debunks fraudulent claims, or uses sarcasm/satire to expose scam tactics. The speaker tells viewers NOT to trust fraudsters, NEVER to pay fees, and NEVER to share OTPs.\n"
        "3. 'neutral_discussion': Legitimate financial education, broad market commentary, historical performance disclosures (e.g., 'fund generated 14% over the past 5 years'), corporate earnings news, or standard statutory disclaimers.\n"
        "4. 'quoted_claim': Speaker quotes, narrates, portrays, or questions a suspicious tip or promise made by a third party without endorsing it.\n"
        "5. 'ambiguous': Content discusses suspicious claims, extreme yields, or controversial strategies without clear promotional endorsement and without clear cautionary warning (requires human review).\n\n"
        "EVALUATING HIGH-RISK ACTIONS (OTPs, Credentials, Advance Fees, Guaranteed Returns):\n"
        "- ENDORSING/SOLICITING: Speaker asks the audience to perform the action ('send OTP', 'pay advance margin', 'join VIP group', 'I guarantee 50%') -> scam_promotion.\n"
        "- WARNING/PROHIBITING: Speaker instructs the audience NOT to perform the action ('never share OTP', 'do not deposit fees', 'beware of guaranteed returns') -> awareness_warning.\n"
        "- QUOTING/ATTRIBUTING: Speaker mentions scam tactics as an example of what bad actors do or quotes a video ('Scammers claim they can double your money', 'I saw a video promising triple returns') -> quoted_claim or awareness_warning.\n"
        "- REPORTING/DEBUNKING: Speaker shares a fraud story or advises reporting to authorities ('I reported a scammer who demanded 10% fee to SEBI') -> awareness_warning.\n"
        "- SARCASM/IRONY: Speaker uses sarcasm to ridicule scam promises ('Sure, Loscar movie, beggar ban jaoge, blockbuster scam hai ye') -> awareness_warning.\n"
        "- SATIRICAL ROLEPLAY & DEMONSTRATION: Speaker roleplays as a scammer/villain to demonstrate how scams work ('main yaane ki de villain... promote over misleading ads... create artificial demand... thanks to bakra investors like you...'). The speaker is EXPOSING scam tactics, NOT promoting them -> awareness_warning (stance: warning).\n"
        "- TOKEN DISCLAIMER EVASION: Speaker says 'educational only' or 'not financial advice', but directly pitches a paid VIP group, guaranteed profits, or asks for money -> scam_promotion.\n\n"
        "SEGMENT-LEVEL ANALYSIS INSTRUCTIONS:\n"
        "- When timestamped segments are provided, analyze each segment in 'segments_analysis'.\n"
        "- For each segment, output:\n"
        "  - segment_index: integer (1-based index matching [Segment X])\n"
        "  - intent: exactly one of 'scam_promotion', 'awareness_warning', 'neutral_discussion', 'quoted_claim', 'ambiguous'\n"
        "  - speaker_stance: exactly one of 'endorsing', 'warning', 'quoting', 'unclear'\n"
        "  - extracted_claims: list of exact quote strings for suspicious claims in this segment (empty if none)\n"
        "  - evidence: short explanation of stance and intent for this segment\n"
        "  - segment_risk: float (0.0 to 1.0)\n"
        "(Do NOT repeat the full transcript text or timestamps in segments_analysis; identify segments by segment_index).\n\n"
        "- TEMPORAL MIXED-INTENT AGGREGATION RULES:\n"
        "  1. Quoted bait / inquiry followed by awareness warning: If a speaker quotes or asks about a suspicious third-party stock tip / return promise without endorsing it, and then explicitly debunks it as a scam, ridicules it, or issues investor protection advice (e.g. 'Loscar movie... beggar ban jaoge... blockbuster scam... soch kar invest kar'), the overall content_intent is 'awareness_warning', speaker_stance is 'warning', is_scam_likely is false, composite_risk_score is 0.0, and specific_return_promises is empty.\n"
        "  2. Active promotion with token disclaimer: If a speaker actively promotes a scheme, guaranteed returns, or VIP group, an attached token disclaimer ('educational only') does not erase the scam. Content_intent remains 'scam_promotion' and is_scam_likely is true.\n"
        "  3. Ambiguous content: If claims are disputed or unclear without clear warning or clear promotion, content_intent is 'ambiguous'.\n\n"
        "CRITICAL EVIDENCE EXTRACTION RULES:\n"
        "- ONLY extract quotes into specific_return_promises, fee_or_transfer_requests, credential_or_otp_requests, urgency_scarcity_language, paywall_push, unsupported_regulatory_claims if the speaker is ENDORSING or SOLICITING them.\n"
        "- DO NOT extract quotes into top-level violation lists if the speaker is warning against, quoting, reporting, or satirizing them.\n"
        "- For 'awareness_warning' and 'neutral_discussion', ALL signal_scores must be 0.0 and is_scam_likely must be false.\n\n"
        "Respond in valid JSON with exactly these keys:\n"
        "- segments_analysis: list of dicts with [segment_index, intent, speaker_stance, extracted_claims, evidence, segment_risk]\n"
        "- content_intent: exactly one of 'scam_promotion', 'awareness_warning', 'neutral_discussion', 'ambiguous'\n"
        "- speaker_stance: exactly one of 'promoting', 'warning', 'neutral', 'ambiguous'\n"
        "- awareness_context_detected: boolean, true if content is warning against scams or providing anti-fraud education\n"
        "- specific_return_promises: list of exact quote strings endorsed by speaker\n"
        "- urgency_scarcity_language: list of exact pressure quote strings used by speaker\n"
        "- fee_or_transfer_requests: list of exact quote strings requesting money/fees by speaker\n"
        "- credential_or_otp_requests: list of exact quote strings requesting credentials/OTPs by speaker\n"
        "- unsupported_regulatory_claims: list of exact quote strings claiming SEBI/RBI approval by speaker\n"
        "- social_proof_inflation: list of exact quote strings inflating member counts\n"
        "- paywall_push: list of exact quote strings pushing paid channels or DMs\n"
        "- implied_returns: list of exact quote strings implying returns\n"
        "- credential_misrepresentation: list of exact quote strings exaggerating credentials\n"
        "- signal_scores: dict with keys (explicit_returns, implied_returns, urgency_scarcity, social_proof, paywall_push, credential_misrep)\n"
        "- is_scam_likely: boolean, true ONLY if content_intent is 'scam_promotion'\n"
        "- reasoning: short explanatory string describing speaker intent and stance."
    )

    timeout_sec = timeout_short if len(analysis_content) < 400 else timeout_long
    if chunks:
        timeout_sec = max(timeout_sec, 90.0)

    try:
        print(f"[{job_id}] Sending DPDP-scrubbed content to Ollama ({model_id}, timeout={timeout_sec:.1f}s)...")
        if chunks:
            formatted_segments = "\n".join(
                f"[Segment {idx+1}] ({c['start']}s - {c['end']}s): \"{c['text']}\""
                for idx, c in enumerate(chunks)
            )
            user_content = (
                f"<untrusted_user_content>\n"
                f"TRANSCRIPT SEGMENTS WITH TIMESTAMPS:\n{formatted_segments}\n\n"
                f"FULL TRANSCRIPT:\n{scrubbed_transcript}\n"
                f"</untrusted_user_content>"
            )
        else:
            user_content = f"<untrusted_user_content>\n{scrubbed_transcript}\n</untrusted_user_content>"

        payload = {
            "model": model_id,
            "keep_alive": -1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 500,
                "num_ctx": 2048,
                "repeat_penalty": 1.1
            }
        }

        response = requests.post(api_url, json=payload, timeout=timeout_sec)
        response.raise_for_status()

        data = response.json()
        content = data.get("message", {}).get("content", "{}")

        parsed_json = None
        try:
            parsed_json = extract_json_payload(content)
        except (json.JSONDecodeError, ValidationError) as initial_err:
            print(f"[{job_id}] Initial JSON parse failed ({type(initial_err).__name__}: {initial_err}). Retrying with concise JSON repair prompt...")
            try:
                repair_payload = {
                    "model": model_id,
                    "keep_alive": -1,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a JSON repair tool. Fix any syntax errors, unescaped quotes, trailing commas, "
                                "or missing brackets in the provided text. Output ONLY the valid, well-formed JSON object. "
                                "No markdown fences, no explanatory commentary, no text before or after the JSON."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Fix this malformed JSON and return valid JSON:\n{content[:2500]}"
                        }
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 500,
                        "num_ctx": 2048,
                        "repeat_penalty": 1.1
                    }
                }
                repair_resp = requests.post(api_url, json=repair_payload, timeout=min(timeout_sec, 25.0))
                if repair_resp.status_code == 200:
                    repair_data = repair_resp.json()
                    repair_content = repair_data.get("message", {}).get("content", "{}")
                    parsed_json = extract_json_payload(repair_content)
                    print(f"[{job_id}] One-shot JSON repair succeeded.")
                else:
                    raise initial_err
            except Exception as repair_fail:
                print(f"[{job_id}] One-shot JSON repair failed ({type(repair_fail).__name__}: {repair_fail}). Activating deterministic heuristic fallback.")
                fb = dict(heuristic_baseline)
                fb["llm_used"] = False
                fb["fallback_used"] = True
                fb["error"] = f"LLM output parse error ({type(initial_err).__name__})"
                fb["analysis_status"] = "fallback_parse_error"
                fb["reasoning"] = "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] " + fb.get("reasoning", "")
                return fb

        try:
            # 1. AI-Led Contextual Intent & Stance Resolution
            raw_intent = str(parsed_json.get("content_intent", "")).strip().lower()
            if raw_intent in ("scam_promotion", "scam", "promotion", "fraud", "solicitation"):
                intent = "scam_promotion"
            elif raw_intent in ("awareness_warning", "awareness", "warning", "education", "educational", "debunking"):
                intent = "awareness_warning"
            elif raw_intent in ("neutral_discussion", "neutral", "discussion", "benign", "informational"):
                intent = "neutral_discussion"
            elif raw_intent in ("quoted_claim", "quoted", "quoting"):
                intent = "quoted_claim"
            elif raw_intent in ("ambiguous", "uncertain", "review", "unverified"):
                intent = "ambiguous"
            else:
                intent = heuristic_baseline.get("content_intent", "ambiguous")

            # Retain the review-required ambiguous state rather than forcing a safe or scam verdict
            if heuristic_baseline.get("content_intent") == "ambiguous" and intent in ("neutral_discussion", "neutral"):
                intent = "ambiguous"

            parsed_json["content_intent"] = intent

            raw_stance = str(parsed_json.get("speaker_stance", "")).strip().lower()
            if raw_stance in ("promoting", "warning", "neutral", "ambiguous", "quoting"):
                stance = raw_stance
            elif intent == "awareness_warning":
                stance = "warning"
            elif intent == "scam_promotion":
                stance = "promoting"
            elif intent == "quoted_claim":
                stance = "quoting"
            elif intent == "neutral_discussion":
                stance = "neutral"
            else:
                stance = heuristic_baseline.get("speaker_stance", "ambiguous")
            parsed_json["speaker_stance"] = stance

            if "awareness_context_detected" not in parsed_json:
                parsed_json["awareness_context_detected"] = (
                    intent == "awareness_warning"
                    or heuristic_baseline.get("awareness_context_detected", False)
                )

            # 2. Validate or populate segments_analysis
            llm_segs = parsed_json.get("segments_analysis")
            if isinstance(llm_segs, list) and len(llm_segs) > 0:
                validated_segs = []
                for idx, s in enumerate(llm_segs):
                    if isinstance(s, dict):
                        chunk_ref = None
                        seg_idx = s.get("segment_index") or s.get("index")
                        if isinstance(seg_idx, int) and 1 <= seg_idx <= len(chunks):
                            chunk_ref = chunks[seg_idx - 1]
                        elif idx < len(chunks):
                            chunk_ref = chunks[idx]

                        start_val = float(s.get("start", chunk_ref["start"] if chunk_ref else 0.0))
                        end_val = float(s.get("end", chunk_ref["end"] if chunk_ref else 0.0))
                        text_val = str(s.get("text", "")).strip() or (chunk_ref["text"] if chunk_ref else "")

                        seg_item = {
                            "start": start_val,
                            "end": end_val,
                            "text": text_val,
                            "intent": str(s.get("intent", "neutral_discussion")),
                            "speaker_stance": str(s.get("speaker_stance", "neutral")),
                            "extracted_claims": list(s.get("extracted_claims", [])),
                            "evidence": str(s.get("evidence", "")),
                            "segment_risk": float(s.get("segment_risk", 0.0)),
                            "analysis_status": "success"
                        }
                        # Safeguard: pedagogical villain roleplay / pump-and-dump demonstration / debunking
                        villain_debunk_pattern = (
                            r"(?i)\b(?:bakra\s+investors?|the\s+villain|दे\s*विलन|द\s*विलन|दविलन|"
                            r"misleading\s+advertisements?|artificially\s+create\s+demand|blockbuster\s+scam|"
                            r"ब्लोक\s*बस्टर\s*स्काम|ब्लॉक\s*बस्टर\s*स्कैम|बैगर\s*बन\s*जाओगे|बेगर\s*बन|"
                            r"लुट(?:े|गा)\s*हम\s*बाजार|लूटेगे\s*हम\s*बाज़ार|सोच\s*के,\s*समझ\s*के|सोचकर,\s*समझकर)\b"
                        )
                        if re.search(villain_debunk_pattern, seg_item["text"]):
                            seg_item["intent"] = "awareness_warning"
                            seg_item["speaker_stance"] = "warning"
                            seg_item["segment_risk"] = 0.0
                            seg_item["evidence"] = "Satirical roleplay / pedagogical demonstration exposing pump-and-dump scam mechanics."
                        validated_segs.append(seg_item)
                parsed_json["segments_analysis"] = validated_segs
            elif heuristic_segments:
                parsed_json["segments_analysis"] = heuristic_segments
            else:
                parsed_json["segments_analysis"] = []

            # 3. Temporal Mixed-Intent Aggregation
            if parsed_json.get("segments_analysis"):
                parsed_json = aggregate_temporal_segments(
                    parsed_json["segments_analysis"],
                    scrubbed_transcript,
                    parsed_json
                )
                intent = parsed_json["content_intent"]

            # 4. Normalize and map signal_scores to canonical keys safely
            raw_scores = parsed_json.get("signal_scores")
            parsed_json["signal_scores"] = normalize_signal_scores(raw_scores, default_all_zero=True)

            # 5. Sanitize, deduplicate, and validate all evidence quote lists
            for list_key in [
                "specific_return_promises", "urgency_scarcity_language",
                "social_proof_inflation", "paywall_push", "implied_returns",
                "credential_misrepresentation", "fee_or_transfer_requests",
                "credential_or_otp_requests", "unsupported_regulatory_claims"
            ]:
                raw_list = parsed_json.get(list_key)
                if isinstance(raw_list, list):
                    cleaned = []
                    for item in raw_list:
                        if isinstance(item, str) and item.strip():
                            s = item.strip()
                            if s not in cleaned:
                                cleaned.append(s)
                    parsed_json[list_key] = cleaned
                else:
                    parsed_json[list_key] = []

            # 6. Intent Enforcement & Score Clamping
            if intent in ("awareness_warning", "neutral_discussion"):
                parsed_json["is_scam_likely"] = False
                parsed_json["signal_scores"] = {k: 0.0 for k in SIGNAL_WEIGHTS}
                for list_key in [
                    "specific_return_promises", "urgency_scarcity_language",
                    "social_proof_inflation", "paywall_push", "implied_returns",
                    "credential_misrepresentation", "fee_or_transfer_requests",
                    "credential_or_otp_requests", "unsupported_regulatory_claims"
                ]:
                    parsed_json[list_key] = []
                parsed_json["composite_risk_score"] = 0.0
                parsed_json["analysis_status"] = "success"

            elif intent == "ambiguous":
                parsed_json["is_scam_likely"] = False
                if not parsed_json.get("claimed_advisor_name") and heuristic_baseline.get("claimed_advisor_name"):
                    parsed_json["claimed_advisor_name"] = heuristic_baseline["claimed_advisor_name"]
                if not parsed_json.get("claimed_registration_number") and heuristic_baseline.get("claimed_registration_number"):
                    parsed_json["claimed_registration_number"] = heuristic_baseline["claimed_registration_number"]
                comp = compute_composite_score(parsed_json["signal_scores"], normalize=False)
                parsed_json["composite_risk_score"] = max(0.35, comp)
                parsed_json["analysis_status"] = "success"

            else:  # scam_promotion
                if not parsed_json.get("claimed_advisor_name") and heuristic_baseline.get("claimed_advisor_name"):
                    parsed_json["claimed_advisor_name"] = heuristic_baseline["claimed_advisor_name"]
                if not parsed_json.get("claimed_registration_number") and heuristic_baseline.get("claimed_registration_number"):
                    parsed_json["claimed_registration_number"] = heuristic_baseline["claimed_registration_number"]
                for k in [
                    "fee_or_transfer_requests", "credential_or_otp_requests", "unsupported_regulatory_claims",
                    "urgency_scarcity_language", "specific_return_promises", "paywall_push", "implied_returns"
                ]:
                    if not parsed_json.get(k) and heuristic_baseline.get(k):
                        parsed_json[k] = heuristic_baseline[k]

                if parsed_json.get("specific_return_promises") and parsed_json["signal_scores"].get("explicit_returns", 0.0) < 0.5:
                    parsed_json["signal_scores"]["explicit_returns"] = max(parsed_json["signal_scores"].get("explicit_returns", 0.0), 0.85)
                if parsed_json.get("urgency_scarcity_language") and parsed_json["signal_scores"].get("urgency_scarcity", 0.0) < 0.5:
                    parsed_json["signal_scores"]["urgency_scarcity"] = max(parsed_json["signal_scores"].get("urgency_scarcity", 0.0), 0.70)
                if parsed_json.get("paywall_push") and parsed_json["signal_scores"].get("paywall_push", 0.0) < 0.5:
                    parsed_json["signal_scores"]["paywall_push"] = max(parsed_json["signal_scores"].get("paywall_push", 0.0), 0.75)
                if parsed_json.get("implied_returns") and parsed_json["signal_scores"].get("implied_returns", 0.0) < 0.5:
                    parsed_json["signal_scores"]["implied_returns"] = max(parsed_json["signal_scores"].get("implied_returns", 0.0), 0.70)

                active_slang = heuristic_baseline.get("hinglish_slang_detected", [])
                if active_slang:
                    current_implied = parsed_json["signal_scores"].get("implied_returns", 0.0)
                    parsed_json["signal_scores"]["implied_returns"] = max(current_implied, 0.75)
                    if not parsed_json["implied_returns"]:
                        parsed_json["implied_returns"] = []
                    for s in active_slang:
                        quote = f"[Hinglish Scam Slang]: '{s}'"
                        if quote not in parsed_json["implied_returns"]:
                            parsed_json["implied_returns"].append(quote)

                comp = compute_composite_score(parsed_json["signal_scores"], normalize=False)
                has_concrete_violations = any(parsed_json.get(k) for k in [
                    "specific_return_promises", "implied_returns", "urgency_scarcity_language",
                    "paywall_push", "fee_or_transfer_requests", "credential_or_otp_requests",
                    "unsupported_regulatory_claims", "social_proof_inflation", "credential_misrepresentation"
                ]) or any(v > 0.0 for v in parsed_json["signal_scores"].values())

                if not has_concrete_violations:
                    # Without quoted violations or elevated signals, content cannot be a confirmed scam.
                    # Route to ambiguous for human compliance review.
                    parsed_json["content_intent"] = "ambiguous"
                    parsed_json["speaker_stance"] = "ambiguous"
                    parsed_json["is_scam_likely"] = False
                    parsed_json["composite_risk_score"] = 0.35
                    parsed_json["analysis_status"] = "conflict_review"
                    parsed_json["reasoning"] = (
                        "Compliance review recommended: Content was flagged for potentially suspicious discussion, but contained no extractable regulatory violation quotes or verified return promises."
                    )
                else:
                    parsed_json["composite_risk_score"] = max(0.50, comp)
                    parsed_json["is_scam_likely"] = True
                    parsed_json["analysis_status"] = "success"

            if injection_found:
                parsed_json["prompt_injection_detected"] = True
                parsed_json["is_scam_likely"] = True
                parsed_json["content_intent"] = "scam_promotion"
                parsed_json["speaker_stance"] = "promoting"
                parsed_json["awareness_context_detected"] = False
                parsed_json["composite_risk_score"] = 1.0
                parsed_json["signal_scores"]["credential_misrep"] = 1.0
                if not parsed_json.get("credential_misrepresentation"):
                    parsed_json["credential_misrepresentation"] = []
                quote = f"[Adversarial Manipulation Attempt]: '{injection_match}'"
                if quote not in parsed_json["credential_misrepresentation"]:
                    parsed_json["credential_misrepresentation"].append(quote)
                parsed_json["reasoning"] = f"CRITICAL: Adversarial prompt injection attempt detected ('{injection_match}') to bypass SEBI compliance scanner. " + parsed_json.get("reasoning", "")

            analysis = SEBIAnalysis(**parsed_json)
            result = analysis.model_dump()

            result["dpdp_pii_scrubbed_count"] = pii_count
            result["hinglish_slang_detected"] = heuristic_baseline.get("hinglish_slang_detected", [])
            result["segments_analysis"] = parsed_json.get("segments_analysis", [])

            result["llm_used"] = True
            result["fallback_used"] = False
            result["error"] = None
            result["analysis_status"] = "success"

            print(f"[{job_id}] LLM reasoning complete. Intent: {result['content_intent']}, Scam likely: {result['is_scam_likely']}, Composite Risk: {result['composite_risk_score']:.2f}, DPDP Masked: {pii_count}, Slang: {len(result['hinglish_slang_detected'])}, Segments: {len(result['segments_analysis'])}")
            return result

        except ValidationError as val_err:
            print(f"[{job_id}] Schema validation error after parse ({val_err}), using heuristic fallback engine.")
            fb = dict(heuristic_baseline)
            fb["llm_used"] = False
            fb["fallback_used"] = True
            fb["error"] = f"LLM schema validation error ({type(val_err).__name__})"
            fb["analysis_status"] = "fallback_parse_error"
            fb["reasoning"] = "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] " + fb.get("reasoning", "")
            return fb

    except requests.exceptions.Timeout as e:
        err_msg = f"LLM inference timeout after {timeout_sec:.1f}s ({model_id})"
        print(f"[{job_id}] {err_msg}, using heuristic fallback engine.")
        fb = dict(heuristic_baseline)
        fb["llm_used"] = False
        fb["fallback_used"] = True
        fb["error"] = err_msg
        fb["analysis_status"] = "fallback_timeout"
        fb["reasoning"] = "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] " + fb.get("reasoning", "")
        return fb
    except requests.exceptions.ConnectionError as e:
        err_msg = f"Ollama service unreachable at {api_url}"
        print(f"[{job_id}] {err_msg}, using heuristic fallback engine.")
        fb = dict(heuristic_baseline)
        fb["llm_used"] = False
        fb["fallback_used"] = True
        fb["error"] = err_msg
        fb["analysis_status"] = "fallback_unavailable"
        fb["reasoning"] = "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] " + fb.get("reasoning", "")
        return fb
    except Exception as e:
        err_msg = f"LLM stage error ({type(e).__name__}: {e})"
        print(f"[{job_id}] {err_msg}, using heuristic fallback engine.")
        fb = dict(heuristic_baseline)
        fb["llm_used"] = False
        fb["fallback_used"] = True
        fb["error"] = f"LLM stage error ({type(e).__name__})"
        fb["analysis_status"] = "fallback_error"
        fb["reasoning"] = "[HEURISTIC FALLBACK: Deterministic SEBI compliance rules applied.] " + fb.get("reasoning", "")
        return fb
