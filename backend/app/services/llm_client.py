"""
LLM client — wraps OpenAI for generation and claim verification.

Two responsibilities:
  generate()  — draft answer as strict JSON using PROMPT_GEN_SYSTEM.
  verify()    — YES/NO entailment check using PROMPT_VERIFY_CLAIM.

All prompt text lives in docs/PROMPTS.md and is referenced by ID here.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import openai
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
        )
    return _client


# ── Prompt templates (IDs match docs/PROMPTS.md) ─────────────

PROMPT_GEN_SYSTEM = """\
You are a strict closed-book question-answering assistant.
You may ONLY use information present in the CONTEXT provided below.
Do NOT use any external knowledge, general knowledge, or assumptions.
If the answer cannot be derived from the CONTEXT, return ONLY the exact string:
  Not found in your notes for {subject}

You MUST respond with a single valid JSON object matching this schema exactly:
{{
  "answer": "string",
  "citations": [
    {{"file": "string", "page_start": 1, "page_end": 1, "chunk_id": "string", "score": 0.0}}
  ],
  "evidence_snippets": ["string"],
  "confidence": "High|Medium|Low"
}}
No prose before or after the JSON. No markdown code fences.
"""

PROMPT_GEN_USER = """\
CONTEXT:
{context}

QUESTION: {question}
"""

PROMPT_VERIFY_CLAIM = """\
Your task is to determine whether the following CLAIM is supported by the CONTEXT.
Answer ONLY with a single word: YES or NO.

CONTEXT:
{context}

CLAIM: {claim}
"""


# ── Helpers ───────────────────────────────────────────────────

def _format_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into labeled CONTEXT block."""
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"[{i}] file={c['file']}  pages={c['page_start']}-{c['page_end']}  chunk_id={c['chunk_id']}\n{c['text']}"
        )
    return "\n\n---\n\n".join(parts)


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Try to extract a JSON object from a potentially messy LLM string."""
    raw = raw.strip()
    # Remove markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to find a JSON object substring
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


# ── Public API ────────────────────────────────────────────────

async def generate(
    question: str,
    chunks: list[dict[str, Any]],
    subject: str,
) -> dict[str, Any] | str:
    """
    Generate an answer from retrieved chunks.

    Returns either:
      - A dict conforming to the response JSON schema, or
      - The exact refusal string if LLM signals no evidence.
    """
    client = _get_client()
    context = _format_context(chunks)
    system = PROMPT_GEN_SYSTEM.format(subject=subject)
    user = PROMPT_GEN_USER.format(context=context, question=question)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_gen_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=1500,
        )
    except openai.APIError as exc:
        logger.error("LLM generate failed", extra={"error": str(exc)})
        raise

    raw = response.choices[0].message.content or ""
    logger.debug("LLM generate raw", extra={"raw": raw[:200]})

    # Check if the model returned the refusal phrase
    refusal_check = settings.refusal(subject)
    if refusal_check.lower() in raw.lower() or raw.strip().startswith("Not found"):
        return refusal_check

    parsed = _extract_json(raw)
    if parsed is None:
        logger.warning("LLM response could not be parsed as JSON — treating as refusal")
        return refusal_check

    return parsed


async def verify_claim(claim: str, context_chunks: list[dict[str, Any]]) -> bool:
    """
    Entailment check: is the CLAIM supported by the CONTEXT?
    Returns True if YES, False if NO.
    """
    client = _get_client()
    context = _format_context(context_chunks)
    prompt = PROMPT_VERIFY_CLAIM.format(context=context, claim=claim)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_gen_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=5,
        )
    except openai.APIError as exc:
        logger.error("LLM verify failed", extra={"error": str(exc)})
        return False  # fail safe — treat as unsupported

    answer = (response.choices[0].message.content or "").strip().upper()
    logger.debug("Claim verification result", extra={"claim": claim[:60], "result": answer})
    return answer.startswith("YES")
