import os
import gc
import io
import base64
import torch
import cv2
from PIL import Image
from torchvision import transforms
import numpy as np

from src.config import get_device, get_stage_config, get_vision_config, get_vision_detector_config, get_threshold, get_vision_threshold

def estimate_mouth_region_motion(frame_paths: list) -> float:
    """
    Estimates optical motion and edge variance in the mouth region (viseme area).
    Synthetic lip-sync / reenactment overlays (Wav2Lip, DeepFaceLive) often show
    localized boundary blending jitter or unnatural stillness compared to full-face dynamics.
    """
    if len(frame_paths) < 2:
        return 0.0
    mouth_diffs = []
    prev_mouth = None
    for p in frame_paths:
        if not os.path.exists(p):
            continue
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        h, w = img.shape
        # Lower third center is the mouth region (y: 60%-95%, x: 25%-75%)
        mouth = img[int(h * 0.60):int(h * 0.95), int(w * 0.25):int(w * 0.75)]
        mouth = cv2.resize(mouth, (64, 48))
        if prev_mouth is not None:
            diff = float(np.mean(cv2.absdiff(mouth, prev_mouth)))
            mouth_diffs.append(diff)
        prev_mouth = mouth
    if not mouth_diffs:
        return 0.0
    return float(np.mean(mouth_diffs))

