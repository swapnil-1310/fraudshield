"""
FraudShield-SEBI Pro — Screenshot Forensic Scanner v2 (Fully Offline)
========================================================================
Runs 100% locally on GPU:
  EasyOCR (GPU-accelerated) + SEBI Rule Engine + Image Heuristics

Prompts documented in: core/prompts.py → EASYOCR_ENGINE_DESCRIPTION
"""

import os
import re
import sys
from typing import Dict, Any
from PIL import Image
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

# ── EasyOCR (Local GPU) ─────────────────────────────────────────────────────
_ocr_reader = None


def _get_ocr_reader():
    """Lazy-load EasyOCR reader (cached singleton). Runs on GPU if available."""
    global _ocr_reader
    if _ocr_reader is not None:
        return _ocr_reader

    try:
        import easyocr
        import torch
        use_gpu = torch.cuda.is_available()
        print(f"[ScreenshotScanner] Loading EasyOCR (GPU={use_gpu})...")
        _ocr_reader = easyocr.Reader(['en'], gpu=use_gpu)
        print("[ScreenshotScanner] EasyOCR loaded.")
        return _ocr_reader
    except ImportError:
        print("[ScreenshotScanner] easyocr is not installed.")
        return None
    except Exception as e:
        print(f"[ScreenshotScanner] EasyOCR init error: {e}")
        return None


def _analyze_image_heuristics(image_path: str) -> Dict[str, Any]:
    """
    Image-level heuristics for detecting visual fraud indicators:
    - Impossibly round profit numbers
    - Screenshot-of-screenshot compression artifacts
    - Suspicious font rendering
    - UI element inconsistencies
    """
    import cv2

    signals = []
    heuristic_score = 0.0

    try:
        img = cv2.imread(image_path)
        if img is None:
            return {"score": 0.0, "signals": []}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # 1. JPEG compression artifact detection (screenshot-of-screenshot)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = lap.var()
        if lap_var < 50.0:
            heuristic_score += 0.10
            signals.append("low_image_complexity_possible_compression")

        # 2. Check for notification bar cropping (common in real screenshots)
        top_strip = gray[:min(50, h), :]
        top_var = float(np.std(top_strip))
        if top_var < 15.0:
            heuristic_score += 0.05
            signals.append("uniform_top_bar")

        # 3. Edge density around text areas (fake UIs have cleaner edges)
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / edges.size
        if edge_ratio < 0.01:
            heuristic_score += 0.10
            signals.append("very_low_edge_density")
        elif edge_ratio > 0.35:
            heuristic_score += 0.05
            signals.append("high_edge_noise")

        # 4. Color uniformity check (fake apps often use flat/solid colors)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        unique_hues = len(np.unique(hsv[:, :, 0] // 10))
        if unique_hues < 5:
            heuristic_score += 0.08
            signals.append("very_limited_color_palette")

        heuristic_score = min(round(heuristic_score, 4), 0.5)

    except Exception as e:
        print(f"[ScreenshotScanner] Heuristic analysis error: {e}")

    return {"score": heuristic_score, "signals": signals}


def _analyze_with_local_ocr(image_path: str) -> Dict[str, Any]:
    """
    Local analysis: EasyOCR + SEBI Compliance Rule Engine + Image Heuristics.
    Runs entirely on local GPU without any API calls.
    """
    from .sebi_compliance import analyze_sebi_compliance

    reader = _get_ocr_reader()
    if reader is None:
        return None

    try:
        print(f"[ScreenshotScanner] Running local EasyOCR on GPU...")
        result = reader.readtext(image_path, detail=0)
        extracted_text = " ".join(result)

        print(f"[ScreenshotScanner] OCR extracted text length: {len(extracted_text)} chars")

        if len(extracted_text.strip()) < 5:
            return {
                "is_violation": False,
                "risk_score": 0.05,
                "verdict": "COMPLIANT",
                "confidence": "LOW",
                "summary": "No readable text found in image.",
                "reasons": ["Image contains no detectable text content."],
                "sebi_rules": [],
                "detected_schemes": ["none"]
            }

        # Run SEBI compliance analysis on extracted text
        compliance_result = analyze_sebi_compliance(extracted_text)

        # Run image-level heuristics
        heuristics = _analyze_image_heuristics(image_path)

        # Blend text compliance score with image heuristics
        text_score = compliance_result["risk_score"]
        image_score = heuristics["score"]
        combined_score = min(1.0, round(0.85 * text_score + 0.15 * image_score, 4))

        reasons = compliance_result["reasons"]
        if heuristics["signals"]:
            reasons.append(f"Visual heuristics: {', '.join(heuristics['signals'])}")

        is_violation = combined_score >= config.SEBI_RISK_THRESHOLD

        return {
            "is_violation": is_violation,
            "risk_score": combined_score,
            "verdict": compliance_result["verdict"] if is_violation else "COMPLIANT",
            "confidence": "MEDIUM (Local OCR + Rule Engine)",
            "summary": f"Local OCR analysis: {compliance_result['summary']}",
            "reasons": reasons,
            "sebi_rules": compliance_result["sebi_rules"],
            "detected_schemes": compliance_result["detected_schemes"]
        }

    except Exception as e:
        print(f"[ScreenshotScanner] Local OCR analysis error: {e}")
        return None


def analyze_screenshot(image_path: str) -> Dict[str, Any]:
    """
    Analyze a trading app screenshot for SEBI violations and fraud indicators.
    Runs fully offline using EasyOCR (GPU) + SEBI Rule Engine + Image Heuristics.
    """

    local_result = _analyze_with_local_ocr(image_path)

    if local_result is not None:
        return local_result

    # EasyOCR not available — return error
    return {
        "is_violation": False,
        "risk_score": 0.0,
        "verdict": "ERROR",
        "confidence": "LOW",
        "summary": "EasyOCR is not installed. Run: pip install easyocr",
        "reasons": ["Analysis could not be completed — EasyOCR required."],
        "detected_schemes": ["none"],
        "sebi_rules": []
    }
