# backend/services/ai_evaluation.py
from urllib import response
import httpx
from openai import OpenAI
from typing import Dict, Tuple, Optional
import json
from backend.config import get_settings

settings = get_settings()
client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
    http_client=httpx.Client(trust_env=False),
)


def count_fillers(transcript: str) -> dict:
    """Count filler words in transcript"""
    t = transcript.lower()

    fillers = {
        "um":        t.count(" um ") + t.count(" um,") + t.count(" um."),
        "uh":        t.count(" uh ") + t.count(" uh,") + t.count(" uh."),
        "ah":        t.count(" ah ") + t.count(" ah,") + t.count(" ah."),
        "like":      t.count(" like ") + t.count(", like"),
        "you know":  t.count("you know"),
        "so":        t.count(" so ") + t.count("so,"),
        "actually":  t.count(" actually "),
        "basically": t.count(" basically "),
        "kind of":   t.count("kind of"),
        "sort of":   t.count("sort of"),
    }

    total = sum(fillers.values())
    word_count = len(transcript.strip().split())
    fillers_per_100_words = round((total / word_count) * 100, 1) if word_count > 0 else 0

    return {
        "total": total,
        "breakdown": {k: v for k, v in fillers.items() if v > 0},
        "fillers_per_100_words": fillers_per_100_words
    }


def validate_transcript_quality(transcript: str) -> Tuple[bool, str]:
    """
    Validate if transcript has sufficient content for evaluation
    Returns: (is_valid, error_message)
    """
    transcript = transcript.strip()

    if not transcript:
        return False, "Transcript is empty. No speech was detected in the audio."

    if len(transcript) < 10:
        return False, "Response too short to evaluate. Please speak more clearly."

    word_count = len(transcript.split())
    if word_count < 5:
        return False, (
            f"Only {word_count} words detected. "
            "Please provide a more complete spoken response."
        )

    if transcript.lower() in ["um", "uh", "hmm", "...", "silence", "ah"]:
        return False, "No meaningful speech detected. Please speak clearly."

    return True, ""


