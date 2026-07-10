"""
Hiring Process Agent – generates standard HR interview questions for hiring process category.
"""

import os
import re
from typing import Optional
import httpx
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    http_client=httpx.Client(trust_env=False),
)

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")
MAX_HISTORY_TURNS = int(os.getenv("CHAT_HISTORY_TURNS", "5"))
MAX_COMPLETION_TOKENS = int(os.getenv("CHAT_MAX_COMPLETION_TOKENS", "150"))


def _sanitize_question_output(text: str) -> str:
    cleaned = text.strip().strip('"').strip("'")
    prefixes = (
        "Interviewer:",
        "AI:",
        "Assistant:",
        "Question:",
        "Q:",
    )

    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix):].strip()
                changed = True

    cleaned = " ".join(cleaned.split())
    return cleaned


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def _is_repetitive_with_history(question: str, history: list[dict]) -> bool:
    if not question:
        return True

    current_tokens = _tokenize(question)
    if not current_tokens:
        return True

    for turn in history:
        prev_question = str(turn.get("question") or "").strip()
        if not prev_question:
            continue
        previous_tokens = _tokenize(prev_question)
        if not previous_tokens:
            continue

        # Jaccard overlap to detect near-duplicate phrasing
        overlap = len(current_tokens & previous_tokens) / max(len(current_tokens | previous_tokens), 1)
        if overlap >= 0.70:
            return True

    return False


def _get_round_theme(current_round: int) -> str:
    """Get the focus theme for each round."""
    themes = {
        1: "Introduction and professional background",
        2: "Relevant experience and key achievements",
        3: "Technical and soft skills with proof",
        4: "Problem-solving approach and decision-making",
        5: "Team collaboration and communication style",
        6: "Motivation, company fit, and growth mindset",
        7: "Career vision and role-specific strengths",
    }
    return themes.get(current_round, "Overall fit and suitability for the role")


def _get_fixed_round_1_question(candidate_name: Optional[str]) -> str:
    """Return the fixed round 1 opening question."""
    if candidate_name:
        return f"Hello {candidate_name}, could you please introduce yourself and tell us about your professional background?"
    return "Could you please introduce yourself and tell us about your professional background?"


def _fallback_question(current_round: int, candidate_name: Optional[str]) -> str:
    """Fallback question if generation fails."""
    theme = _get_round_theme(current_round)
    if current_round == 1:
        return _get_fixed_round_1_question(candidate_name)
    return f"In the context of {theme.lower()}, can you walk me through a specific example from your experience?"


def generate_next_question(
    *,
    test_title: str,
    test_context: str,
    rubrics: list[dict],
    total_rounds: int,
    current_round: int,
    conversation_history: list[dict],  # [{question, answer?}]
    candidate_response: Optional[str],
    candidate_name: Optional[str] = None,
) -> str:
    """Generate the next hiring process question following a structured HR interview flow."""

    # Round 1: Always use the fixed opening question
    if current_round == 1:
        return _get_fixed_round_1_question(candidate_name)

    # Rounds 2+: Generate contextual follow-up questions
    recent_history = conversation_history[-MAX_HISTORY_TURNS:] if MAX_HISTORY_TURNS > 0 else conversation_history
    rubric_list = ", ".join(r.get("name", "") for r in rubrics[:4] if r.get("name"))

    history_text = "\n\n".join(
        f"Round {i + 1} Question: {turn['question']}"
        + (f"\nRound {i + 1} Response: {turn['answer']}" if turn.get("answer") else "")
        for i, turn in enumerate(recent_history)
    )

    round_theme = _get_round_theme(current_round)
    name_instruction = (
        f"The candidate's name is {candidate_name}. Use it naturally if appropriate."
        if candidate_name
        else ""
    )

    system_prompt = f"""You are a professional HR interviewer conducting an open-ended hiring interview.

Interview: {test_title}
Context: {test_context}
Evaluation criteria: {rubric_list or 'General role fit'}
Current turn: {current_round}

TURN FOCUS: {round_theme}

Your task: Generate one conversational HR interview question that:
1. Explores this round's theme in depth
2. Builds on previous answers (context provided below)
3. Is NOT a repetition of earlier questions
4. Is specific and actionable (not generic)
5. Is a single line with no prefixes, bullets, or labels
6. {name_instruction if name_instruction else "Do not force the candidate name into every question."}

Keep the tone professional but warm, like a real HR conversation."""

    messages = [{"role": "system", "content": system_prompt}]
    
    if history_text:
        messages.append({"role": "user", "content": f"Interview history so far:\n{history_text}"})

    if candidate_response:
        messages.append(
            {
                "role": "user",
                "content": (
                    f'Latest candidate response: "{candidate_response}"\n\n'
                    f"Now ask the next turn question, focusing on {round_theme.lower()}. "
                    "Make it a fresh angle, not a restatement of earlier topics."
                ),
            }
        )
    else:
        messages.append(
            {
                "role": "user",
                "content": f"Generate the next turn question focused on {round_theme.lower()}.",
            }
        )

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        messages=messages,
    )

    draft = _sanitize_question_output(response.choices[0].message.content or "")
    if draft and not _is_repetitive_with_history(draft, recent_history):
        return draft

    # Retry once with explicit freshness instruction
    messages.append(
        {
            "role": "user",
            "content": (
                f"The previous question was too similar to earlier ones: '{draft}'. "
                f"Generate a completely different angle for {round_theme.lower()}. Be specific and avoid generic phrasing."
            ),
        }
    )
    retry = client.chat.completions.create(
        model=CHAT_MODEL,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        messages=messages,
    )
    retry_draft = _sanitize_question_output(retry.choices[0].message.content or "")
    if retry_draft and not _is_repetitive_with_history(retry_draft, recent_history):
        return retry_draft

    return _fallback_question(current_round=current_round, candidate_name=candidate_name)
