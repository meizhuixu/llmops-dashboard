from __future__ import annotations

import logging

from langfuse import Langfuse

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

    def send(self, record: SpanRecord) -> None:
        """Ship a SpanRecord to Langfuse as a trace with one generation span."""
        try:
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
                usage={
                    "promptTokens": record.prompt_tokens,
                    "completionTokens": record.completion_tokens,
                    "totalTokens": record.total_tokens,
                },
                metadata={
                    "latency_ms": record.latency_ms,
                    "cost_usd": record.cost_usd,
                    **record.metadata,
                },
            )
            self._langfuse.flush()
            logger.debug("SpanRecord sent to Langfuse: trace_id=%s", record.trace_id)
        except Exception:
            logger.exception("Failed to send SpanRecord to Langfuse: trace_id=%s", record.trace_id)


def _flatten_tags(record: SpanRecord) -> list[str]:
    """Convert SpanRecord tags + project/component into Langfuse tag list."""
    base = [f"project:{record.project}", f"component:{record.component}", f"model:{record.model}"]
    extra = [f"{k}:{v}" for k, v in record.tags.items()]
    return base + extra
