from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SpanRecord(BaseModel):
    """Canonical trace record — all fields required unless noted.

    Evolution policy: only add Optional fields with defaults. Never delete or retype.
    See docs/schema_versioning.md.
    """

    trace_id: str
    span_id: str
    project: str
    component: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_usd: float
    tags: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