def evaluate_communication(
    transcript: str,
    scenario: str,
    rubric: Dict[str, int],
    rubric_descriptions: Dict[str, str] = None,
    difficulty_level: str = "Medium",
    audio_metrics: Optional[dict] = None
) -> Tuple[Dict[str, float], float, str, str]:
    """
    AI-first evaluation with minimal hardcoded rules.
    Returns: (scores, total_percentage, strengths, improvements)
    """
    
    word_count = len(transcript.strip().split())
    
    # Only hard reject truly empty responses
    if len(transcript.strip()) < 10 or word_count < 3:
        scores = {skill: 0 for skill in rubric.keys()}
        return (
            scores, 0.0,
            "1. No response – No meaningful speech detected.",
            "1. Record again – Please speak clearly into the microphone."
        )
    
    # Build rubric with descriptions
    rubric_str = ""
    for skill, max_score in rubric.items():
        rubric_str += f"\n- **{skill}** (max {max_score} points)"
        if rubric_descriptions and skill in rubric_descriptions:
            rubric_str += f"\n  Guidelines: {rubric_descriptions[skill]}"
    
    # Audio context (factual data only, let AI interpret)
    audio_context = ""
    if audio_metrics and not audio_metrics.get("error"):
        audio_context = f"""
RECORDING QUALITY CHECK (use only to detect recording/silence issues):
- Duration: {audio_metrics['duration_seconds']:.1f} seconds
- Active speech time: {audio_metrics['speech_ratio_percent']:.1f}% ({audio_metrics['total_speech_seconds']:.1f}s speaking)
- Audio feedback: {audio_metrics['feedback']}

Use this only to detect silence, recording failure, or severe audio dropouts.
Do NOT reduce scores for pauses, speaking speed, confidence, or voice energy.
Primary scoring must be based on transcript content quality.
"""
    
    # Filler detection
    filler_info = count_fillers(transcript)
    filler_note = ""
    #if filler_info["total"] > 0:
    if filler_info["total"] >= 8:  # v2upgrades
        filler_note = f"\nFiller words detected: {filler_info['breakdown']} (total: {filler_info['total']})"
    
    # Difficulty guidelines (guidance, not rules)
    if difficulty_level.lower() == "easy":
        difficulty_note = "EASY level: Be encouraging. Accept basic attempts. 6-7 = good, 8+ = excellent."
    elif difficulty_level.lower() == "hard":
        difficulty_note = "HARD level: Expect excellence. Brief responses should score lower. 8+ = only for comprehensive answers."
    else:
        difficulty_note = "MEDIUM level: Balanced evaluation. Reward completeness and clarity."
    
    # Main prompt - let AI decide everything
    prompt = f"""You are ComCoach, a fair and content-focused corporate communication evaluation system.
    You are NOT a casual chatbot.
    You evaluate objectively using the rubric.
    You never overpraise.
    you should be balanced, realistic, and encouraging when deserved.
    You never give generic feedback.
    You never skip rubric categories.
    Evaluate ONLY the participant’s spoken communication skill.
    DO NOT give generic advice.
    DO NOT give audience-related suggestions.
    DO NOT give presentation tips.
    Focus only on wording, clarity, structure, tone, logic, and completeness.

    DIFFICULTY LEVEL: {difficulty_level.upper()}
    {difficulty_note}

    SCENARIO:
    {scenario}
    SCENARIO COVERAGE CHECK:
    Identify 3 key requirements of the scenario.
    Check if participant covered them.
    If missing, explain exactly what was missing.

    PARTICIPANT'S RESPONSE:
    "{transcript}"
    (Word count: {word_count}){filler_note}

    {audio_context}

    EVALUATION RUBRIC:
    {rubric_str}

    SCORING ANCHORS:
    For each skill:
    - 0–1 = missing, incorrect, or irrelevant
    - 2–3 = basic/partial coverage
    - 4–6 = adequate coverage with some gaps
    - 7–8 = strong, clear, and mostly complete
    - Max = excellent, comprehensive, and professional
    Use full range fairly.

    TRANSCRIPT ANALYSIS STEP:
    First list factual issues from the transcript such as:
    - grammar errors
    - repeated words
    - incomplete sentences
    - missing scenario points
    - logical gaps
    Only after listing these, assign scores.

    YOUR TASK:
    Evaluate each skill using EVIDENCE from the response.

    RULES:
    - Quote exact phrases from the participant when explaining scores.
    - If something is missing, say exactly what was missing from the scenario.
    - Do NOT say generic phrases like:
    "improve communication"
    "be more confident"
    "speak clearly"
    - Every improvement must say HOW to fix it.
    - Focus only on the participant’s monologue, not audience advice.

    SCORING PRINCIPLES:
    - Score each skill between 0 and its max points.
    - Brief answers should score lower unless scenario requires brevity.
    - Prioritize content relevance, completeness, and clarity over delivery style.\n    - Do not heavily penalize natural pauses or occasional filler words.\n    - Brief answers should score lower only when key scenario points are missing."
    - Use transcript as primary evidence.
    - Use audio data only to detect silence or recording failure.
    - Do NOT lower marks for pauses, fluency, voice energy, or engagement cues.
    
    SCORING DISCIPLINE:
    - Score every rubric skill numerically.
    - Base score only on transcript evidence.
    - Do not guess or exaggerate.
    - Use full scoring range. 
    - If response is weak → score 0–3.
    - If response is strong → score near max.
    - Do NOT default to middle scores.

    ANTI-GENERIC RULES:
    - Do NOT say “Good explanation”, “Good fluency”, “Nice example”.
    - Every feedback must reference an exact phrase from the transcript.
    - If no clear strength exists, say so.

    OUTPUT FORMAT - Return ONLY this JSON:
    {{
    "scores": {{
        "SkillName1": score_number,
        "SkillName2": score_number
    }},
    "score_justifications": {{
        "SkillName1": "Brief explanation of why this score was given",
        "SkillName2": "Brief explanation of why this score was given"
    }},
    "strengths": [
        "Strength title – Detailed positive observation",
        "Another strength – Explanation",
        "Third strength – Observation"
    ],
    "improvements": [
        "Issue title – What was weak and how to improve",
        "Another issue – Specific actionable feedback",
        "Third issue – Improvement strategy"
    ]
    }}

    SCORING PRINCIPLES:
    - Provide 2-4 strengths and 2-4 improvements
    - Each point must follow "Title – Explanation" format
    - Be specific and actionable

    Now evaluate the response:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    # "content": (
                    #     "You are a strict evaluator who only gives evidence-based feedback. "
                    #     "You never give generic advice. " 
                    #     "You give realistic scores based on actual performance. "
                    #     "You provide specific, actionable feedback with clear justifications."
                    # )
                    "content": (
                        "You are a fair evaluator who gives evidence-based feedback. "  # v2upgrades
                        "You never give generic advice."
                        "You give realistic and balanced scores based on actual performance. "  # v2upgrades
                        "Prioritize content quality over delivery imperfections like pauses. "  # v2upgrades
                        "You provide specific, actionable feedback with clear justifications."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            top_p=0.9,
            frequency_penalty=0.2,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        scores = result.get("scores", {})

         # Clamp scores to rubric max
        for skill in scores:
            if skill in rubric:
                scores[skill] = min(scores[skill], rubric[skill])

        score_justifications = result.get("score_justifications", {})
        strengths_list = result.get("strengths", [])
        improvements_list = result.get("improvements", [])
        
        # Ensure lists
        if isinstance(strengths_list, str):
            strengths_list = [strengths_list]
        if isinstance(improvements_list, str):
            improvements_list = [improvements_list]
        
        # Format with numbers
        strengths_str = "\n".join([f"{i+1}. {s}" for i, s in enumerate(strengths_list)])
        improvements_str = "\n".join([f"{i+1}. {s}" for i, s in enumerate(improvements_list)])
        
        # Add justifications to improvements for transparency
        #if score_justifications:
        #    improvements_str += "\n\n**Score Justifications:**"
        #    for skill, justification in score_justifications.items():
        #        score = scores.get(skill, 0)
        #        max_score = rubric.get(skill, 10)
        #        improvements_str += f"\n• {skill} ({score}/{max_score}): {justification}"
        
        if score_justifications:
            improvements_str += "\n\n**Skill Feedback:**"
            for skill, justification in score_justifications.items():
                improvements_str += f"\n {skill} : {justification}"

        # Calculate total
        total_score = sum(scores.values())
        max_possible = sum(rubric.values())
        total_percentage = (total_score / max_possible) * 100
        
        return scores, total_percentage, strengths_str, improvements_str
    
    except Exception as e:
        raise Exception(f"AI evaluation failed: {str(e)}")
