import os
import re
import json
import time
from rapidfuzz import process, fuzz

from src.config import get_stage_config, get_threshold

# M2: Module-level registry cache to avoid re-parsing JSON on every request
_REGISTRY_CACHE: list = []
_REGISTRY_CACHE_MTIME: float = 0.0
_REGISTRY_CACHE_LOADED_AT: float = 0.0
_REGISTRY_CACHE_TTL_SEC: float = 3600.0  # 1 hour

def _load_registry_cached(source_file: str) -> list:
    """Loads SEBI registry with file-mtime + TTL-based caching."""
    global _REGISTRY_CACHE, _REGISTRY_CACHE_MTIME, _REGISTRY_CACHE_LOADED_AT
    now = time.monotonic()
    try:
        current_mtime = os.path.getmtime(source_file) if os.path.exists(source_file) else 0.0
    except OSError:
        current_mtime = 0.0

    cache_stale = (
        not _REGISTRY_CACHE
        or current_mtime != _REGISTRY_CACHE_MTIME
        or (now - _REGISTRY_CACHE_LOADED_AT) > _REGISTRY_CACHE_TTL_SEC
    )
    if cache_stale:
        if os.path.exists(source_file):
            with open(source_file, "r", encoding="utf-8") as f:
                _REGISTRY_CACHE = json.load(f)
            _REGISTRY_CACHE_MTIME = current_mtime
            _REGISTRY_CACHE_LOADED_AT = now
        else:
            _REGISTRY_CACHE = []
    return _REGISTRY_CACHE

