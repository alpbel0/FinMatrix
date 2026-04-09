"""Small adapter around CrewAI agent construction.

Core FinMatrix services remain framework-independent. This adapter keeps CrewAI
at the orchestration boundary and lets unit tests run even when CrewAI is not
installed in the local virtual environment.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CrewAgentSpec:
    """Fallback metadata for a CrewAI agent role."""

    role: str
    goal: str
    backstory: str
    llm_model: str


def is_crewai_available() -> bool:
    """Return True if the CrewAI package can be imported."""
    try:
        import crewai  # noqa: F401
    except ImportError:
        return False
    return True


def create_agent_or_spec(
    *,
    role: str,
    goal: str,
    backstory: str,
    llm_model: str,
    verbose: bool = False,
) -> Any:
    """Create a CrewAI Agent when available, otherwise return role metadata."""
    spec = CrewAgentSpec(
        role=role,
        goal=goal,
        backstory=backstory,
        llm_model=llm_model,
    )

    try:
        from crewai import Agent
    except ImportError:
        return spec

    try:
        return Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm_model,
            verbose=verbose,
        )
    except Exception:
        # Agent construction can fail if an installed CrewAI/LiteLLM version
        # expects a provider-prefixed model string. Keep imports safe and let
        # the orchestrator decide the concrete runtime configuration later.
        return CrewAgentSpec(
            role=role,
            goal=goal,
            backstory=backstory,
            llm_model=llm_model,
        )
