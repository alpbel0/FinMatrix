"""YAML prompt loader for LLM agents.

This module provides utilities for loading and parsing YAML prompt files
for different agents. YAML format allows storing model parameters
alongside prompt templates.

Key functions:
- load_prompt: Load a YAML prompt file
- PromptConfig: Parsed prompt configuration
"""

from pathlib import Path
from typing import Any

import yaml

from app.services.utils.logging import logger

# ============================================================================
# Constants
# ============================================================================

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


# ============================================================================
# Models
# ============================================================================


class PromptConfig:
    """Parsed prompt configuration from YAML file.

    Attributes:
        model: OpenRouter model identifier
        temperature: Temperature for generation
        max_tokens: Maximum tokens to generate
        system_prompt: System message content
        user_prompt_template: User message template with placeholders
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: str = "",
        user_prompt_template: str = "",
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        # Store any additional fields
        self.extra = kwargs

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptConfig":
        """Create PromptConfig from dictionary.

        Args:
            data: Dictionary from YAML parsing

        Returns:
            PromptConfig instance
        """
        return cls(
            model=data.get("model", ""),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 1024),
            system_prompt=data.get("system_prompt", ""),
            user_prompt_template=data.get("user_prompt_template", ""),
        )

    def format_user_prompt(self, **kwargs: Any) -> str:
        """Format user prompt template with provided values.

        Args:
            **kwargs: Values to substitute in template

        Returns:
            Formatted user prompt
        """
        if not self.user_prompt_template:
            return ""
        try:
            return self.user_prompt_template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template parameter: {e}")
            return self.user_prompt_template


# ============================================================================
# Core Functions
# ============================================================================


def load_prompt(prompt_name: str) -> PromptConfig:
    """Load a YAML prompt file by name.

    Looks for {prompt_name}.yaml in the prompts directory.

    Args:
        prompt_name: Name of the prompt file (without .yaml extension)

    Returns:
        PromptConfig instance

    Raises:
        FileNotFoundError: If prompt file doesn't exist
        ValueError: If prompt file is invalid
    """
    prompt_path = PROMPTS_DIR / f"{prompt_name}.yaml"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid prompt file format: {prompt_path}")

        logger.debug(f"Loaded prompt: {prompt_name}")
        return PromptConfig.from_dict(data)

    except yaml.YAMLError as e:
        raise ValueError(f"YAML parsing error in {prompt_path}: {e}")


def get_openrouter_chat_url() -> str:
    """Get OpenRouter chat completions API URL.

    Returns:
        OpenRouter API URL for chat completions
    """
    return "https://openrouter.ai/api/v1/chat/completions"