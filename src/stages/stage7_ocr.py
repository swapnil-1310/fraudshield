import gc
import torch
from PIL import Image
import numpy as np

from src.config import get_device, get_threshold

def run_stage7_ocr(image_path: str, job_id: str):
    """
    Extracts text from an image using EasyOCR (Hindi + English).
    Designed for scam screenshots: fake profit P&Ls, edited SEBI certificates,
    WhatsApp forwards, and Telegram channel screenshots.
    Returns:
        dict: {
            "extracted_text": str,
            "avg_confidence": float,
            "text_blocks": list[dict]  # {"text": str, "confidence": float, "bbox": list}
        }
    """
    print(f"[{job_id}] Running Stage 7: OCR Text Extraction (EasyOCR)")
    
    result = {
        "extracted_text": "",
        "avg_confidence": 0.0,
        "text_blocks": []
    }
    
    if not image_path:
        print(f"[{job_id}] No image path provided. Skipping OCR stage.")
        return result
    
    reader = None
    try:
        import easyocr
        
        device = get_device()
        use_gpu = device == "cuda" and torch.cuda.is_available()
        
        print(f"[{job_id}] Loading EasyOCR reader (en+hi) on {'GPU' if use_gpu else 'CPU'}...")
        reader = easyocr.Reader(['en', 'hi'], gpu=use_gpu, verbose=False)
        
        print(f"[{job_id}] Extracting text from image...")
        ocr_results = reader.readtext(image_path, detail=1, paragraph=False)
        
        all_texts = []
        confidences = []
        
        ocr_min_conf = get_threshold("ocr_min_confidence", 0.15)
        for (bbox, text, conf) in ocr_results:
            if conf < ocr_min_conf:  # Skip very low confidence noise (from config)
                continue
            text_clean = text.strip()
            if not text_clean:
                continue
                
            all_texts.append(text_clean)
            confidences.append(conf)
            result["text_blocks"].append({
                "text": text_clean,
                "confidence": round(float(conf), 3),
                "bbox": [[int(p) for p in point] for point in bbox]
            })
        
        result["extracted_text"] = " ".join(all_texts)
        result["avg_confidence"] = round(float(np.mean(confidences)), 3) if confidences else 0.0
        
        print(f"[{job_id}] OCR complete. Extracted {len(all_texts)} text blocks, avg confidence: {result['avg_confidence']:.3f}")
        
    except ImportError:
        print(f"[{job_id}] easyocr not installed. Run: pip install easyocr")
    except Exception as e:
        print(f"[{job_id}] OCR stage failed: {e}")
    finally:
        if reader is not None:
            del reader
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    return result


