"""
Tests — Verifier service (no real LLM calls — mocked).
Covers: verbatim check, entailment mock, support ratio, rejection, acceptance.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.verifier import (
    ClaimResult,
    VerificationResult,
    _verbatim_present,
    compute_evidence_overlap,
    verify_answer,
)

_CHUNKS = [
    {
        "chunk_id": "c1",
        "text": "Photosynthesis is the process by which plants use sunlight to produce glucose.",
        "file": "bio.pdf",
        "page_start": 1,
        "page_end": 1,
    },
    {
        "chunk_id": "c2",
        "text": "Mitosis is cell division that produces two identical daughter cells.",
        "file": "bio.pdf",
        "page_start": 2,
        "page_end": 2,
    },
]


# ── Verbatim check ────────────────────────────────────────────

def test_verbatim_present_exact():
    claim = "plants use sunlight to produce glucose"
    result = _verbatim_present(claim, _CHUNKS)
    assert result is not None


def test_verbatim_present_not_found():
    result = _verbatim_present("neurons fire in the brain", _CHUNKS)
    assert result is None


def test_verbatim_too_short_returns_none():
    # Fewer than 4 words should not match
    result = _verbatim_present("plants use", _CHUNKS)
    assert result is None


# ── Evidence overlap ──────────────────────────────────────────

def test_evidence_overlap_full():
    answer = "plants use sunlight to produce glucose"
    snippets = ["plants use sunlight to produce glucose from the notes"]
    overlap = compute_evidence_overlap(answer, snippets)
    assert overlap > 0.8


def test_evidence_overlap_empty_snippets():
    overlap = compute_evidence_overlap("some answer", [])
    assert overlap == 0.0


def test_evidence_overlap_partial():
    answer = "mitosis is cell division producing daughter cells"
    snippets = ["cell division occurs in mitosis"]
    overlap = compute_evidence_overlap(answer, snippets)
    assert 0.0 < overlap < 1.0


# ── Full pipeline (LLM mocked) ───────────────────────────────

@pytest.mark.asyncio
async def test_verify_answer_all_verbatim():
    answer = "Photosynthesis is the process by which plants use sunlight to produce glucose."
    with patch("app.services.verifier.llm_client.verify_claim", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True  # should not be called for verbatim matches
        result = await verify_answer(answer, _CHUNKS)
    assert result.accepted is True
    assert result.support_ratio == 1.0


@pytest.mark.asyncio
async def test_verify_answer_llm_entailment_passes():
    answer = "Plants convert sunlight into sugar through photosynthesis."  # paraphrase
    with patch("app.services.verifier.llm_client.verify_claim", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True
        result = await verify_answer(answer, _CHUNKS)
    assert result.accepted is True


@pytest.mark.asyncio
async def test_verify_answer_unsupported_claim_rejected():
    answer = "The moon is made of cheese and orbits the Earth."
    with patch("app.services.verifier.llm_client.verify_claim", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = False  # LLM says unsupported
        result = await verify_answer(answer, _CHUNKS)
    assert result.accepted is False
    assert len(result.unsupported_claims) > 0


@pytest.mark.asyncio
async def test_verify_empty_answer():
    result = await verify_answer("", _CHUNKS)
    assert result.accepted is False
