"""SpanRecord Pydantic V2 schema boundary tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from llmops_dashboard.instrumentation.schema import SpanRecord


def _minimal() -> dict[str, object]:
    return {
        "trace_id": "abc123def456abc123def456abc12345",
        "span_id": "abc123def456abc1",
        "project": "test-project",
        "component": "test-component",
        "model": "claude-sonnet-4-6",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "latency_ms": 1200,
        "cost_usd": 0.001,
    }


def test_minimal_valid_record() -> None:
    record = SpanRecord.model_validate(_minimal())
    assert record.project == "test-project"
    assert record.tags == {}
    assert record.metadata == {}


def test_total_tokens_property() -> None:
    record = SpanRecord.model_validate(_minimal())
    assert record.total_tokens == 150


def test_tags_default_empty_dict() -> None:
    record = SpanRecord.model_validate(_minimal())
    assert isinstance(record.tags, dict)
    assert len(record.tags) == 0


def test_tags_are_accepted() -> None:
    data = {**_minimal(), "tags": {"env": "prod", "version": "2.0"}}
    record = SpanRecord.model_validate(data)
    assert record.tags["env"] == "prod"
    assert record.tags["version"] == "2.0"


def test_metadata_accepts_nested_values() -> None:
    data = {**_minimal(), "metadata": {"nested": {"key": "value"}, "count": 42}}
    record = SpanRecord.model_validate(data)
    assert record.metadata["count"] == 42


def test_missing_required_field_raises() -> None:
    data = _minimal()
    del data["project"]
    with pytest.raises(ValidationError):
        SpanRecord.model_validate(data)


def test_wrong_type_prompt_tokens_raises() -> None:
    data = {**_minimal(), "prompt_tokens": "not-an-int"}
    with pytest.raises(ValidationError):
        SpanRecord.model_validate(data)


def test_negative_latency_is_allowed() -> None:
    # We don't constrain negative latency — it can happen in tests with mocked time
    data = {**_minimal(), "latency_ms": -1}
    record = SpanRecord.model_validate(data)
    assert record.latency_ms == -1


def test_zero_cost_is_allowed() -> None:
    data = {**_minimal(), "cost_usd": 0.0}
    record = SpanRecord.model_validate(data)
    assert record.cost_usd == 0.0


def test_model_dump_is_json_serializable() -> None:
    import json

    record = SpanRecord.model_validate(_minimal())
    dumped = record.model_dump()
    # Should not raise
    json.dumps(dumped)


def test_model_validate_roundtrip() -> None:
    original = SpanRecord.model_validate(_minimal())
    roundtripped = SpanRecord.model_validate(original.model_dump())
    assert original == roundtripped


# --- Cost breakdown tests ---


def test_breakdown_auto_sums_to_total() -> None:
    data = {
        **_minimal(),
        "cost_usd": 0.0,  # omit / default — validator should fill it in
        "input_cost_usd": 0.003,
        "output_cost_usd": 0.012,
    }
    record = SpanRecord.model_validate(data)
    assert record.input_cost_usd == pytest.approx(0.003)
    assert record.output_cost_usd == pytest.approx(0.012)
    assert record.cost_usd == pytest.approx(0.015)


def test_breakdown_inconsistent_with_total_raises() -> None:
    data = {
        **_minimal(),
        "cost_usd": 0.020,  # doesn't equal 0.003 + 0.012 = 0.015
        "input_cost_usd": 0.003,
        "output_cost_usd": 0.012,
    }
    with pytest.raises(ValidationError, match="cost_usd"):
        SpanRecord.model_validate(data)


def test_legacy_cost_only_still_works() -> None:
    data = {**_minimal(), "cost_usd": 0.007}
    record = SpanRecord.model_validate(data)
    assert record.cost_usd == pytest.approx(0.007)
    assert record.input_cost_usd is None
    assert record.output_cost_usd is None


def test_set_cost_emits_deprecation_warning() -> None:
    import warnings

    from llmops_dashboard.instrumentation.tracer import LLMTracer

    tracer = LLMTracer(project="p", component="c", model="m")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tracer.set_cost(0.005)

    assert len(caught) == 1
    assert issubclass(caught[0].category, DeprecationWarning)
    assert "set_cost_breakdown" in str(caught[0].message)
