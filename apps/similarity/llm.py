"""OpenAI-powered semantic similarity scoring, explanations, and recommendations.

Uses Python's standard library HTTP client so no extra runtime packages are required.
Falls back cleanly to ``apps.similarity.engine`` when ``OPENAI_API_KEY`` is unset or
the OpenAI API is unreachable.
"""

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.conf import settings

from . import engine

OPENAI_BASE_URL = "https://api.openai.com/v1"
MAX_CANDIDATES_FOR_LLM = 8


class OpenAIError(RuntimeError):
    """Raised when an OpenAI API request fails or returns unusable output."""


@dataclass
class LLMMatch:
    candidate_id: int
    score: Decimal
    explanation: str


@dataclass
class LLMAnalysis:
    matches: list
    recommendations: list
    model: str


def is_configured():
    return bool(getattr(settings, "OPENAI_API_KEY", "").strip())


def format_proposal(sections):
    """Render non-empty proposal sections into a compact structured block."""
    lines = []
    for name, (label, _) in engine.SECTIONS.items():
        value = (sections.get(name) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines) or "Empty proposal"


def _post_json(path, payload):
    api_key = getattr(settings, "OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIError("OPENAI_API_KEY is not configured.")
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{OPENAI_BASE_URL}/{path.lstrip('/')}",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(getattr(settings, "OPENAI_TIMEOUT", 25))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise OpenAIError(f"OpenAI HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OpenAIError(f"OpenAI network error: {exc}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpenAIError("OpenAI returned invalid JSON.") from exc


def _vector_cosine(first, second):
    if not first or not second or len(first) != len(second):
        return 0.0
    dot = sum(a * b for a, b in zip(first, second))
    norm = math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second))
    if not norm:
        return 0.0
    return max(0.0, min(dot / norm, 1.0))


def rank_candidates(proposal, candidates, limit=MAX_CANDIDATES_FOR_LLM):
    """Shortlist the closest candidates using OpenAI text embeddings."""
    if not candidates:
        return []
    embedding_model = getattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    inputs = [format_proposal(proposal)] + [format_proposal(sections) for _, sections in candidates]
    data = _post_json("embeddings", {"model": embedding_model, "input": inputs})
    items = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
    if len(items) != len(inputs):
        raise OpenAIError("Unexpected embedding response length.")
    target_vec = items[0].get("embedding")
    ranked = []
    for (candidate_id, sections), item in zip(candidates, items[1:]):
        sim = _vector_cosine(target_vec, item.get("embedding"))
        ranked.append((candidate_id, sections, round(sim * 100, 1)))
    ranked.sort(key=lambda entry: (-entry[2], entry[0]))
    return ranked[:limit]


def _clamp_score(value):
    try:
        score = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise OpenAIError(f"Invalid similarity score: {value!r}") from exc
    if score < Decimal("0.00"):
        return Decimal("0.00")
    if score > Decimal("100.00"):
        return Decimal("100.00")
    return score


def analyze_similarity(proposal, candidates, max_matches=5):
    """Score semantic overlap, explain matches, and generate recommendations via OpenAI."""
    model = getattr(settings, "OPENAI_MODEL", "gpt-6-luna")
    shortlist = rank_candidates(proposal, candidates, limit=max(max_matches + 3, MAX_CANDIDATES_FOR_LLM))
    allowed_ids = {candidate_id for candidate_id, _, _ in shortlist}

    candidate_payload = [
        {
            "candidate_id": candidate_id,
            "embedding_hint_percent": hint,
            "proposal": format_proposal(sections),
        }
        for candidate_id, sections, hint in shortlist
    ]
    missing_sections = [
        label
        for name, (label, _) in engine.SECTIONS.items()
        if name != "category" and not (proposal.get(name) or "").strip()
    ]

    system_prompt = (
        "You evaluate student project proposals for conceptual and functional similarity.\n"
        "Compare the TARGET proposal against each CANDIDATE proposal.\n"
        "Scoring rubric (0 to 100):\n"
        "- 70-100: High similarity — essentially the same problem, solution, and users (even if reworded).\n"
        "- 40-69: Moderate similarity — significant overlap in problem domain or core solution.\n"
        "- 10-39: Low similarity — minor shared theme or partial feature overlap in a related domain.\n"
        "- 0-9: Distinct / unrelated — different domain, problem, and users (do NOT include in matches).\n"
        "Return strict JSON with keys:\n"
        '  "matches": list of objects {"candidate_id": int, "similarity_score": number (10..100), '
        '"explanation": string (1-2 concise sentences explaining the specific overlap)},\n'
        '  "recommendations": list of 2 to 4 concise, actionable strings advising how to make the '
        "target proposal more distinct and complete.\n"
        "Only use candidate_id values provided in the input. Never invent candidates."
    )
    user_payload = {
        "target_proposal": format_proposal(proposal),
        "missing_sections": missing_sections,
        "candidates": candidate_payload,
    }

    response = _post_json(
        "chat/completions",
        {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        },
    )

    choices = response.get("choices") or []
    if not choices:
        raise OpenAIError("OpenAI returned no completion choices.")
    content = (choices[0].get("message") or {}).get("content") or ""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OpenAIError("OpenAI completion content was not valid JSON.") from exc

    seen_ids = set()
    matches = []
    for item in parsed.get("matches") or []:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("candidate_id")
        try:
            candidate_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if candidate_id not in allowed_ids or candidate_id in seen_ids:
            continue
        score = _clamp_score(item.get("similarity_score", 0))
        if score < engine.MIN_SCORE:
            continue
        explanation = str(item.get("explanation") or "").strip()
        if not explanation:
            explanation = "The proposals overlap in problem focus or proposed approach."
        seen_ids.add(candidate_id)
        matches.append(LLMMatch(candidate_id=candidate_id, score=score, explanation=explanation))

    matches.sort(key=lambda item: (-item.score, item.candidate_id))
    matches = matches[:max_matches]

    recommendations = [
        str(item).strip()
        for item in (parsed.get("recommendations") or [])
        if str(item).strip()
    ][:5]
    if not recommendations:
        recommendations = [
            "No similar projects were found. Your idea looks distinct among the available proposals."
            if not matches
            else "Clarify what differentiates your solution, scope, and target users from similar projects."
        ]

    return LLMAnalysis(matches=matches, recommendations=recommendations, model=model)
