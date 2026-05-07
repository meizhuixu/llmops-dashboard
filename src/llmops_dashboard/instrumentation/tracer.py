from __future__ import annotations

import logging
import os
import time
import warnings
from types import TracebackType
from typing import Any

from llmops_dashboard.instrumentation.client import LangfuseClient
from llmops_dashboard.instrumentation.schema import SpanRecord

logger = logging.getLogger(__name__)


class LLMTracer:
    """Context manager that measures LLM call latency and ships a SpanRecord to Langfuse.

    Cost reporting options (in order of preference):

    1. (Recommended) Omit all cost calls — Langfuse auto-computes from its Model Pricing table.
       Requires the model name to be configured in Langfuse Settings → Models.

    2. Call set_cost_breakdown(input_usd, output_usd) for split cost tracking.
       Langfuse UI shows separate input / output cost columns.

    3. (Deprecated) Call set_cost(total_usd) for backward compatibility.
       Langfuse receives total_cost only; no input/output split visible in UI.

    Usage::

        with LLMTracer(project="auto-sentinel", component="diagnosis-agent",
                       model="claude-opus-4-7") as t:
            response = client.messages.create(...)
            t.set_tokens(prompt=response.usage.input_tokens,
                         completion=response.usage.output_tokens)
            t.set_cost_breakdown(input_usd=0.003, output_usd=0.012)
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

        # OTel-compatible 32-char hex trace IDs required by Langfuse v2 SDK
        self._trace_id = os.urandom(16).hex()
        self._span_id = os.urandom(8).hex()
        self._start_ns: int = 0
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._cost_usd: float = 0.0
        self._input_cost_usd: float | None = None
        self._output_cost_usd: float | None = None

    def set_tokens(self, *, prompt: int, completion: int) -> None:
        self._prompt_tokens = prompt
        self._completion_tokens = completion

    def set_cost(self, cost_usd: float) -> None:
        """Set total cost. Deprecated — use set_cost_breakdown() for accurate Langfuse reporting.

        Langfuse can only show a single total_cost value; no input/output split will be visible.
        Alternatively, omit cost entirely to let Langfuse auto-compute from its Model Pricing table.
        """
        warnings.warn(
            "set_cost(total_usd) is deprecated. "
            "Use set_cost_breakdown(input_usd, output_usd) for split cost reporting in Langfuse UI, "
            "or omit cost entirely to let Langfuse auto-compute from its model pricing table.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._cost_usd = cost_usd

    def set_cost_breakdown(self, *, input_usd: float, output_usd: float) -> None:
        """Set input and output cost separately for detailed Langfuse cost reporting.

        Langfuse UI will show separate input_cost and output_cost columns.
        cost_usd is auto-computed as input_usd + output_usd.
        """
        self._input_cost_usd = input_usd
        self._output_cost_usd = output_usd
        self._cost_usd = input_usd + output_usd

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
            input_cost_usd=self._input_cost_usd,
            output_cost_usd=self._output_cost_usd,
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