def generate_srm_heatmap_base64(image_path: str, model) -> str:
    """
    Generates a color-mapped forensic noise residual heatmap for explainability.
    Highlights facial regions with high-frequency GAN synthesis artifacts.
    Returns a data URI string (data:image/jpeg;base64,...).
    """
    try:
        orig_img = cv2.imread(image_path)
        if orig_img is None:
            return ""

        orig_h, orig_w = orig_img.shape[:2]

        # Pass through SRM layer in model
        rgb_img = cv2.cvtColor(orig_img, cv2.COLOR_BGR2RGB)
        tensor_img = transforms.ToTensor()(Image.fromarray(rgb_img)).unsqueeze(0)

        device = next(model.parameters()).device
        tensor_img = tensor_img.to(device)

        with torch.no_grad():
            srm_out = model.srm(tensor_img).squeeze(0).cpu().numpy()

        # Calculate residual energy map across the 3 SRM filters
        residual_energy = np.mean(np.abs(srm_out), axis=0)
        norm_map = cv2.normalize(residual_energy, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        norm_map = cv2.resize(norm_map, (orig_w, orig_h))

        # Apply Jet colormap (Blue=Natural texture, Red=Anomalous high-frequency synthesis noise)
        heatmap = cv2.applyColorMap(norm_map, cv2.COLORMAP_JET)

        # Blend with original image
        blended = cv2.addWeighted(orig_img, 0.6, heatmap, 0.4, 0)

        # Encode to base64 JPEG
        _, buffer = cv2.imencode('.jpg', blended, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        b64_str = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        print(f"[EXPLAINABILITY] Failed to generate heatmap: {e}")
        return ""

def run_stage2_vision(face_frames_paths: list, job_id: str):
    """
    Runs the vision deepfake detection model on the extracted face frames.
    Uses HybridDeepfakeDetector (EfficientNet-B4 + Xception SRM) and cross-modal mouth activity tracking.
    Returns:
        dict: {
            "avg_score": float,
            "max_score": float,
            "peak_frame": str or None,
            "temporal_variance": float,
            "mouth_motion_activity": float,
            "heatmap_base64": str or None
        }
    """
    print(f"[{job_id}] Running Stage 2: Vision Deepfake Detection")
    stage_config = get_stage_config("stage2_vision")
    vision_cfg = get_vision_config()
    detector_cfg = get_vision_detector_config()
    device = "cpu" if stage_config.get("use_cpu") else get_device()
    threshold = get_vision_threshold()

    backend_name = detector_cfg.get("backend") or "hybrid_phase2"
    early_exit_frames = vision_cfg.get("early_exit_frame_count", 4)
    early_exit_score = vision_cfg.get("early_exit_score", 0.92)
    consensus_weight = vision_cfg.get("consensus_top_weight", 0.65)
    consensus_min_frames = vision_cfg.get("consensus_min_frames", 3)

    result = {
        "avg_score": 0.0,
        "max_score": 0.0,
        "peak_frame": None,
        "temporal_variance": 0.0,
        "mouth_motion_activity": 0.0,
        "heatmap_base64": None,
        "model_backend": backend_name,
        "model_id": None,
        "threshold_applied": threshold
    }

    if not face_frames_paths:
        print(f"[{job_id}] No face frames provided. Skipping vision stage.")
        return result

    backend = None
    try:
        # Cross-modal mouth motion dynamics (Viseme analysis)
        result["mouth_motion_activity"] = estimate_mouth_region_motion(face_frames_paths)

        print(f"[{job_id}] Initializing Vision Backend '{backend_name}' on {device}...")
        from src.stages.backends import get_vision_backend
        backend = get_vision_backend(backend_name=backend_name, device=device)
        result["model_backend"] = backend.backend_name
        result["model_id"] = backend.model_id
        result["weights_path"] = getattr(backend, "weights_path", None)
        result["is_finetuned"] = getattr(backend, "is_finetuned", False)
        result["checkpoint_source"] = getattr(backend, "checkpoint_source", backend.model_id)

        print(f"[{job_id}] Initialized Vision Backend '{backend.backend_name}'. Checkpoint: {result['checkpoint_source']}, Fine-Tuned: {result['is_finetuned']}, Threshold: {threshold:.2f} (higher=fake)")

        scores = []
        best_frame = None
        max_s = -1.0
        early_exit_triggered = False

        print(f"[{job_id}] Processing {len(face_frames_paths)} frames (early-exit at {early_exit_frames} consecutive frames >{early_exit_score:.2f})...")
        consecutive_high = 0
        for frame_path in face_frames_paths:
            if not os.path.exists(frame_path):
                continue

            fake_prob = backend.predict_frame(frame_path)
            scores.append(fake_prob)

            if fake_prob > max_s:
                max_s = fake_prob
                best_frame = frame_path

            # Early-exit: N consecutive high-confidence frames -> no need to process more
            if fake_prob > early_exit_score:
                consecutive_high += 1
                if consecutive_high >= early_exit_frames:
                    print(f"[{job_id}] Early-exit triggered after {len(scores)} frames (score {fake_prob:.3f} > {early_exit_score}).")
                    early_exit_triggered = True
                    break
            else:
                consecutive_high = 0

        if scores:
            scores_sorted = sorted(scores, reverse=True)
            k = min(3, len(scores_sorted))
            top_k_mean = float(np.mean(scores_sorted[:k]))
            anti_weight = round(1.0 - consensus_weight, 4)
            median_score = float(np.median(scores))
            high_ratio = sum(1 for s in scores if s >= threshold) / len(scores)

            # Temporal consensus aggregation with interpretable anomaly gating
            if early_exit_triggered:
                consensus_score = float(max_s)
                aggregation_mode = "early_exit"
            elif len(scores) >= consensus_min_frames:
                peak = float(scores_sorted[0])
                s2 = float(scores_sorted[1]) if len(scores_sorted) > 1 else peak
                # Isolated Outlier Spike: a single frame anomaly (e.g. camera flash, glare, rapid cut)
                # where peak is elevated (>=0.40) but drops sharply to a clean frame 2 (peak - s2 >= 0.30, s2 < 0.20, median < 0.10).
                # Rather than crushing multi-frame evidence with median, only single-frame outliers are attenuated.
                if peak >= 0.40 and (peak - s2 >= 0.30) and s2 < 0.20 and median_score < 0.10:
                    consensus_score = float(0.35 * peak + 0.65 * s2)
                    aggregation_mode = "isolated_outlier_attenuation"
                else:
                    # Sustained multi-frame consensus: combines top-k cluster and peak
                    # without artificial median suppression that crushes subtle generative face-swaps.
                    consensus_score = float(consensus_weight * top_k_mean + anti_weight * max_s)
                    aggregation_mode = "sustained_consensus"
            else:
                consensus_score = float(max_s)
                aggregation_mode = "peak_fallback"

            result["avg_score"] = float(np.mean(scores))
            result["max_score"] = consensus_score
            result["raw_peak_score"] = float(max_s)
            result["peak_frame"] = best_frame
            result["temporal_variance"] = float(np.var(scores))
            result["frame_scores"] = [float(round(s, 4)) for s in scores]
            result["top_k_mean"] = float(round(top_k_mean, 4))
            result["median_score"] = float(round(median_score, 4))
            result["aggregation_mode"] = aggregation_mode
            result["aggregation_details"] = {
                "mode": aggregation_mode,
                "peak": float(round(max_s, 4)),
                "top_k_mean": float(round(top_k_mean, 4)),
                "median": float(round(median_score, 4)),
                "high_ratio": float(round(high_ratio, 4)),
                "early_exit_triggered": early_exit_triggered,
                "frames_evaluated": len(scores)
            }

            # Generate Explainability Saliency Heatmap for the most suspicious frame
            if best_frame and os.path.exists(best_frame):
                result["heatmap_base64"] = backend.generate_heatmap(best_frame)

        print(f"[{job_id}] Vision complete [{result['model_backend']}]. Calibrated Score: {result['max_score']:.4f} (Peak: {max_s:.4f}), Avg: {result['avg_score']:.4f}, Threshold: {threshold:.2f}")

    except Exception as e:
        print(f"[{job_id}] Vision stage failed locally: {e}")
        # Try cloud fallback if enabled in config.yaml
        try:
            from src.backup_api import check_sightengine_deepfake
            from src.config import is_cloud_fallback_enabled
            if is_cloud_fallback_enabled() and face_frames_paths:
                cloud_res = check_sightengine_deepfake(face_frames_paths[0])
                if cloud_res:
                    print(f"[{job_id}] Cloud fallback succeeded (Sightengine): {cloud_res['score']:.4f}")
                    result["max_score"] = cloud_res["score"]
                    result["avg_score"] = cloud_res["score"]
                    result["peak_frame"] = face_frames_paths[0]
                    result["backup_provider"] = "sightengine"
            else:
                # Re-raise so errors are not silently ignored
                raise e
        except Exception as cloud_err:
            print(f"[{job_id}] Cloud fallback failed or not enabled: {cloud_err}")
            raise e
    finally:
        if backend is not None:
            backend.close()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return result
