"""
Tests — Grounding score formula.
"""
from app.services.grounding import compute_score


def test_perfect_score():
    score, conf = compute_score(1.0, 1.0, 1.0)
    assert score == 100
    assert conf == "High"


def test_zero_score():
    score, conf = compute_score(0.0, 0.0, 0.0)
    assert score == 0
    assert conf == "Low"


def test_formula_weighting():
    # 0.5*0.8 + 0.3*1.0 + 0.2*0.5 = 0.4 + 0.3 + 0.1 = 0.8 → 80
    score, conf = compute_score(0.8, 1.0, 0.5)
    assert score == 80
    assert conf == "High"


def test_medium_confidence():
    # ~0.55*100 = 55 → Medium
    score, conf = compute_score(0.5, 0.7, 0.5)
    assert 50 <= score < 75
    assert conf == "Medium"


def test_low_confidence():
    score, conf = compute_score(0.2, 0.4, 0.1)
    assert score < 50
    assert conf == "Low"


def test_score_clamped_to_range():
    score, _ = compute_score(2.0, 2.0, 2.0)  # values > 1.0
    assert 0 <= score <= 100
