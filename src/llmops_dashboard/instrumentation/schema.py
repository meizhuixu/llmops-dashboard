from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class SpanRecord(BaseModel):
    """Canonical trace record — all fields required unless noted.

    Evolution policy: only add Optional fields with defaults. Never delete or retype.
    See docs/schema_versioning.md.

    Cost fields (three valid patterns):
      1. Omit all cost fields → Langfuse auto-computes from its Model Pricing table.
      2. Set input_cost_usd + output_cost_usd → cost_usd is auto-summed; Langfuse
         receives split cost (input_cost / output_cost) for detailed reporting.
      3. Set cost_usd only (legacy) → Langfuse receives total_cost only.
         Prefer set_cost_breakdown() over set_cost() for new code.
    """

    trace_id: str
    span_id: str
    project: str
    component: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int

    # Legacy total-cost field. Kept for backward compatibility.
    # Omit (default 0.0) to let Langfuse auto-compute from its model pricing table.
    cost_usd: float = 0.0

    # Breakdown fields (preferred over cost_usd for new code).
    # NOTE: despite the _usd suffix (kept for schema back-compat — renames are
    # forbidden), these hold values in `cost_currency`, which may not be USD.
    input_cost_usd: float | None = None
    output_cost_usd: float | None = None

    # Currency of the cost_* fields. Langfuse v2 ModelUsage has no currency slot,
    # so this is surfaced via generation metadata, not the cost columns. Defaults
    # to USD: the auto-compute and legacy set_cost() paths price in USD (Langfuse
    # Models table is USD). set_cost_breakdown() overrides it per call.
    cost_currency: str = "USD"

    tags: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reconcile_costs(self) -> SpanRecord:
        """Keep cost_usd, input_cost_usd, output_cost_usd consistent.

        Rules:
        - If breakdown provided but cost_usd is 0.0 (default) → auto-sum.
        - If all three provided → breakdown sum must equal cost_usd (±1e-9 float tolerance).
        """
        has_breakdown = self.input_cost_usd is not None or self.output_cost_usd is not None
        if not has_breakdown:
            return self

        input_c = self.input_cost_usd or 0.0
        output_c = self.output_cost_usd or 0.0
        breakdown_sum = input_c + output_c

        if self.cost_usd == 0.0:
            # Auto-sum from breakdown
            self.cost_usd = breakdown_sum
        elif abs(self.cost_usd - breakdown_sum) > 1e-9:
            raise ValueError(
                f"cost_usd ({self.cost_usd}) must equal "
                f"input_cost_usd ({self.input_cost_usd}) + output_cost_usd ({self.output_cost_usd}) "
                f"= {breakdown_sum}"
            )
        return self

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
