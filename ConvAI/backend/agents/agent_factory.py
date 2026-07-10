"""
Agent Factory – routes interview requests to the appropriate agent based on category.

This module provides a single interface for generating interview questions,
delegating to specialized agents based on the interview category.
Supports:
  - Leadership: Scenario-based behavioral interview with format validation
  - Hiring Process: Standard HR interview with structured questions
  
To add new categories:
  1. Create a new agent file in the agents folder (e.g., technical_agent.py)
  2. Implement generate_next_question() function with the same signature
  3. Register it in the AGENT_REGISTRY below
"""

from typing import Optional
from agents.interviewer import generate_next_question as leadership_generate
from agents.hiring_agent import generate_next_question as hiring_generate
from agents.candidate_agent import generate_candidate_answer as candidate_generate


# Registry of available agents
# Add new agents here to make them discoverable
AGENT_REGISTRY = {
    "leadership": {
        "name": "Leadership & Behavioral",
        "description": "Scenario-based behavioral interview for assessing leadership, decision-making, and interpersonal skills",
        "generate_function": leadership_generate,
    },
    "hiring_process": {
        "name": "Hiring Process",
        "description": "Standard HR interview flow covering background, experience, skills, and career aspirations",
        "generate_function": hiring_generate,
    },
    "interviewer_evaluation": {
        "name": "Interviewer Evaluation",
        "description": "Trainer asks questions, AI plays candidate, and system evaluates interviewer quality",
        "generate_function": leadership_generate,
        "candidate_function": candidate_generate,
    },
}


def get_available_categories() -> dict:
    """Return all available interview categories with metadata."""
    return {
        key: {"name": value["name"], "description": value["description"]}
        for key, value in AGENT_REGISTRY.items()
    }


def get_agent_by_category(category: str):
    """
    Get the agent generate function for a given category.
    
    Args:
        category: The interview category (lowercase, underscore-separated)
        
    Returns:
        The generate_next_question function for that category
        
    Raises:
        ValueError: If category is not found in registry
    """
    normalized_category = category.lower().replace(" ", "_")
    
    if normalized_category not in AGENT_REGISTRY:
        available = ", ".join(AGENT_REGISTRY.keys())
        raise ValueError(
            f"Unknown interview category: '{category}'. "
            f"Available categories: {available}"
        )
    
    return AGENT_REGISTRY[normalized_category]["generate_function"]


def get_candidate_agent_by_category(category: str):
    """Get candidate-answer function for categories that support interviewer evaluation mode."""
    normalized_category = category.lower().replace(" ", "_")

    if normalized_category not in AGENT_REGISTRY:
        available = ", ".join(AGENT_REGISTRY.keys())
        raise ValueError(
            f"Unknown interview category: '{category}'. "
            f"Available categories: {available}"
        )

    return AGENT_REGISTRY[normalized_category].get("candidate_function")


def generate_next_question(
    *,
    category: str,
    test_title: str,
    test_context: str,
    rubrics: list[dict],
    total_rounds: int,
    current_round: int,
    conversation_history: list[dict],
    candidate_response: Optional[str],
    candidate_name: Optional[str] = None,
) -> str:
    """
    Generate the next interview question using the appropriate agent.
    
    Args:
        category: Interview category (e.g., "leadership", "hiring_process")
        test_title: Title of the interview/test
        test_context: Scenario context or job description
        rubrics: Evaluation criteria
        total_rounds: Total number of interview rounds
        current_round: Current round number (1-indexed)
        conversation_history: List of previous questions and answers
        candidate_response: The candidate's most recent response
        candidate_name: Optional candidate name for personalization
        
    Returns:
        The next interview question as a string
        
    Raises:
        ValueError: If category is not recognized
        Exception: Any errors from the underlying agent
    """
    agent_function = get_agent_by_category(category)
    
    # Call the agent with all parameters
    # Note: Some agents may ignore parameters they don't use
    return agent_function(
        test_title=test_title,
        test_context=test_context,
        rubrics=rubrics,
        total_rounds=total_rounds,
        current_round=current_round,
        conversation_history=conversation_history,
        candidate_response=candidate_response,
        candidate_name=candidate_name,
    )


def generate_candidate_answer(
    *,
    category: str,
    role_context: str,
    candidate_profile: str,
    interviewer_question: str,
    conversation_history: list[dict],
    current_round: int,
    session_seed: Optional[str] = None,
) -> str:
    """Generate candidate answer for interviewer-evaluation categories."""
    candidate_function = get_candidate_agent_by_category(category)
    if candidate_function is None:
        raise ValueError(f"Category '{category}' does not support candidate-answer mode")

    return candidate_function(
        role_context=role_context,
        candidate_profile=candidate_profile,
        interviewer_question=interviewer_question,
        conversation_history=conversation_history,
        current_round=current_round,
        session_seed=session_seed,
    )
