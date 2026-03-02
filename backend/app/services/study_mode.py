"""
Study Mode service — generates MCQs and short-answer questions
grounded entirely in subject chunks.

Every generated item is citation-verified before being returned.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schema import Citation, MCQItem, MCQOption, ShortAnswerItem, StudyResponse
from app.services import llm_client
from app.services.retriever import RetrievedChunk

logger = get_logger(__name__)

# ── Prompt IDs (PROMPT_STUDY_MCQ, PROMPT_STUDY_SA) ───────────

_MCQ_SYSTEM = """\
You are a study-material generator. Create multiple-choice questions STRICTLY from the provided CONTEXT.
Do NOT introduce facts outside the context.
Return a JSON array of MCQ objects. Each object must match exactly:
{{
  "question": "string",
  "options": [
    {{"label":"A","text":"string","is_correct":false}},
    {{"label":"B","text":"string","is_correct":true}},
    {{"label":"C","text":"string","is_correct":false}},
    {{"label":"D","text":"string","is_correct":false}}
  ],
  "explanation": "string (cite the relevant sentence from context)",
  "difficulty": "easy|medium|hard",
  "chunk_id": "string (chunk_id that supports the correct answer)"
}}
Generate exactly {count} MCQs. Only one option must be is_correct=true per question.
No prose outside the JSON array. No markdown fences.
"""

_SA_SYSTEM = """\
You are a study-material generator. Create short-answer questions STRICTLY from the provided CONTEXT.
Return a JSON array of short-answer objects. Each object must match exactly:
{{
  "question": "string",
  "answer": "string (direct quote or close paraphrase from context)",
  "chunk_id": "string (chunk_id that supports the answer)"
}}
Generate exactly {count} short-answer items. No prose outside the JSON array. No markdown fences.
"""

_CONTEXT_USER = """\
CONTEXT:
{context}

TOPIC FOCUS: {topic}
"""


def _format_context(chunks: list[RetrievedChunk], chunk_texts: dict[str, dict[str, Any]]) -> str:
    parts = []
    for rc in chunks:
        info = chunk_texts.get(rc.chunk_id, {})
        parts.append(
            f"[chunk_id={rc.chunk_id}] file={info.get('file','?')}  "
            f"pages={info.get('page_start','?')}-{info.get('page_end','?')}\n"
            f"{info.get('text','')}"
        )
    return "\n\n---\n\n".join(parts)


def _extract_json_array(raw: str) -> list[dict[str, Any]] | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                if isinstance(obj, list):
                    return obj
            except json.JSONDecodeError:
                pass
    return None


async def generate_study_material(
    subject_id: str,
    subject_name: str,
    retrieved_chunks: list[RetrievedChunk],
    chunk_texts: dict[str, dict[str, Any]],  # chunk_id -> {text, file, page_start, page_end}
    topic: str | None,
    mcq_count: int = 5,
    short_answer_count: int = 3,
) -> StudyResponse:
    """
    Generate and citation-verify MCQs and short answers.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
    )
    topic_str = topic or f"the main topics in {subject_name}"
    context_str = _format_context(retrieved_chunks, chunk_texts)

    # ─── MCQs ───────────────────────────────────────────────
    mcq_system = _MCQ_SYSTEM.format(count=mcq_count)
    mcq_user = _CONTEXT_USER.format(context=context_str, topic=topic_str)

    mcq_response = await client.chat.completions.create(
        model=settings.openai_gen_model,
        messages=[
            {"role": "system", "content": mcq_system},
            {"role": "user", "content": mcq_user},
        ],
        temperature=0.3,
        max_tokens=3000,
    )
    mcq_raw = mcq_response.choices[0].message.content or ""

    # ─── Short answers ───────────────────────────────────────
    sa_system = _SA_SYSTEM.format(count=short_answer_count)
    sa_response = await client.chat.completions.create(
        model=settings.openai_gen_model,
        messages=[
            {"role": "system", "content": sa_system},
            {"role": "user", "content": _CONTEXT_USER.format(context=context_str, topic=topic_str)},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    sa_raw = sa_response.choices[0].message.content or ""

    # ─── Parse & verify MCQs ─────────────────────────────────
    mcqs: list[MCQItem] = []
    raw_mcqs = _extract_json_array(mcq_raw) or []
    for item in raw_mcqs:
        chunk_id = item.get("chunk_id", "")
        info = chunk_texts.get(chunk_id, {})
        if not info:
            continue  # skip unverifiable items
        citation = Citation(
            file=info.get("file", "unknown"),
            page_start=info.get("page_start", 1),
            page_end=info.get("page_end", 1),
            chunk_id=chunk_id,
            score=next((r.score for r in retrieved_chunks if r.chunk_id == chunk_id), 0.0),
        )
        options = [
            MCQOption(
                label=o.get("label", "?"),
                text=o.get("text", ""),
                is_correct=bool(o.get("is_correct", False)),
            )
            for o in item.get("options", [])
        ]
        mcqs.append(
            MCQItem(
                question=item.get("question", ""),
                options=options,
                explanation=item.get("explanation", ""),
                difficulty=item.get("difficulty", "medium"),  # type: ignore[arg-type]
                citation=citation,
            )
        )

    # ─── Parse & verify short answers ────────────────────────
    short_answers: list[ShortAnswerItem] = []
    raw_sas = _extract_json_array(sa_raw) or []
    for item in raw_sas:
        chunk_id = item.get("chunk_id", "")
        info = chunk_texts.get(chunk_id, {})
        if not info:
            continue
        citation = Citation(
            file=info.get("file", "unknown"),
            page_start=info.get("page_start", 1),
            page_end=info.get("page_end", 1),
            chunk_id=chunk_id,
            score=next((r.score for r in retrieved_chunks if r.chunk_id == chunk_id), 0.0),
        )
        short_answers.append(
            ShortAnswerItem(
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                citation=citation,
            )
        )

    logger.info(
        "Study material generated",
        extra={"subject_id": subject_id, "mcqs": len(mcqs), "short_answers": len(short_answers)},
    )
    return StudyResponse(mcqs=mcqs, short_answers=short_answers)
