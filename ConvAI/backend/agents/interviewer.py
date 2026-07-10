#backend/agents/interviewer.py
"""
Conversational Agent – generates the next conversation prompt using OpenAI chat.
"""

import os
from typing import Optional
import httpx
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL") or None,
    http_client=httpx.Client(trust_env=False),
)

#CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o")
# new lower model
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o") #reduce time
MAX_HISTORY_TURNS = int(os.getenv("CHAT_HISTORY_TURNS", "5")) #reduce time
MAX_COMPLETION_TOKENS = int(os.getenv("CHAT_MAX_COMPLETION_TOKENS", "220")) #reduce time


def _sanitize_question_output(text: str) -> str:
    cleaned = text.strip()
    # Only remove leading/trailing quotes if they wrap the entire response
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    
    # Remove prefixes only if they appear at the very start
    prefixes = (
        "Interviewer:",
        "AI:",
        "Assistant:",
        "Question:",
        "Q:",
    )
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
            break
    
    return cleaned


def _extract_approach_signals(text: Optional[str]) -> list[str]:
    if not text:
        return []

    lowered = text.lower()
    signal_map = [
        ("structured plan", ["step", "plan", "first", "second", "third", "framework"]),
        ("empathy", ["empathy", "understand", "listen", "acknowledge", "feel"]),
        ("ownership", ["own", "ownership", "responsibility", "accountable", "accountability"]),
        ("conflict handling", ["conflict", "resolve", "de-escalate", "deescalate", "mediate"]),
        ("escalation handling", ["escalate", "manager", "lead", "escalation"]),
        ("collaboration", ["collaborate", "align", "together", "stakeholder"]),
        ("follow-up", ["follow up", "follow-up", "check in", "review"]),
    ]

    detected: list[str] = []
    for signal, keywords in signal_map:
        if any(keyword in lowered for keyword in keywords):
            detected.append(signal)

    return detected

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
    recent_history = conversation_history[-MAX_HISTORY_TURNS:] if MAX_HISTORY_TURNS > 0 else conversation_history #(reduce time)
    latest_answer = candidate_response or (recent_history[-1].get("answer") if recent_history else None)
    approach_signals = _extract_approach_signals(latest_answer)

    rubric_list = ", ".join(r['name'] for r in rubrics[:3])

    history_text = "\n\n".join(
        f"Round {i + 1} Question: {turn['question']}"
        + (f"\nRound {i + 1} Response: {turn['answer']}" if turn.get("answer") else "")
        #for i, turn in enumerate(conversation_history)
        for i, turn in enumerate(recent_history) #reduce time
    )

    system_prompt = f"""Conduct a structured scenario-based interview as an open-ended conversation. Current turn: {current_round}.

Title: {test_title}
Scenario: {test_context}
Rubrics: {rubric_list}

CORE DIRECTIVES:
1. Ask ONE focused scenario-specific question per round
2. Round 1: Introduce yourself and your role in the scenario, then ask an open-ended question to start the conversation
3. Later turns: Create adaptive scenarios that reflect how the person responds to the situation—vary their tone, willingness, resistance, or clarity
4. Progress through scenario steps in order; follow branching logic if present
5. Cross-question vague/incomplete/inconsistent answers—demand scenario-specific evidence
6. Challenge ownership, accountability, conflict handling, escalation capability
7. No labels/prefixes, no multiple questions, no explanation—ask naturally

DIALOGUE FORMAT (STRICT):
- Conversational, human, scenario-grounded wording (never robotic/generic)
- Start with the person's name and a brief action verb (responds, says, acknowledges, leaves, becomes, suggests, etc.)
- Include a realistic direct quote capturing their attitude/position/resistance/commitment
- End with a sharp objective-driven question starting with "How will you respond to..."
- Build on latest answer; use approach signals: {', '.join(approach_signals) if approach_signals else 'none'}

ADAPTIVE SCENARIO EXAMPLES (NOT TO BE REUSED):
1. "Amit responds, 'If this keeps slipping, we'll need to have a tougher conversation, but for now, let's do regular check-ins and support you wherever you are stuck.' How will you respond to ensure accountability while making it clear that further delays will trigger significant consequences?"
2. "Amit acknowledges the need for alignment but says, 'I want us as a team to focus less on explaining missteps and more on owning them early so it doesn't start affecting others.' How will you respond to clearly outline expectations, consequences, and follow-up while still signaling support?"
3. "Amit says, 'If we can't meet the benchmarks, let's reset them now, but once we agree, I expect us to stick to it.' How will you respond to address the behavior pattern influencing team morale without making it personal?"
4. "Amit leaves the conversation unclear about expectations and says, 'I appreciate you wanting to be supportive, but I still don't see how I can meet those deadlines.' How will you respond to reset expectations clearly under pressure?"

GENERATING CONTEXT-APPROPRIATE SCENARIOS:
- Vary Amit's response type based on round and candidate's answer:
  * Early rounds: Receptive, exploratory, open-ended
  * Mid rounds: More resistant, setting boundaries, testing limits
  * Later rounds: Attempting resets, frustration, unclear on expectations
  * Pattern-based: If candidate avoids accountability, show Amit avoiding too
  * If candidate shows support, show Amit acknowledging it but pushing back
- Each scenario should feel realistic and contextual to interview progression

MANDATORY OUTPUT TEMPLATE (ALWAYS):
[Name] [action verb], "[direct quote capturing their position/tone]." How will you respond to [clear objective]?

HARD OUTPUT RULES:
- Output exactly ONE question in a single continuous line
- Must include BOTH parts: (1) realistic direct quote, (2) "How will you respond to ...?"
- Do not output bullet points, role labels, explanations, or multiple questions
- Avoid generic stems like "What would you do?" unless tied to a clear scenario-specific objective
- Never repeat exact scenarios or quotes from previous rounds
- Keep the quote realistic and concise (1-2 sentences in quotes)

BRANCHING & PROGRESSION:
- If scenario specifies conditions ("If learner...", "Challenge 2A/2B"), follow strictly
- Choose branch matching latest response; default to accountability/clarity if ambiguous
- Stay consistent in branch until task complete
- Prioritize skills: accountability > communication > conflict > consequences
- Deepen with trade-offs, stakeholder perspectives, follow-up actions (stay scenario-focused)
"""

    messages = [{"role": "system", "content": system_prompt}]

    if history_text:
        messages.append({"role": "user", "content": f"Previous conversation:\n{history_text}"})

    if candidate_response:
        messages.append({
            "role": "user",
            "content": (
                f'The candidate just responded: "{candidate_response}"\n\n'
                f"Generate an adaptive scenario question for the next turn. "
                f"Based on the candidate's answer, create a realistic next scenario that Amit might present. "
                f"This should reflect how Amit would naturally respond to what the candidate said. "
                f"The scenario must:\n"
                f"1. Use a direct attributable quote (what Amit says/does/acknowledges/leaves unclear)\n"
                f"2. Be contexually different from previous rounds - show progression or new complexity\n"
                f"3. Probe, challenge, or deepen based on the candidate's most recent answer\n"
                f"4. Follow the exact format: [Name] [action], \"[quote].\" How will you respond to [objective]?\n"
                f"Return exactly one line. Do not add any explanation, bullet points, or prefixes."
            ),
        })
    else:
        messages.append({
            "role": "user",
            "content": (
                f"Generate the opening scenario question for this conversation. "
                f"Start by introducing yourself and your role, then present Amit's initial response/reaction. "
                f"Format: [Name] [action], \"[quote].\" How will you respond to [objective]? "
                f"Return exactly one line. Do not add explanation or prefixes."
            ),
        })

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        # max_completion_tokens=200,
        max_completion_tokens=MAX_COMPLETION_TOKENS, #reduce time       
        messages=messages,
    )

    if response.choices[0].message.content:
        return _sanitize_question_output(response.choices[0].message.content)
    return "Please tell me about yourself."
