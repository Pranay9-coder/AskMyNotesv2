"""
Grounding score service.

Formula (as documented in PLAN.md and docs/PROMPTS.md):
  grounding_score = round(
      (0.5 × top_similarity + 0.3 × support_ratio + 0.2 × evidence_overlap) × 100
  )

Confidence thresholds:
  High   >= 75
  Medium >= 50
  Low    < 50
"""
from __future__ import annotations

from typing import Literal

from app.models.schema import GroundingDetail


def compute_score(
    top_similarity: float,
    support_ratio: float,
    evidence_overlap: float,
) -> tuple[int, Literal["High", "Medium", "Low"]]:
    """
    Returns (grounding_score 0-100, confidence level).

    Args:
        top_similarity  : best cosine score among retrieved chunks (0..1)
        support_ratio   : supported_claims / total_claims (0..1)
        evidence_overlap: fraction of answer tokens in evidence snippets (0..1)
    """
    raw = (0.5 * top_similarity + 0.3 * support_ratio + 0.2 * evidence_overlap) * 100
    score = max(0, min(100, round(raw)))

    if score >= 75:
        confidence: Literal["High", "Medium", "Low"] = "High"
    elif score >= 50:
        confidence = "Medium"
    else:
        confidence = "Low"

    return score, confidence


def build_grounding_detail(
    top_similarity: float,
    support_ratio: float,
    evidence_overlap: float,
) -> GroundingDetail:
    return GroundingDetail(
        top_similarity=round(top_similarity, 4),
        support_ratio=round(support_ratio, 4),
        evidence_overlap=round(evidence_overlap, 4),
    )
