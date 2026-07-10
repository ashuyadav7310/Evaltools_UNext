#backend/agents/evaluator.py
"""
Evaluation Agent – scores candidate responses against rubrics using OpenAI chat.
"""

import json
import os
import httpx
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    http_client=httpx.Client(trust_env=False),
)

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")


def _normalize_score_breakdown(parsed: dict, rubrics: list[dict]) -> tuple[list[dict], float, float]:
    score_breakdown = parsed.get("scoreBreakdown") or [
        {"criterion": r["name"], "score": 5, "maxScore": 10, "justification": "N/A"}
        for r in rubrics
    ]
    total_score = sum(item.get("score", 0) for item in score_breakdown)
    max_score = sum(item.get("maxScore", 10) for item in score_breakdown)
    return score_breakdown, total_score, max_score


def evaluate_candidate(
    *,
    test_title: str,
    test_context: str,
    rubrics: list[dict],
    responses: list[dict],  # [{round, question, transcript}]
    candidate_name: str,
    time_spent_seconds: float | None = None,
) -> dict:
    rubric_list = "\n".join(
        f"- {r['name']}" + (f": {r['description']}" if r.get("description") else "")
        for r in rubrics
    )

    transcript = "\n\n".join(
        f"Round {r['round']}:\nInterviewer: {r['question']}\nCandidate: {r['transcript']}"
        for r in responses
    )

    system_prompt = """You are an expert interview evaluator. Evaluate the candidate's performance based on the rubrics provided.

Return a JSON object with this exact structure:
{
  "scoreBreakdown": [
    {
      "criterion": "rubric name",
      "score": 0-10,
      "maxScore": 10,
      "justification": "brief explanation"
    }
  ],
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "improvements": ["suggestion 1", "suggestion 2"],
  "overallJustification": "overall summary of performance"
}

Scoring: 1-10 for each criterion (1=very poor, 5=average, 10=excellent)
Be fair, objective, and specific in justifications.

Additional rules:
- Do NOT give generic feedback.
- Every scoreBreakdown justification must reference the candidate's actual response content.
- Mention the round number and cite a short quote or a close paraphrase of what the candidate said.
- Strengths must state what the candidate said that was effective and why it helped.
- Weaknesses must state what the candidate said that was weak, vague, missing, contradictory, or incorrect and why it hurt the evaluation.
- Improvements must be actionable and tied to a specific response or missed opportunity from the interview.
- overallJustification must summarize the candidate's performance using concrete evidence from multiple rounds.
- If the candidate gave contradictory or shallow answers, call that out explicitly.
- Avoid unsupported praise such as 'good communication' unless you explain which response demonstrated it."""

    user_prompt = f"""Interview Title: {test_title}
Scenario Context: {test_context}
Candidate Name: {candidate_name}

Evaluation Rubrics:
{rubric_list}

Interview Transcript:
{transcript}

Please evaluate the candidate and return a JSON response.

Important: your feedback must explicitly reference what the candidate actually said in the transcript, not just general observations."""

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        max_completion_tokens=2000,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    parsed = json.loads(raw)

    score_breakdown, total_score, max_score = _normalize_score_breakdown(parsed, rubrics)

    return {
        "totalScore": total_score,
        "maxScore": max_score,
        "scoreBreakdown": score_breakdown,
        "strengths": parsed.get("strengths", []),
        "weaknesses": parsed.get("weaknesses", []),
        "improvements": parsed.get("improvements", []),
        "overallJustification": parsed.get("overallJustification", ""),
        "timeSpentSeconds": time_spent_seconds,
    }


def evaluate_interviewer(
    *,
    test_title: str,
    test_context: str,
    rubrics: list[dict],
    responses: list[dict],  # [{round, question, transcript}] question=human interviewer, transcript=AI candidate answer
    interviewer_name: str,
    time_spent_seconds: float | None = None,
) -> dict:
    rubric_list = "\n".join(
        f"- {r['name']}" + (f": {r['description']}" if r.get("description") else "")
        for r in rubrics
    )

    transcript = "\n\n".join(
        f"Round {r['round']}:\nInterviewer: {r['question']}\nCandidate: {r['transcript']}"
        for r in responses
    )

    system_prompt = """You are an expert interviewer coach evaluating interview quality.

Evaluate the interviewer's performance from the transcript and return a JSON object with this exact structure:
{
  "scoreBreakdown": [
    {
      "criterion": "rubric name",
      "score": 0-10,
      "maxScore": 10,
      "justification": "brief explanation"
    }
  ],
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "improvements": ["suggestion 1", "suggestion 2"],
    "decision": "Hire | No Hire",
  "overallJustification": "summary with concrete evidence"
}

Scoring rules:
- Score each criterion 0 to 10 (0=very poor, 10=excellent).
- Use transcript evidence and mention round numbers.
- Focus on interviewer quality: structure, sequencing, probing, opening and closure quality.
- Detect patterns when present: generic questions, missing follow-ups, poor sequencing, weak closure.

Decision rules:
- If interviewer fails to assess properly, choose "No Hire".
- If interview is strong and well-structured, choose "Hire".
- If mixed quality and partial assessment, choose "No Hire".

Output must be strict JSON only."""

    user_prompt = f"""Interview Title: {test_title}
Interview Context: {test_context}
Interviewer Name: {interviewer_name}

Evaluation Rubrics:
{rubric_list}

Interview Transcript:
{transcript}

Return JSON only. Ensure each justification references what the interviewer asked in specific rounds."""

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        max_completion_tokens=2200,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    parsed = json.loads(raw)

    score_breakdown, total_score, max_score = _normalize_score_breakdown(parsed, rubrics)
    raw_decision = str(parsed.get("decision", "")).strip().lower()
    decision = "Hire" if raw_decision == "hire" else "No Hire"
    overall = (parsed.get("overallJustification") or "").strip()
    overall_with_decision = f"Decision: {decision}. {overall}".strip()

    return {
        "totalScore": total_score,
        "maxScore": max_score,
        "scoreBreakdown": score_breakdown,
        "strengths": parsed.get("strengths", []),
        "weaknesses": parsed.get("weaknesses", []),
        "improvements": parsed.get("improvements", []),
        "overallJustification": overall_with_decision,
        "timeSpentSeconds": time_spent_seconds,
    }
