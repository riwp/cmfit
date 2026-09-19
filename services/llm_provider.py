"""Provider-neutral LLM interface for CMFit chat agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[Any]]


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    tool_calls: list[dict[str, Any]]


class LLMProvider(ABC):
    """Base contract for any LLM provider used by CMFit."""

    name = "base"

    @abstractmethod
    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        instructions: str,
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
    ) -> ChatResult:
        raise NotImplementedError
