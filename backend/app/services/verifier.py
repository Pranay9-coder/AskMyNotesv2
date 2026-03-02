"""
Verifier service — two-layer claim verification.

Layer 1: Verbatim / near-verbatim string check against stored chunks.
Layer 2: LLM entailment check for claims not present verbatim.

Pipeline:
  1. Split answer into atomic claims (sentence-level).
  2. For each claim: try verbatim first; if fails -> LLM verify.
  3. If any claim unsupported -> reject entire answer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services import llm_client

logger = get_logger(__name__)


# ── Sentence tokenizer ────────────────────────────────────────

try:
    import spacy  # type: ignore

    _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner", "tagger"])
    _nlp.add_pipe("sentencizer")

    def _split_sentences(text: str) -> list[str]:
        doc = _nlp(text)
        return [s.text.strip() for s in doc.sents if s.text.strip()]

except Exception:
    logger.warning("spaCy not available — using regex sentence splitter")

    def _split_sentences(text: str) -> list[str]:
        # Simple fallback: split on sentence-ending punctuation
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]


# ── Data structures ───────────────────────────────────────────

@dataclass
class ClaimResult:
    claim: str
    supported: bool
    method: str  # "verbatim" | "entailment" | "unsupported"
    evidence_snippet: str | None = None


@dataclass
class VerificationResult:
    accepted: bool
    claim_results: list[ClaimResult] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    support_ratio: float = 0.0


# ── Verbatim check ────────────────────────────────────────────

def _normalise_for_match(text: str) -> str:
    """Lowercase, collapse whitespace for loose verbatim matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _verbatim_present(claim: str, chunks: list[dict[str, Any]]) -> str | None:
    """
    Returns the matching chunk text excerpt if the claim
    (or a close normalised version) is found verbatim in any chunk.
    """
    norm_claim = _normalise_for_match(claim)
    # Remove very short or trivial claims
    if len(norm_claim.split()) < 4:
        return None  # too short to be meaningful evidence
    for chunk in chunks:
        norm_chunk = _normalise_for_match(chunk["text"])
        if norm_claim in norm_chunk:
            return chunk["text"][:300]  # return a trim of the matching chunk
    return None


# ── Evidence overlap ──────────────────────────────────────────

def compute_evidence_overlap(answer: str, snippets: list[str]) -> float:
    """
    Fraction of non-trivial answer tokens found in evidence snippets.
    """
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "of", "in", "to", "and", "or", "it"}
    answer_tokens = {
        t.lower() for t in re.findall(r"\b\w+\b", answer) if t.lower() not in stop_words and len(t) > 2
    }
    snippet_tokens = {
        t.lower()
        for s in snippets
        for t in re.findall(r"\b\w+\b", s)
        if t.lower() not in stop_words and len(t) > 2
    }
    if not answer_tokens:
        return 0.0
    overlap = answer_tokens & snippet_tokens
    return len(overlap) / len(answer_tokens)


# ── Main verification pipeline ────────────────────────────────

async def verify_answer(
    answer: str,
    chunks: list[dict[str, Any]],
) -> VerificationResult:
    """
    Verify all atomic claims in an answer against retrieved chunks.

    Returns VerificationResult with accepted=True only if every
    atomic claim is supported.
    """
    claims = _split_sentences(answer)
    if not claims:
        return VerificationResult(accepted=False, support_ratio=0.0)

    claim_results: list[ClaimResult] = []

    for claim in claims:
        # Layer 1: verbatim check
        snippet = _verbatim_present(claim, chunks)
        if snippet is not None:
            claim_results.append(
                ClaimResult(claim=claim, supported=True, method="verbatim", evidence_snippet=snippet)
            )
            continue

        # Layer 2: LLM entailment
        supported = await llm_client.verify_claim(claim, chunks)
        if supported:
            claim_results.append(
                ClaimResult(claim=claim, supported=True, method="entailment", evidence_snippet=None)
            )
        else:
            claim_results.append(
                ClaimResult(claim=claim, supported=False, method="unsupported", evidence_snippet=None)
            )
            logger.info("Unsupported claim detected", extra={"claim": claim[:80]})

    unsupported = [r.claim for r in claim_results if not r.supported]
    total = len(claim_results)
    supported_count = total - len(unsupported)
    support_ratio = supported_count / total if total > 0 else 0.0

    accepted = len(unsupported) == 0
    return VerificationResult(
        accepted=accepted,
        claim_results=claim_results,
        unsupported_claims=unsupported,
        support_ratio=support_ratio,
    )
