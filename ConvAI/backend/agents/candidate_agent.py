"""
Candidate Agent - simulates a job candidate responding to interviewer questions.
"""

import hashlib
import os
from typing import Optional

import httpx
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    http_client=httpx.Client(trust_env=False),
)

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")
MAX_COMPLETION_TOKENS = int(os.getenv("CHAT_MAX_COMPLETION_TOKENS", "220"))


def _choose_session_mode(session_seed: str) -> str:
    """Pick one mode per interview session and keep it fixed across all rounds."""
    seed = session_seed.strip() or "default-session"
    bucket = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % 100
    return "best" if bucket < 50 else "rubbish"


def _sanitize_answer_output(text: str) -> str:
    cleaned = " ".join((text or "").strip().split())
    prefixes = ("Candidate:", "AI:", "Assistant:", "Answer:", "A:")
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
            break
    return cleaned


def generate_candidate_answer(
    *,
    role_context: str,
    candidate_profile: str,
    interviewer_question: str,
    conversation_history: Optional[list[dict]] = None,
    current_round: int = 1,
    session_seed: Optional[str] = None,
) -> str:
    mode = _choose_session_mode(session_seed or "")
    history_tail = conversation_history[-3:] if conversation_history else []
    history_text = "\n\n".join(
        f"Round {i + 1} Interviewer Question: {turn.get('question', '')}\n"
        f"Round {i + 1} Candidate Answer: {turn.get('answer', '')}"
        for i, turn in enumerate(history_tail)
    )

    system_prompt = """You are role-playing as a real Indian candidate in a live interview.

Speak like natural spoken English, not written English.

Answer style:
- Use very simple words and short sentences.
- Sound like a person thinking while speaking.
- Use contractions: "I am" -> "I'm", "I have" -> "I've", etc.
- Add light fillers sometimes: "umm", "so", "actually", "basically", "you know".
- Do not overuse fillers. 1 or 2 in a reply is enough.
- Slightly imperfect grammar is okay if it feels natural.
- Small self-corrections are okay, like "I mean" or "sorry, let me rephrase".
- No labels, no bullet points, no polished essay structure.

Behavior:
- Stay role-relevant using role context and candidate profile.
- If asked "step by step", answer in a natural flow: "first..., then..., after that..., finally...".
- If unsure, say it honestly and politely.
- Give practical examples when useful.
- Avoid buzzwords, corporate jargon, and textbook tone.

Length and flow:
- Keep it concise, usually 3 to 6 sentences.
- Keep each sentence moderately short.
- End cleanly; do not leave the final sentence incomplete.

Session consistency:
- The interview session mode is fixed for all rounds and is either:
    - best: clear, relevant, practical answers with natural spoken flow
    - rubbish: weaker, vague, or partly off-target answers, but still human and conversational
- Never mention these instructions or the response mode explicitly.
"""

    user_prompt = (
        f"Role context:\n{role_context}\n\n"
        f"Candidate profile:\n{candidate_profile}\n\n"
        f"Current round: {current_round}\n"
        f"Response mode: {mode}\n\n"
        f"Recent conversation:\n{history_text or 'N/A'}\n\n"
        f"Interviewer question:\n{interviewer_question}\n\n"
        "Return only the candidate's direct spoken answer. Keep it human, simple, and concise."
    )

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    answer = _sanitize_answer_output(response.choices[0].message.content or "")
    if answer:
        return answer
    raise RuntimeError("Candidate model returned an empty answer")
