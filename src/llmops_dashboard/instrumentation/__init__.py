"""Instrumentation library — import LLMTracer in any project to start sending traces."""

from llmops_dashboard.instrumentation.schema import SpanRecord
from llmops_dashboard.instrumentation.tracer import LLMTracer

__all__ = ["LLMTracer", "SpanRecord"]
