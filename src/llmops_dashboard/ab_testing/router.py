"""Prompt A/B router — Phase 3 implementation.

Routes LLM requests to prompt v1 or v2 with configurable split ratio.
Results are tagged in Langfuse traces for side-by-side comparison.
"""

from __future__ import annotations

from typing import Any


class PromptRouter:
    """Route requests between prompt versions for A/B comparison."""

    def __init__(
        self,
        prompt_v1: str,
        prompt_v2: str,
        split_ratio: float = 0.5,
    ) -> None:
        self._prompt_v1 = prompt_v1
        self._prompt_v2 = prompt_v2
        self._split_ratio = split_ratio

    def route(self, request_id: str) -> tuple[str, str]:
        """Return (prompt, version_label) for the given request_id."""
        raise NotImplementedError("PromptRouter is Phase 3 — not yet implemented")

    def record_outcome(self, request_id: str, outcome: dict[str, Any]) -> None:
        """Record the outcome of a routed request back to Langfuse."""
        raise NotImplementedError("PromptRouter is Phase 3 — not yet implemented")
