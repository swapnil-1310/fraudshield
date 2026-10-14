"""
Unit Test: Production Model Output to Fake Probability Conversion
================================================================
Tests the conversion logic used in src/stages/stage2_vision.py:
    fake_prob = max(0.0, min(1.0, 1.0 - prob_real))

Validates behavior with:
1. Exact boundary probabilities (0.0, 1.0, 0.5)
2. Clamping of out-of-bound float values (<0.0, >1.0)
3. Known synthetic logits passed through the model's Sigmoid activation
4. Invariance to numerical precision
"""

import pytest
import math
import torch
import torch.nn as nn


def production_convert_prob_real_to_fake(prob_real: float) -> float:
    """Exact logic extracted from src/stages/stage2_vision.py line 172."""
    return max(0.0, min(1.0, 1.0 - prob_real))


def test_boundary_probabilities():
    # When model outputs certainty of REAL (1.0), fake probability must be 0.0
    assert production_convert_prob_real_to_fake(1.0) == 0.0
    # When model outputs certainty of FAKE (0.0), fake probability must be 1.0
    assert production_convert_prob_real_to_fake(0.0) == 1.0
    # Neutral decision boundary (0.5)
    assert production_convert_prob_real_to_fake(0.5) == 0.5


def test_clamping_out_of_bounds():
    # Numerical instability causing slight overflow/underflow
    assert production_convert_prob_real_to_fake(1.000001) == 0.0
    assert production_convert_prob_real_to_fake(1.5) == 0.0
    assert production_convert_prob_real_to_fake(-0.000001) == 1.0
    assert production_convert_prob_real_to_fake(-0.5) == 1.0


def test_conversion_with_known_synthetic_logits():
    sigmoid = nn.Sigmoid()

    # Logit -> Probability mappings:
    # z = +10.0 -> Sigmoid(10.0) = 0.9999546 -> fake_prob = 0.0000454 (classified REAL)
    z_real = torch.tensor([10.0])
    prob_real = sigmoid(z_real).item()
    fake_prob = production_convert_prob_real_to_fake(prob_real)
    assert math.isclose(prob_real, 0.9999546, rel_tol=1e-4)
    assert math.isclose(fake_prob, 0.0000454, rel_tol=1e-3)
    assert fake_prob < 0.5  # Classified as Real

    # z = -10.0 -> Sigmoid(-10.0) = 0.0000454 -> fake_prob = 0.9999546 (classified FAKE)
    z_fake = torch.tensor([-10.0])
    prob_fake = sigmoid(z_fake).item()
    fake_prob_from_fake = production_convert_prob_real_to_fake(prob_fake)
    assert math.isclose(prob_fake, 0.0000454, rel_tol=1e-3)
    assert math.isclose(fake_prob_from_fake, 0.9999546, rel_tol=1e-4)
    assert fake_prob_from_fake > 0.5  # Classified as Fake

    # z = 0.0 -> Sigmoid(0.0) = 0.5 -> fake_prob = 0.5
    z_zero = torch.tensor([0.0])
    prob_zero = sigmoid(z_zero).item()
    assert production_convert_prob_real_to_fake(prob_zero) == 0.5

    # z = +2.0 -> Sigmoid(2.0) = 0.880797 -> fake_prob = 0.119203
    z_pos2 = torch.tensor([2.0])
    prob_pos2 = sigmoid(z_pos2).item()
    assert math.isclose(production_convert_prob_real_to_fake(prob_pos2), 0.119203, rel_tol=1e-4)

    # z = -2.0 -> Sigmoid(-2.0) = 0.119203 -> fake_prob = 0.880797
    z_neg2 = torch.tensor([-2.0])
    prob_neg2 = sigmoid(z_neg2).item()
    assert math.isclose(production_convert_prob_real_to_fake(prob_neg2), 0.880797, rel_tol=1e-4)


def test_production_threshold_agreement():
    """Validates that a fake_prob > 0.5 occurs if and only if prob_real < 0.5."""
    test_probs = [0.0, 0.1, 0.3, 0.499, 0.5, 0.501, 0.7, 0.9, 1.0]
    for p in test_probs:
        fake_p = production_convert_prob_real_to_fake(p)
        is_classified_fake = (fake_p > 0.5)
        expected_fake = (p < 0.5)
        assert is_classified_fake == expected_fake, f"Discrepancy at prob_real={p}: fake_p={fake_p}"
