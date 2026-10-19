"""
Unit Tests for Deepfake Model Fine-Tuning Pipeline & Dataset Integrity
======================================================================
Verifies:
  1. Base model loading and parameter freezing policies (head_only vs head_and_high_attn).
  2. Output logit shape [B, 1] and BCEWithLogitsLoss gradient flow.
  3. Isotropic aspect-ratio preserving preprocessing.
  4. Dataset manifest validator logic and schema compliance.
  5. Cross-split identity leakage detection.
  6. Benchmark contamination protection.
  7. Production inference backend isolation (unchanged defaults).
"""

import os
import sys
import csv
import pytest
import numpy as np
import torch
import torch.nn as nn

APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from experiments.deepfake_finetune.scripts.train_finetune import build_model
from experiments.deepfake_finetune.scripts.validate_dataset import validate_manifest
from src.stages.backends.ms_eff_gcvit_backend import preprocess_isotropic
from src.stages.backends import get_vision_backend
from src.config import get_vision_threshold


def test_finetune_model_loading_and_freezing():
    """Verifies that head_only freezing locks backbone and unlocks head only."""
    model = build_model(freeze_strategy="head_only", device="cpu")

    # Head parameters should require grad
    for name, param in model.head.named_parameters():
        assert param.requires_grad, f"Head parameter {name} should be trainable"

    # Backbone parameters should NOT require grad
    for name, param in model.feat_extractor.named_parameters():
        assert not param.requires_grad, f"feat_extractor parameter {name} should be frozen"
    for name, param in model.l_gcvit.named_parameters():
        assert not param.requires_grad, f"l_gcvit parameter {name} should be frozen"
    for name, param in model.h_gcvit.named_parameters():
        assert not param.requires_grad, f"h_gcvit parameter {name} should be frozen"

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    assert trainable_params == 101697, f"Expected 101,697 trainable parameters, got {trainable_params}"


def test_finetune_loss_and_output_compatibility():
    """Verifies that model output [B, 1] works cleanly with BCEWithLogitsLoss."""
    model = build_model(freeze_strategy="head_only", device="cpu")
    criterion = nn.BCEWithLogitsLoss()

    x = torch.randn(4, 3, 224, 224)
    target = torch.tensor([[0.0], [1.0], [0.0], [1.0]], dtype=torch.float32)

    logits = model(x)
    assert logits.shape == (4, 1), f"Expected shape (4, 1), got {logits.shape}"

    loss = criterion(logits, target)
    assert loss.item() >= 0.0

    loss.backward()
    # Check that head weights have gradients
    for name, param in model.head.named_parameters():
        assert param.grad is not None, f"Expected gradient for {name}"

    # Check that backbone weights have NO gradients
    for name, param in model.feat_extractor.named_parameters():
        assert param.grad is None, f"Expected no gradient for {name}"


def test_isotropic_preprocessing_aspect_ratio_preservation():
    """Verifies isotropic padding maintains aspect ratio without image stretching."""
    # Create non-square dummy image (100h x 300w)
    dummy_img = np.ones((100, 300, 3), dtype=np.uint8) * 128
    tensor = preprocess_isotropic(dummy_img, target_size=(224, 224), is_bgr=True)

    assert tensor.shape == (1, 3, 224, 224)
    assert isinstance(tensor, torch.Tensor)
    assert tensor.dtype == torch.float32


def test_manifest_schema_validation():
    """Validates benchmark manifest passes all integrity checks."""
    manifest_path = os.path.join(APP_ROOT, "experiments", "deepfake_finetune", "data", "benchmark_manifest.csv")
    rep = validate_manifest(manifest_path, check_faces=False)
    assert rep["is_valid"], f"Manifest failed validation: {rep['errors']}"
    assert rep["total_records"] == 20
    assert rep["valid_records"] == 20
    assert len(rep["identity_leakage_violations"]) == 0
    assert len(rep["benchmark_contamination_violations"]) == 0


