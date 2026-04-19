"""Mock CrewAI framework for agent testing without requiring crewai package.

This module provides mock implementations for CrewAI Agent and related classes.
The mocks allow tests to run without the actual CrewAI package installed,
while still testing the integration between FinMatrix agents and the CrewAI adapter.

Usage:
    from tests.mocks import MockCrewAgent, MockCrewAI, create_mock_agent

    # Test with mocked CrewAI available
    MockCrewAI.set_available(True)
    agent = create_mock_agent(role="Analyst", goal="Analyze", backstory="You are...", llm_model="gpt-4")
    assert agent.role == "Analyst"

    # Test with CrewAI disabled (returns spec instead)
    MockCrewAI.set_available(False)
"""

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Mock Agent and Spec classes
# ---------------------------------------------------------------------------


@dataclass
class MockCrewAgent:
    """Mock CrewAI Agent for testing.

    Mimics the interface of crewai.Agent without requiring the package.
    Can be used to verify agent construction parameters and tool attachments.
    """

    role: str
    goal: str
    backstory: str
    llm_model: str
    verbose: bool = False
    tools: list = field(default_factory=list)

    def add_tool(self, tool: Any) -> None:
        """Add a tool to the agent (mimics CrewAI agent.add_tool)."""
        self.tools.append(tool)

    def __repr__(self) -> str:
        return f"MockCrewAgent(role={self.role!r}, goal={self.goal!r}, tools_count={len(self.tools)})"


@dataclass(frozen=True)
class MockCrewAgentSpec:
    """Fallback metadata for CrewAI agent when CrewAI is not available.

    Matches the structure of app.services.agents.crewai_adapter.CrewAgentSpec.
    """

    role: str
    goal: str
    backstory: str
    llm_model: str


# ---------------------------------------------------------------------------
# Mock CrewAI package state
# ---------------------------------------------------------------------------


class MockCrewAI:
    """Mock CrewAI package availability state.

    Controls whether create_agent_or_spec returns a MockCrewAgent or
    MockCrewAgentSpec, simulating the real behavior where CrewAI may or
    may not be installed.
    """

    _available: bool = False
    _agent_count: int = 0
    _call_history: list[dict[str, Any]] = []

    @classmethod
    def set_available(cls, available: bool) -> None:
        """Set whether CrewAI is considered available.

        Args:
            available: True if crewai package should be considered installed
        """
        cls._available = available

    @classmethod
    def is_available(cls) -> bool:
        """Check if CrewAI is currently considered available."""
        return cls._available

    @classmethod
    def reset(cls) -> None:
        """Reset all mock state (call history and agent count)."""
        cls._agent_count = 0
        cls._call_history = []

    @classmethod
    def get_call_history(cls) -> list[dict[str, Any]]:
        """Get the history of agent creation calls."""
        return cls._call_history.copy()


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def create_mock_agent(
    role: str,
    goal: str,
    backstory: str,
    llm_model: str,
    *,
    verbose: bool = False,
) -> MockCrewAgent:
    """Factory for creating mock CrewAI agents.

    Args:
        role: Agent role name
        goal: Agent goal description
        backstory: Agent backstory
        llm_model: LLM model identifier
        verbose: Whether verbose output is enabled

    Returns:
        MockCrewAgent instance
    """
    MockCrewAI._agent_count += 1
    MockCrewAI._call_history.append(
        {
            "type": "agent",
            "role": role,
            "goal": goal,
            "backstory": backstory,
            "llm_model": llm_model,
            "verbose": verbose,
        }
    )
    return MockCrewAgent(
        role=role,
        goal=goal,
        backstory=backstory,
        llm_model=llm_model,
        verbose=verbose,
    )


def create_mock_spec(
    role: str,
    goal: str,
    backstory: str,
    llm_model: str,
) -> MockCrewAgentSpec:
    """Factory for creating mock CrewAgentSpec.

    Used when CrewAI is not available and the adapter returns spec metadata.

    Args:
        role: Agent role name
        goal: Agent goal description
        backstory: Agent backstory
        llm_model: LLM model identifier

    Returns:
        MockCrewAgentSpec instance
    """
    MockCrewAI._call_history.append(
        {
            "type": "spec",
            "role": role,
            "goal": goal,
            "backstory": backstory,
            "llm_model": llm_model,
        }
    )
    return MockCrewAgentSpec(
        role=role,
        goal=goal,
        backstory=backstory,
        llm_model=llm_model,
    )


# ---------------------------------------------------------------------------
# Mock CrewAI Adapter replacement
# ---------------------------------------------------------------------------


def mock_create_agent_or_spec(
    *,
    role: str,
    goal: str,
    backstory: str,
    llm_model: str,
    verbose: bool = False,
) -> MockCrewAgent | MockCrewAgentSpec:
    """Mock version of crewai_adapter.create_agent_or_spec.

    This function simulates the real adapter behavior:
    - Returns MockCrewAgent when CrewAI is available
    - Returns MockCrewAgentSpec when CrewAI is not available

    Args:
        role: Agent role name
        goal: Agent goal description
        backstory: Agent backstory
        llm_model: LLM model identifier
        verbose: Whether verbose output is enabled

    Returns:
        MockCrewAgent if CrewAI available, MockCrewAgentSpec otherwise
    """
    if MockCrewAI.is_available():
        return create_mock_agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm_model=llm_model,
            verbose=verbose,
        )
    return create_mock_spec(
        role=role,
        goal=goal,
        backstory=backstory,
        llm_model=llm_model,
    )


# ---------------------------------------------------------------------------
# Mock Tool class
# ---------------------------------------------------------------------------


class MockCrewTool:
    """Mock CrewAI Tool for testing.

    Mimics crewai.Tool without requiring the package.
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Any = None,
    ):
        self.name = name
        self.description = description
        self.func = func

    def __repr__(self) -> str:
        return f"MockCrewTool(name={self.name!r})"


def create_mock_tool(
    name: str,
    description: str,
    func: Any = None,
) -> MockCrewTool:
    """Factory for creating mock CrewAI tools.

    Args:
        name: Tool name
        description: Tool description
        func: Optional function to attach to the tool

    Returns:
        MockCrewTool instance
    """
    return MockCrewTool(name=name, description=description, func=func)
