from __future__ import annotations

import logging

from langfuse import Langfuse
from langfuse.model import ModelUsage

from llmops_dashboard.config import settings
from llmops_dashboard.instrumentation.schema import SpanRecord

logger = logging.getLogger(__name__)


class LangfuseClient:
    """Thin wrapper around the Langfuse SDK (v2.x) that translates SpanRecord → trace/generation."""

    def __init__(
        self,
        host: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self._langfuse = Langfuse(
            host=host or settings.langfuse_host,
            public_key=public_key or settings.langfuse_public_key,
            secret_key=secret_key or settings.langfuse_secret_key,
        )

    def send(self, record: SpanRecord, owns_trace: bool = True) -> None:
        """Ship a SpanRecord to Langfuse.

        When ``owns_trace`` is True (default), creates a new Langfuse trace and
        nests one generation span under it — the standard single-call pattern.

        When ``owns_trace`` is False, attaches the generation to an existing
        trace identified by ``record.trace_id`` without emitting any trace-level
        payload. This is the multi-agent pattern: the caller (e.g. a LangGraph
        entry point) owns the parent trace and its name/tags/metadata, and each
        sub-agent's LLMTracer only contributes a generation. Avoids overwriting
        parent trace fields via last-write-wins.
        """
        try:
            if owns_trace:
                trace = self._langfuse.trace(
                    id=record.trace_id,
                    name=f"{record.project}/{record.component}",
                    metadata=record.metadata,
                    tags=_flatten_tags(record),
                )
                trace.generation(
                    id=record.span_id,
                    name=record.component,
                    model=record.model,
                    usage=_build_usage(record),
                    metadata={
                        "latency_ms": record.latency_ms,
                        "cost_currency": record.cost_currency,
                        **record.metadata,
                    },
                )
            else:
                self._langfuse.generation(
                    trace_id=record.trace_id,
                    id=record.span_id,
                    name=record.component,
                    model=record.model,
                    usage=_build_usage(record),
                    metadata={
                        "latency_ms": record.latency_ms,
                        "cost_currency": record.cost_currency,
                        **record.metadata,
                    },
                )
            self._langfuse.flush()
            logger.debug("SpanRecord sent to Langfuse: trace_id=%s", record.trace_id)
        except Exception:
            logger.exception("Failed to send SpanRecord to Langfuse: trace_id=%s", record.trace_id)


def _build_usage(record: SpanRecord) -> ModelUsage:
    """Translate SpanRecord cost fields to Langfuse ModelUsage.

    Cost priority:
    - breakdown (input_cost_usd + output_cost_usd) → sent as input_cost + output_cost + total_cost
    - total only (cost_usd > 0, no breakdown) → sent as total_cost
    - no cost (cost_usd == 0, no breakdown) → omit cost fields; Langfuse auto-computes from pricing
    """
    usage: ModelUsage = {
        "unit": "TOKENS",
        "input": record.prompt_tokens,
        "output": record.completion_tokens,
        "total": record.total_tokens,
        "input_cost": None,
        "output_cost": None,
        "total_cost": None,
    }

    has_breakdown = record.input_cost_usd is not None or record.output_cost_usd is not None
    if has_breakdown:
        usage["input_cost"] = record.input_cost_usd
        usage["output_cost"] = record.output_cost_usd
        usage["total_cost"] = record.cost_usd
    elif record.cost_usd > 0.0:
        usage["total_cost"] = record.cost_usd
    # else: leave cost fields None → Langfuse auto-computes from model pricing table

    return usage


def _flatten_tags(record: SpanRecord) -> list[str]:
    """Convert SpanRecord tags + project/component into Langfuse tag list."""
    base = [f"project:{record.project}", f"component:{record.component}", f"model:{record.model}"]
    extra = [f"{k}:{v}" for k, v in record.tags.items()]
    return base + extra