def run_stage6_registry(sebi_analysis: dict, job_id: str):
    """
    Cross-checks the claimed advisor name and registration number against the local SEBI registry.
    Supports exact registration matching, alias matching, and fuzzy name matching.
    Returns:
        dict: {
            "verdict": "verified" | "not found" | "malformed number" | "name-number mismatch" | "not claimed",
            "matched_entity": dict or None
        }
    """
    print(f"[{job_id}] Running Stage 6: SEBI Registrant Cross-check")
    stage_config = get_stage_config("stage6_registry")
    name_number_thresh = get_threshold("registry_name_number_match_score", 65)
    name_only_thresh = get_threshold("registry_name_only_match_score", 80)
    source_file = os.path.join(os.path.dirname(__file__), "..", "..", stage_config.get("source", "static_data/sebi_registry.json"))
    
    result = {
        "verdict": "not claimed",
        "match_status": "absent",  # "confirmed" | "uncertain" | "absent"
        "entity_type": None,
        "matched_entity": None,
        "is_conclusive_fraud": False,
        "explanation": "No financial advisor or entity registration claimed.",
        "snapshot_date": "August 2026",
        "disclaimer": "Evaluated against local SEBI registry snapshot (August 2026). Final regulatory status must be cross-verified on official sebi.gov.in portal."
    }
    
    claimed_name = sebi_analysis.get("claimed_advisor_name")
    claimed_reg_no = sebi_analysis.get("claimed_registration_number")
    
    if not claimed_name and not claimed_reg_no:
        print(f"[{job_id}] No advisor claims made. Skipping registry check.")
        return result
        
    print(f"[{job_id}] Checking claim - Name: {claimed_name}, Reg No: {claimed_reg_no}")
    
    if claimed_reg_no:
        # Valid SEBI IA/RA/Broker starts with INA/INH/INZ followed by alphanumeric
        clean_reg_no = claimed_reg_no.upper().replace(" ", "").replace("-", "").strip()
        if not re.match(r"^IN[A-Z]{1,3}[0-9]{4,12}$", clean_reg_no):
            result["verdict"] = "malformed number"
            result["match_status"] = "uncertain"
            result["entity_type"] = None
            result["is_conclusive_fraud"] = False
            result["explanation"] = f"Claimed registration number '{claimed_reg_no}' has a malformed format (does not match SEBI IN... pattern)."
            print(f"[{job_id}] Verdict: Malformed registration number format: {claimed_reg_no}")
            return result
        claimed_reg_no = clean_reg_no
            
    # Load Registry (M2: uses module-level TTL cache — avoids disk I/O on every request)
    try:
        registry = _load_registry_cached(source_file)
    except Exception as e:
        print(f"[{job_id}] Failed to load registry: {e}")
        return result

    if not registry:
        print(f"[{job_id}] Warning: Registry is empty or file not found at {source_file}.")
        result["verdict"] = "not found"
        result["match_status"] = "absent"
        result["entity_type"] = None
        result["is_conclusive_fraud"] = False
        result["explanation"] = "Local SEBI registry snapshot is currently unavailable. Cross-verify on official sebi.gov.in."
        return result

    # Check by Registration Number (Strongest check)
    if claimed_reg_no:
        matched_entity = next((item for item in registry if item.get("registration_number", "").upper() == claimed_reg_no), None)
        
        if matched_entity:
            entity_type = matched_entity.get("type", "Unknown")
            # Number exists, check if name or any alias matches (fuzzy)
            if claimed_name:
                possible_names = [matched_entity.get("name", "")] + matched_entity.get("aliases", [])
                best_score = max(
                    [fuzz.token_sort_ratio(claimed_name.lower(), p.lower()) for p in possible_names if p],
                    default=0
                )
                if best_score > name_number_thresh:
                    result["verdict"] = "verified"
                    result["match_status"] = "confirmed"
                    result["matched_entity"] = matched_entity
                    result["entity_type"] = entity_type
                    result["is_conclusive_fraud"] = False
                    result["explanation"] = f"Confirmed match in SEBI registry: '{matched_entity.get('name')}' registered as {entity_type} (Reg No: {claimed_reg_no})."
                    print(f"[{job_id}] Verdict: Verified (Match score: {best_score})")
                else:
                    result["verdict"] = "name-number mismatch"
                    result["match_status"] = "uncertain"
                    result["matched_entity"] = None
                    result["entity_type"] = entity_type
                    result["is_conclusive_fraud"] = False
                    result["explanation"] = f"Registration number {claimed_reg_no} is registered to '{matched_entity.get('name')}' ({entity_type}), but speaker claimed '{claimed_name}'."
                    print(f"[{job_id}] Verdict: Name-Number Mismatch. Registered to {matched_entity.get('name')}, claimed {claimed_name}.")
            else:
                result["verdict"] = "verified"
                result["match_status"] = "confirmed"
                result["matched_entity"] = matched_entity
                result["entity_type"] = entity_type
                result["is_conclusive_fraud"] = False
                result["explanation"] = f"Confirmed registration number in SEBI registry: '{matched_entity.get('name')}' registered as {entity_type}."
                print(f"[{job_id}] Verdict: Verified (Number only).")
            return result
        else:
            result["verdict"] = "not found"
            result["match_status"] = "absent"
            result["matched_entity"] = None
            result["entity_type"] = None
            result["is_conclusive_fraud"] = False
            result["explanation"] = f"Registration number '{claimed_reg_no}' is absent from local SEBI registry snapshot. Absence alone is not conclusive proof of fraud; cross-verification on official sebi.gov.in is recommended."
            print(f"[{job_id}] Verdict: Registration number {claimed_reg_no} not found in registry.")
            return result
            
    # Check by Name or Aliases (fuzzy search)
    if claimed_name:
        candidates = []
        for item in registry:
            if item.get("name"):
                candidates.append((item["name"], item))
            for alias in item.get("aliases", []):
                candidates.append((alias, item))
                
        if not candidates:
            result["verdict"] = "not found"
            result["match_status"] = "absent"
            result["entity_type"] = None
            result["is_conclusive_fraud"] = False
            result["explanation"] = f"Advisor name '{claimed_name}' absent from registry snapshot. Absence alone is not conclusive proof of fraud; verify on official sebi.gov.in."
            return result
            
        candidate_strings = [c[0] for c in candidates]
        best_match = process.extractOne(claimed_name, candidate_strings, scorer=fuzz.token_sort_ratio)
        
        if best_match and best_match[1] >= name_only_thresh:  # threshold from config
            matched_tuple = next((c for c in candidates if c[0] == best_match[0]), None)
            matched_entity = matched_tuple[1] if matched_tuple else None
            entity_type = matched_entity.get("type", "Unknown") if matched_entity else None
            result["verdict"] = "verified"
            result["match_status"] = "confirmed"
            result["matched_entity"] = matched_entity
            result["entity_type"] = entity_type
            result["is_conclusive_fraud"] = False
            result["explanation"] = f"Confirmed match in SEBI registry for '{matched_entity.get('name') if matched_entity else best_match[0]}' ({entity_type})."
            print(f"[{job_id}] Verdict: Verified by Name/Alias '{best_match[0]}' (Score: {best_match[1]}). Entity: {matched_entity.get('name') if matched_entity else 'Unknown'}")
        elif best_match and best_match[1] >= name_number_thresh:
            matched_tuple = next((c for c in candidates if c[0] == best_match[0]), None)
            matched_entity = matched_tuple[1] if matched_tuple else None
            entity_type = matched_entity.get("type", "Unknown") if matched_entity else None
            result["verdict"] = "uncertain match"
            result["match_status"] = "uncertain"
            result["matched_entity"] = matched_entity
            result["entity_type"] = entity_type
            result["is_conclusive_fraud"] = False
            result["explanation"] = (
                f"Uncertain registry match for claimed name '{claimed_name}'. "
                f"Closest registered entity is '{matched_entity.get('name') if matched_entity else best_match[0]}' "
                f"({entity_type}) with similarity {best_match[1]:.0f}%. "
                f"Cross-verification on official sebi.gov.in is recommended."
            )
            print(f"[{job_id}] Verdict: Uncertain match for '{claimed_name}'. Closest: '{best_match[0]}' ({best_match[1]}%).")
        else:
            result["verdict"] = "not found"
            result["match_status"] = "absent"
            result["matched_entity"] = None
            result["entity_type"] = None
            result["is_conclusive_fraud"] = False
            result["explanation"] = f"Advisor name '{claimed_name}' absent from local SEBI registry snapshot. Absence alone is not conclusive proof of fraud; verify on official sebi.gov.in."
            print(f"[{job_id}] Verdict: Name '{claimed_name}' not found in registry. Best match was '{best_match[0] if best_match else 'None'}' ({best_match[1] if best_match else 0}%).")
            
    return result
