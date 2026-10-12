# 📋 KNOWN_ISSUES.md — Characterization & Known Anomalies Log
> **Phase 1 Baseline Record**: Documents all known behavioral quirks, bugs, and edge cases discovered during characterization testing. Per standing rules, these are recorded and guarded with `@pytest.mark.xfail` without altering production code.

---

## 1. PII Regex Precedence Anomaly (`stage5_llm.py`)
- **Location**: `src/stages/stage5_llm.py:47`
- **Pattern**:
  ```python
  (r"(?i)(?:a/c|acc(?:ount)?(?:\s+no)?[:\s]+)(\d{9,18})", r"a/c [MASKED_BANK_ACCOUNT_DPDP]")
  ```
- **Observed Behavior**: The alternation operator `|` binds `a/c` separately from `(?:\s+no)?[:\s]+`. Consequently:
  - `"account no: 123456789012"` → **MATCHED & MASKED**
  - `"acc 123456789012"` → **MATCHED & MASKED**
  - `"a/c: 123456789012"` → **MATCHED & MASKED**
  - `"a/c 123456789012"` (standard Indian financial phrasing with a space) → **NOT MATCHED / UNMASKED**
- **Test Guard**: Marked with `@pytest.mark.xfail` in `tests/unit/test_pii_shield.py::test_scrub_bank_account_spaced_a_c`.
- **Recommended Phase 2 Fix**: Group prefix alternatives: `r"(?i)(?:a/c|acc(?:ount)?(?:\s+no)?)(?:[:\s]+)(\d{9,18})"`.

---

## 2. Hardcoded Composite Risk Threshold in Calibrated Verdict (`app.py`)
- **Location**: `app.py:67`
- **Code**:
  ```python
  elif composite_risk >= 0.35:
      return "Suspicious: Review Recommended"
  ```
- **Observed Behavior**: While `config.yaml` exposes `thresholds.scam_composite_threshold: 0.35`, `app.py:67` hardcodes the literal float `0.35` instead of invoking `get_threshold("scam_composite_threshold", 0.35)`.
- **Impact**: Changing `scam_composite_threshold` in `config.yaml` updates LLM flagging in Stage 5 but fails to update the final calibrated verdict branch in `app.py`.

---

## 3. Platform-Dependent Virtualenv Path in Registry Sync Endpoint (`app.py`)
- **Location**: `app.py:603`
- **Code**:
  ```python
  result = subprocess.run(
      [".venv/Scripts/python", "scripts/sync_sebi_registry.py"],
      capture_output=True, text=True, cwd=os.getcwd()
  )
  ```
- **Observed Behavior**: Hardcodes the Windows virtualenv interpreter path `".venv/Scripts/python"`.
- **Impact**: Fails with `FileNotFoundError` when deployed on Linux or macOS containers (`.venv/bin/python`), or when running under a non-standard virtualenv name.
- **Recommended Phase 2 Fix**: Use `sys.executable` (`[sys.executable, "scripts/sync_sebi_registry.py"]`).

---

## 4. Unmocked Model Downloads in Legacy `e2e_system_test.py`
- **Location**: `scripts/e2e_system_test.py:24`
- **Observed Behavior**: The test imports `app.py` directly and triggers live video/audio pipeline calls without mocking stage functions, attempting multi-gigabyte HuggingFace weight downloads (`models--Systran--faster-whisper-medium`).
- **Mitigation**: New test suite in `tests/api/test_api_contracts.py` thoroughly mocks ML stages to guarantee instant CPU testing with zero network access.

---

## 5. Starlette / FastAPI TestClient Deprecation Warning
- **Observed Warning**:
  `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`
- **Status**: Non-fatal deprecation warning from Starlette's compatibility shim with recent `httpx` versions. Filtered in `pytest.ini`.
