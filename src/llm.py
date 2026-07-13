"""Loose Ends — the extraction brain.

A thin, swappable wrapper over the DGrid AI gateway (OpenAI-compatible).
`extract_loose_end(text, context)` classifies a single Slack message into a
loose end (commitment / unanswered question) or noise, returning strict JSON.

Design rules:
- Conservative: false positives are worse than misses.
- Low temperature, small max_tokens — must be fast and reliable.
- Parse defensively (strip code fences, tolerate stray prose).
- Never raise on a bad message: on any error, return a safe "not a loose end".
"""
import json
import logging
import re

from openai import OpenAI

from . import config

log = logging.getLogger("looseends.llm")

_client = OpenAI(api_key=config.DGRID_API_KEY, base_url=config.DGRID_BASE_URL)

SYSTEM_PROMPT = """You are the detection engine for "Loose Ends", a Slack accountability agent.
You read ONE Slack message and decide whether it contains a "loose end" that should be tracked.

There are exactly two kinds of loose end:
1. "commitment" — the author personally promises to do something later.
   Genuine signals: "I'll send the deck Friday", "on it, will fix tonight",
   "I'll take that", "let me get you the numbers by EOD", "I can have it done tomorrow".
2. "unanswered_question" — the message asks a clear, answerable question directed at
   the team/someone, that would matter if it scrolled away.
   e.g. "who owns the staging deploy?", "can someone review PR #42 today?"

Return is_loose_end=false for anything else, including:
- smalltalk, greetings, thanks, jokes, reactions ("lol", "nice", "gm")
- statements of fact or opinion with no promise ("the build is green")
- questions that are rhetorical, vague, or already answered in the same message
- someone ELSE being asked to do something (only first-person commitments count as commitments)
- past-tense done work ("I sent the deck") — that is NOT an open commitment

Be conservative. If unsure, prefer is_loose_end=false with low confidence.

Respond with ONLY a JSON object, no prose, no markdown fences:
{
  "is_loose_end": boolean,
  "type": "commitment" | "unanswered_question" | null,
  "summary": string | null,      // short imperative, e.g. "send the Q3 deck" (<= 8 words)
  "due_hint": string | null,     // raw time phrase if present: "friday","tonight","by EOD","next week"; else null
  "confidence": number           // 0.0 - 1.0
}"""


def _coerce(raw: str) -> dict:
    """Pull a JSON object out of a model response, defensively."""
    text = raw.strip()
    # strip ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # grab the first {...} block if there's surrounding prose
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


_EMPTY = {
    "is_loose_end": False,
    "type": None,
    "summary": None,
    "due_hint": None,
    "confidence": 0.0,
}


def _normalize(data: dict) -> dict:
    """Clamp/validate model output into our strict shape."""
    is_le = bool(data.get("is_loose_end", False))
    le_type = data.get("type")
    if le_type not in ("commitment", "unanswered_question"):
        le_type = None
    if le_type is None:
        is_le = False
    try:
        conf = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    summary = data.get("summary")
    summary = summary.strip() if isinstance(summary, str) and summary.strip() else None
    due_hint = data.get("due_hint")
    due_hint = due_hint.strip() if isinstance(due_hint, str) and due_hint.strip() else None
    if not is_le:
        return {**_EMPTY}
    return {
        "is_loose_end": True,
        "type": le_type,
        "summary": summary,
        "due_hint": due_hint,
        "confidence": conf,
    }


ANSWER_PROMPT = """You are "Loose Ends", a Slack accountability agent, answering a question \
a user asked about their own commitments and open questions.

You are given two grounded sources:
- TRACKED LOOSE ENDS — items Loose Ends already detected and stored for this user. This is
  the authoritative record. Prefer it.
- WORKSPACE CONTEXT — raw Slack messages found via Real-Time Search. Use these to add detail,
  catch things not yet tracked, and cite sources. They may be irrelevant; ignore those.

Rules:
- Answer ONLY from the sources. Never invent a commitment, a date, or a person.
- Be concise: a one-line summary, then a short bullet per item. Slack mrkdwn.
- Slack mrkdwn is NOT markdown: use *bold* (single asterisks), and links as <url|text>.
- When a source has a permalink, cite it on that bullet as <permalink|source>.
- Refer to due dates in the human terms given (e.g. "overdue by 3h", "due Fri").
- If the sources contain nothing relevant, say so plainly in one sentence. Do not pad.
- No preamble, no sign-off, no headers. Just the answer."""


def answer_question(
    question: str,
    tracked: list[dict],
    context_messages: list[dict],
) -> str | None:
    """Answer a user's /looseends ask question, grounded in DB rows + RTS hits.

    Returns Slack mrkdwn, or None on failure (caller falls back to a plain list).
    """
    question = (question or "").strip()
    if not question:
        return None

    if tracked:
        tracked_txt = "\n".join(
            f"- [{t['type']}] {t['summary']} · status={t['status']} · {t['due_phrase']}"
            + (f" · <{t['permalink']}|source>" if t.get("permalink") else "")
            for t in tracked
        )
    else:
        tracked_txt = "(none tracked)"

    if context_messages:
        ctx_txt = "\n".join(
            f"- @{m.get('author_name') or m.get('author_user_id')} in #{m.get('channel_name')}: "
            f"{(m.get('content') or '')[:300]}"
            + (f" · <{m['permalink']}|source>" if m.get("permalink") else "")
            for m in context_messages
        )
    else:
        ctx_txt = "(no workspace context available)"

    user_content = (
        f"QUESTION: {question}\n\n"
        f"TRACKED LOOSE ENDS:\n{tracked_txt}\n\n"
        f"WORKSPACE CONTEXT:\n{ctx_txt}"
    )

    try:
        resp = _client.chat.completions.create(
            model=config.DGRID_MODEL,
            temperature=0.2,
            max_tokens=500,
            messages=[
                {"role": "system", "content": ANSWER_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        answer = (resp.choices[0].message.content or "").strip()
        return answer or None
    except Exception as e:  # noqa: BLE001 — /ask must never crash
        log.warning("answer_question failed: %s", e)
        return None


def extract_loose_end(text: str, context: str | None = None) -> dict:
    """Classify a single message. Never raises — returns the _EMPTY shape on error."""
    text = (text or "").strip()
    if not text:
        return {**_EMPTY}

    user_content = text if not context else f"Context: {context}\n\nMessage: {text}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    # Try up to twice: an empty/non-JSON reply from the gateway must not silently
    # drop a real loose end. The retry nudges harder for bare JSON.
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            resp = _client.chat.completions.create(
                model=config.DGRID_MODEL,
                temperature=0,
                max_tokens=200,
                messages=messages,
            )
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                raise ValueError("empty completion")
            return _normalize(_coerce(raw))
        except Exception as e:  # noqa: BLE001 — detection must never crash the app
            last_err = e
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": "Reply with ONLY the JSON object, nothing else.",
                    }
                )
    log.warning("extract_loose_end failed after retry: %s", last_err)
    return {**_EMPTY}