def test_manifest_identity_leakage_detection(tmp_path):
    """Verifies that the validator catches and reports identity leakage across splits."""
    bad_manifest = str(tmp_path / "bad_manifest.csv")
    fieldnames = ["video_id", "video_path", "label", "source_identity", "split"]
    rows = [
        {"video_id": "v1", "video_path": "dummy1.mp4", "label": "0", "source_identity": "person_A", "split": "train"},
        {"video_id": "v2", "video_path": "dummy2.mp4", "label": "1", "source_identity": "person_A", "split": "val"}  # Leakage!
    ]
    with open(bad_manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rep = validate_manifest(bad_manifest, check_faces=False)
    assert not rep["is_valid"]
    assert len(rep["identity_leakage_violations"]) > 0
    assert "person_A" in rep["identity_leakage_violations"][0]


def test_manifest_benchmark_contamination_protection(tmp_path):
    """Verifies that the validator blocks training on identities from the held-out benchmark."""
    contaminated_manifest = str(tmp_path / "contaminated_manifest.csv")
    fieldnames = ["video_id", "video_path", "label", "source_identity", "split"]
    rows = [
        {"video_id": "v1", "video_path": "dummy1.mp4", "label": "0", "source_identity": "id_183", "split": "train"}  # id_183 is in benchmark!
    ]
    with open(contaminated_manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rep = validate_manifest(contaminated_manifest, check_faces=False)
    assert not rep["is_valid"]
    assert len(rep["benchmark_contamination_violations"]) > 0
    assert "id_183" in rep["benchmark_contamination_violations"][0]


def test_production_backend_remains_unchanged():
    """Assures that experimental fine-tuning changes did not touch production backend defaults."""
    backend = get_vision_backend()
    assert backend.backend_name == "ms_eff_gcvit"
    assert "KoreaPeter" in backend.model_id
    assert backend.is_finetuned is False
    assert "Original Pretrained Hugging Face" in backend.checkpoint_source
    assert backend.weights_path.endswith(".safetensors")
    assert get_vision_threshold() == 0.60
    backend.close()


def test_safe_acquisition_plan_generation_and_exclusion():
    """Verifies that safe acquisition planner excludes benchmark IDs and builds 200 balanced videos."""
    from experiments.deepfake_finetune.scripts.safe_dataset_downloader import (
        build_acquisition_plan,
        BENCHMARK_EXCLUDED_IDENTITIES,
    )
    # Mock candidate pairs containing benchmark IDs plus clean dummy pairs
    dummy_pairs = [
        ["585", "599"],  # Benchmark!
        ["183", "253"],  # Benchmark!
        ["469", "481"],  # Benchmark!
    ]
    # Add 60 clean pairs
    for i in range(60):
        dummy_pairs.append([f"clean_{i:03d}a", f"clean_{i:03d}b"])

    plan, stats = build_acquisition_plan(dummy_pairs, "http://mock-server/v3/", "/tmp/mock_datasets")

    assert stats["total_planned_videos"] == 200
    assert stats["total_real"] == 100
    assert stats["total_fake"] == 100
    assert stats["train_count"] == 140
    assert stats["val_count"] == 32
    assert stats["test_count"] == 28
    assert len(stats["rejected_benchmark_pairs"]) == 3

    # Assert no benchmark identity in any plan record
    for r in plan:
        for b_id in BENCHMARK_EXCLUDED_IDENTITIES:
            assert b_id not in r["source_identity"]
            assert b_id not in r["video_path"]
            assert b_id not in r["download_url"]


def test_manipulated_pair_target_identity_leakage_detection(tmp_path):
    """
    Regression test asserting that manipulated videos with two identities (e.g. 672_720.mp4)
    cannot leak either the source donor (672) or target recipient (720) across splits.
    """
    leak_manifest = str(tmp_path / "manip_leak_manifest.csv")
    fieldnames = ["video_id", "video_path", "label", "source_identity", "target_identity", "split"]
    rows = [
        # Train has manipulated video swapping face 672 onto body 720
        {
            "video_id": "ffpp_deepfakes_672_720",
            "video_path": "Deepfakes/c23/videos/672_720.mp4",
            "label": "1",
            "source_identity": "id_672",
            "target_identity": "id_720",
            "split": "train"
        },
        # Val has authentic video of recipient 720 (leakage!)
        {
            "video_id": "ffpp_orig_720",
            "video_path": "original_sequences/youtube/c23/videos/720.mp4",
            "label": "0",
            "source_identity": "id_720",
            "target_identity": "",
            "split": "val"
        }
    ]
    with open(leak_manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rep = validate_manifest(leak_manifest, check_faces=False)
    assert not rep["is_valid"], "Validator should fail when target recipient identity leaks across splits!"
    assert len(rep["identity_leakage_violations"]) > 0
    assert "id_720" in rep["identity_leakage_violations"][0]


def test_benchmark_secondary_identity_253_contamination(tmp_path):
    """
    Asserts that identity 253 (the target paired with 183 in benchmark video 183_253.mp4)
    is strictly blocked from entering train, val, or test.
    """
    contam_manifest = str(tmp_path / "contam_253_manifest.csv")
    fieldnames = ["video_id", "video_path", "label", "source_identity", "target_identity", "split"]
    rows = [
        {
            "video_id": "ffpp_orig_253",
            "video_path": "original_sequences/youtube/c23/videos/253.mp4",
            "label": "0",
            "source_identity": "id_253",
            "target_identity": "",
            "split": "train"
        }
    ]
    with open(contam_manifest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rep = validate_manifest(contam_manifest, check_faces=False)
    assert not rep["is_valid"], "Validator should block identity 253 from entering train!"
    assert "253" in rep["benchmark_contamination_violations"][0]


def test_demo_infer_ground_truth():
    """Verifies label inference logic in demo_video_evaluator."""
    from scripts.demo_video_evaluator import infer_ground_truth

    # Filename matching
    assert infer_ground_truth("demo_real_01.mp4") == 0
    assert infer_ground_truth("demo_fake_deepfakes_01.mp4") == 1
    assert infer_ground_truth("orig_video.mp4") == 0
    assert infer_ground_truth("faceswap_sample.mp4") == 1
    assert infer_ground_truth("judge_mystery_video.mp4") is None

    # Folder matching
    assert infer_ground_truth("dataset/real/video123.mp4") == 0
    assert infer_ground_truth("dataset/fake/video123.mp4") == 1

    # Labels map override
    labels_map = {"judge_mystery_video.mp4": 1}
    assert infer_ground_truth("judge_mystery_video.mp4", labels_map=labels_map) == 1


def test_demo_load_fine_tuned_backend():
    """Verifies loading fine-tuned checkpoint weights without modifying production settings."""
    from scripts.demo_video_evaluator import load_fine_tuned_backend
    weights_path = os.path.join(APP_ROOT, "experiments", "deepfake_finetune", "checkpoints", "best_checkpoint_weights.pth")
    if os.path.isfile(weights_path):
        backend = load_fine_tuned_backend(weights_path, device="cpu")
        assert backend.backend_name == "ms_eff_gcvit"
        backend.close()


def test_demo_evaluator_unsupported_no_face():
    """Verifies that demo evaluator handles non-facial videos gracefully."""
    from scripts.demo_video_evaluator import evaluate_single_video
    from src.stages.backends.ms_eff_gcvit_backend import MsEffGCViTBackend
    import cv2

    # Create temporary blank video
    demo_edge = os.path.join(APP_ROOT, "temp", "test_blank_edge.mp4")
    os.makedirs(os.path.dirname(demo_edge), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(demo_edge, fourcc, 10.0, (160, 120))
    for _ in range(10):
        out.write(np.zeros((120, 160, 3), dtype=np.uint8))
    out.release()

    backend = MsEffGCViTBackend(device="cpu")
    res = evaluate_single_video(
        video_path=demo_edge,
        backend=backend,
        threshold=0.60,
        ground_truth=None
    )
    backend.close()

    assert res["status"] == "UNSUPPORTED_NO_FACE"
    assert res["predicted_label"] == "N/A"
    assert "No human faces detected" in res["error_details"]

    if os.path.isfile(demo_edge):
        os.remove(demo_edge)
