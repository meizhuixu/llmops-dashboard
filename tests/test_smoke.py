"""Smoke tests — verify imports and basic wiring work without external services."""

from __future__ import annotations

import llmops_dashboard
from llmops_dashboard.instrumentation import LLMTracer, SpanRecord


def test_package_imports() -> None:
    assert hasattr(llmops_dashboard, "LLMTracer")
    assert llmops_dashboard.__version__ == "0.1.0"


def test_llmtracer_is_importable() -> None:
    assert LLMTracer is not None


def test_spanrecord_is_importable() -> None:
    assert SpanRecord is not None


def test_alerting_imports() -> None:
    from llmops_dashboard.alerting import AlertRule, load_rules  # noqa: F401

    assert AlertRule is not None
    assert load_rules is not None


def test_eval_imports() -> None:
    from llmops_dashboard.eval.multi_model_compare import MultiModelEval  # noqa: F401

    assert MultiModelEval is not None


def test_ab_testing_imports() -> None:
    from llmops_dashboard.ab_testing.router import PromptRouter  # noqa: F401

    assert PromptRouter is not None
