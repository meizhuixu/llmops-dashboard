from __future__ import annotations

import logging
import os
import time
from types import TracebackType
from typing import Any

from llmops_dashboard.instrumentation.client import LangfuseClient
from llmops_dashboard.instrumentation.schema import SpanRecord

logger = logging.getLogger(__name__)


class LLMTracer:
    """Context manager that measures LLM call latency and ships a SpanRecord to Langfuse.

    Usage::

        with LLMTracer(project="auto-sentinel", component="diagnosis-agent",
                       model="claude-opus-4-7") as t:
            response = client.messages.create(...)
            t.set_tokens(prompt=response.usage.input_tokens,
                         completion=response.usage.output_tokens)
            t.set_cost(0.015)
        # On __exit__: latency computed automatically and SpanRecord sent to Langfuse
    """

    def __init__(
        self,
        project: str,
        component: str,
        model: str,
        tags: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
        client: LangfuseClient | None = None,
    ) -> None:
        self.project = project
        self.component = component
        self.model = model
        self.tags = dict(tags or {})
        self.metadata = dict(metadata or {})
        self._client = client or LangfuseClient()

        # Langfuse v4 (OTel-based) requires 32 lowercase hex char trace/span IDs
        self._trace_id = os.urandom(16).hex()
        self._span_id = os.urandom(8).hex()
        self._start_ns: int = 0
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._cost_usd: float = 0.0

    def set_tokens(self, *, prompt: int, completion: int) -> None:
        self._prompt_tokens = prompt
        self._completion_tokens = completion

    def set_cost(self, cost_usd: float) -> None:
        self._cost_usd = cost_usd

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def span_id(self) -> str:
        return self._span_id

    def __enter__(self) -> LLMTracer:
        self._start_ns = time.perf_counter_ns()
        logger.debug(
            "LLMTracer started: project=%s component=%s model=%s trace_id=%s",
            self.project,
            self.component,
            self.model,
            self._trace_id,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        elapsed_ns = time.perf_counter_ns() - self._start_ns
        latency_ms = int(elapsed_ns / 1_000_000)

        record = SpanRecord(
            trace_id=self._trace_id,
            span_id=self._span_id,
            project=self.project,
            component=self.component,
            model=self.model,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            latency_ms=latency_ms,
            cost_usd=self._cost_usd,
            tags=self.tags,
            metadata={
                **self.metadata,
                **({"error": str(exc_val)} if exc_val else {}),
            },
        )

        logger.info(
            "LLMTracer finished: project=%s latency_ms=%d tokens=%d cost_usd=%.4f",
            self.project,
            latency_ms,
            record.total_tokens,
            self._cost_usd,
        )
        self._client.send(record)
