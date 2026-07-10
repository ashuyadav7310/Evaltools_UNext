# src/rubric_keypoint_gen.py
"""
Generates rubric-aligned keypoints for content rubrics using LLM.
"""

from typing import List, Dict
import json
import os
from openai import OpenAI
import time
from src.logging_config import get_logger

log = get_logger("keypoint_gen")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def split_compound_keypoints(keypoints: list[str]) -> list[str]:
    """
    Split compound keypoints into atomic obligations.
    Example:
    'Identify failure points and mitigation actions'
    → ['Identify failure points', 'Describe mitigation actions']
    """

    refined = []

    for kp in keypoints:
        low = kp.lower()

        # common compound patterns
        if " and " in low:
            parts = kp.split(" and ")

            if len(parts) == 2:
                left, right = parts

                # normalize verbs
                left = left.strip()
                right = right.strip()

                # heuristic verb injection for second clause
                if not right.lower().startswith(
                    ("identify", "describe", "explain", "outline", "discuss")
                ):
                    right = "Describe " + right

                refined.append(left)
                refined.append(right)
            else:
                refined.append(kp)
        else:
            refined.append(kp)

    return refined


def generate_keypoints_for_rubric(
    assignment_text: str,
    rubric: Dict,
    max_keypoints: int = 6,
) -> List[str]:
    """
    Generate atomic keypoints from assignment + rubric.
    """

    rubric_name = rubric.get("name", "")
    rubric_desc = rubric.get("description", "")

    prompt = f"""
    You are generating semantic anchors for automated grading.

    Your task is NOT to restate rubric instructions.

    Instead:

    1. Internally imagine a strong, well-written student email
    that perfectly answers the assignment below.
    2. From that imagined answer, extract short content fragments
    that would realistically appear in the email text itself.

    These fragments will be used for semantic similarity scoring.

    STRICT RULES:
    - Do NOT use instructional phrases (e.g., "include", "mention", "use")
    - Do NOT restate rubric language
    - Do NOT describe what should be done
    - ONLY output phrases that could literally appear in the student's email

    Good example:
        "Final-year Computer Science student"
        "Application for Machine Learning Internship"
        "Completed a sentiment analysis project"
        "Would appreciate the opportunity to discuss"
        "Thank you for your time and consideration"

    Bad example:
        "Clear introduction"
        "Professional closing"
        "Mentions academic background"

    Return ONLY JSON:
    {{ "keypoints": ["...", "..."] }}

    Maximum keypoints: {max_keypoints}
    
    INPUT:

    Rubric Name:
    {rubric_name}

    Rubric Description:
    {rubric_desc}

    Assignment Context:
    {assignment_text[:3500]}

    Return ONLY valid JSON:
    {{ "keypoints": ["...", "..."] }}
    """ 


    last_error = None

    for attempt in range(2):
        try:
            res = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You generate grading keypoints strictly in JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,
                top_p=0.8,
                max_tokens=200
            )

            raw = res.choices[0].message.content.strip()

            # JSON PARSE (ROBUST)
            try:
                data = json.loads(raw)
            except Exception:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                data = json.loads(raw[start:end])

            keypoints = data.get("keypoints", [])
            keypoints = [
                kp.strip()
                for kp in keypoints
                if isinstance(kp, str) and kp.strip()
            ]

            atomic_keypoints = split_compound_keypoints(keypoints)

            log.info(
                "Generated {} keypoints ({} atomic) for rubric {}",
                len(keypoints),
                len(atomic_keypoints),
                rubric_name
            )

            return atomic_keypoints[:max_keypoints]

        except Exception as e:
            last_error = e
            log.warning(
                "Keypoint gen attempt {} failed for rubric {} → {}",
                attempt + 1,
                rubric_name,
                str(e)
            )
            time.sleep(2)

    log.error(
        "Keypoint generation permanently failed for rubric {} → {}",
        rubric_name,
        str(last_error)
    )
    return []