def run_video_keyframes_ocr(keyframes: list, job_id: str) -> dict:
    """
    Extracts on-screen text from a representative subset of video keyframes using EasyOCR.
    Avoids redundant/repeated OCR on near-identical frames using visual similarity checks.
    Preserves timestamps and frame references for regulatory audit trail.
    Safe against failures: OCR errors or missing easyocr never crash the pipeline or imply safety.

    Args:
        keyframes: List of dicts [{"path": str, "timestamp_sec": float, "frame_index": int}]
                   or list of str paths.
        job_id: Pipeline tracking identifier.

    Returns:
        dict: {
            "extracted_text": str,
            "avg_confidence": float,
            "text_blocks": list[dict],
            "frame_results": list[dict],
            "total_keyframes_checked": int,
            "keyframes_processed": int,
            "keyframes_skipped_duplicate": int,
            "status": "success" | "skipped_no_frames" | "unavailable" | "error"
        }
    """
    print(f"[{job_id}] Running Stage 7: Video Keyframe OCR")

    result = {
        "extracted_text": "",
        "avg_confidence": 0.0,
        "text_blocks": [],
        "frame_results": [],
        "total_keyframes_checked": 0,
        "keyframes_processed": 0,
        "keyframes_skipped_duplicate": 0,
        "status": "skipped_no_frames"
    }

    if not keyframes:
        print(f"[{job_id}] No video keyframes provided. Skipping keyframe OCR.")
        return result

    # Normalize input keyframes: support both dict format and raw string paths
    normalized_kfs = []
    for idx, item in enumerate(keyframes):
        if isinstance(item, dict):
            p = item.get("path")
            ts = float(item.get("timestamp_sec", 0.0))
            f_idx = int(item.get("frame_index", idx))
        else:
            p = str(item)
            ts = 0.0
            f_idx = idx
        if p:
            normalized_kfs.append({"path": p, "timestamp_sec": ts, "frame_index": f_idx})

    # Limit to at most 5 representative keyframes to preserve responsiveness
    max_kfs = 5
    if len(normalized_kfs) > max_kfs:
        step = max(1, len(normalized_kfs) // max_kfs)
        candidate_kfs = normalized_kfs[::step][:max_kfs]
    else:
        candidate_kfs = normalized_kfs

    result["total_keyframes_checked"] = len(candidate_kfs)

    reader = None
    try:
        import cv2
        import easyocr

        device = get_device()
        use_gpu = device == "cuda" and torch.cuda.is_available()

        print(f"[{job_id}] Loading EasyOCR reader for keyframes on {'GPU' if use_gpu else 'CPU'}...")
        reader = easyocr.Reader(['en', 'hi'], gpu=use_gpu, verbose=False)
        ocr_min_conf = get_threshold("ocr_min_confidence", 0.15)

        prev_thumb = None
        prev_ts = 0.0
        all_unique_texts = []
        all_confidences = []
        seen_phrases = set()

        for kf in candidate_kfs:
            path = kf["path"]
            ts = kf["timestamp_sec"]
            f_idx = kf["frame_index"]

            # Visual similarity check to avoid redundant OCR on near-identical frames
            is_duplicate = False
            try:
                curr_gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if curr_gray is not None:
                    curr_thumb = cv2.resize(curr_gray, (64, 64))
                    if prev_thumb is not None:
                        diff = float(np.mean(np.abs(curr_thumb.astype(float) - prev_thumb.astype(float))))
                        if diff < 8.0:  # Frames are >97% identical
                            is_duplicate = True
                    if not is_duplicate:
                        prev_thumb = curr_thumb
                        prev_ts = ts
            except Exception as _sim_err:
                print(f"[{job_id}] Visual similarity check non-fatal error: {_sim_err}")

            if is_duplicate:
                result["keyframes_skipped_duplicate"] += 1
                result["frame_results"].append({
                    "frame_path": path,
                    "timestamp_sec": ts,
                    "frame_index": f_idx,
                    "extracted_text": "",
                    "avg_confidence": 0.0,
                    "text_blocks": [],
                    "skipped_as_duplicate": True,
                    "duplicate_of_timestamp": prev_ts
                })
                print(f"[{job_id}] Keyframe at {ts:.2f}s skipped as near-identical duplicate.")
                continue

            # Process frame with OCR
            frame_texts = []
            frame_confs = []
            frame_blocks = []

            try:
                ocr_results = reader.readtext(path, detail=1, paragraph=False)
                for (bbox, text, conf) in ocr_results:
                    if conf < ocr_min_conf:
                        continue
                    clean = text.strip()
                    if not clean:
                        continue
                    frame_texts.append(clean)
                    frame_confs.append(float(conf))
                    frame_blocks.append({
                        "text": clean,
                        "confidence": round(float(conf), 3),
                        "bbox": [[int(p) for p in pt] for pt in bbox]
                    })
                    # Add to overall text if not already seen
                    clean_lower = clean.lower()
                    if clean_lower not in seen_phrases:
                        seen_phrases.add(clean_lower)
                        all_unique_texts.append(clean)
                        all_confidences.append(float(conf))
            except Exception as _f_err:
                print(f"[{job_id}] OCR error on frame {path}: {_f_err}")

            frame_avg_conf = round(float(np.mean(frame_confs)), 3) if frame_confs else 0.0
            result["frame_results"].append({
                "frame_path": path,
                "timestamp_sec": ts,
                "frame_index": f_idx,
                "extracted_text": " ".join(frame_texts),
                "avg_confidence": frame_avg_conf,
                "text_blocks": frame_blocks,
                "skipped_as_duplicate": False
            })
            result["text_blocks"].extend(frame_blocks)
            result["keyframes_processed"] += 1

        result["extracted_text"] = " ".join(all_unique_texts)
        result["avg_confidence"] = round(float(np.mean(all_confidences)), 3) if all_confidences else 0.0
        result["status"] = "success"
        print(f"[{job_id}] Keyframe OCR complete: {result['keyframes_processed']} processed, "
              f"{result['keyframes_skipped_duplicate']} skipped duplicate, "
              f"{len(all_unique_texts)} unique text snippets found.")

    except ImportError:
        print(f"[{job_id}] easyocr not installed — keyframe OCR unavailable.")
        result["status"] = "unavailable"
    except Exception as e:
        print(f"[{job_id}] Video keyframe OCR non-fatal failure: {e}")
        result["status"] = "error"
    finally:
        if reader is not None:
            del reader
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return result
