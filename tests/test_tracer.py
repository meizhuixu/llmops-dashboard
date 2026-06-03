"""Tests for LLMTracer trace_id handling — root and child span scenarios."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from llmops_dashboard.instrumentation import LLMTracer
from llmops_dashboard.instrumentation.client import LangfuseClient
from llmops_dashboard.instrumentation.schema import SpanRecord

_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SHARED_TRACE_ID = "a" * 32


def _make_mock_client() -> MagicMock:
    return MagicMock(spec=LangfuseClient)


def _captured(mock: MagicMock) -> tuple[SpanRecord, bool]:
    """Return (record, owns_trace) from the most recent client.send call."""
    assert mock.send.call_count >= 1
    args, kwargs = mock.send.call_args
    record = args[0] if args else kwargs["record"]
    owns_trace = kwargs.get("owns_trace")
    if owns_trace is None and len(args) > 1:
        owns_trace = args[1]
    assert isinstance(record, SpanRecord)
    assert isinstance(owns_trace, bool)
    return record, owns_trace


def test_default_trace_id_is_generated() -> None:
    """No trace_id passed: LLMTracer generates a fresh 32-char hex trace_id and
    ships a SpanRecord carrying that value with owns_trace=True."""
    mock_client = _make_mock_client()

    with LLMTracer(
        project="auto-sentinel",
        component="root-agent",
        model="claude-opus-4-7",
        client=mock_client,
    ) as t:
        t.set_tokens(prompt=10, completion=20)
        generated_trace_id = t.trace_id

    assert _TRACE_ID_PATTERN.fullmatch(generated_trace_id) is not None
    record, owns_trace = _captured(mock_client)
    assert record.trace_id == generated_trace_id
    assert owns_trace is True


def test_external_trace_id_is_propagated() -> None:
    """trace_id supplied: LLMTracer uses it verbatim, ships SpanRecord with
    matching trace_id, and signals owns_trace=False to the client."""
    mock_client = _make_mock_client()

    with LLMTracer(
        project="auto-sentinel",
        component="diagnosis-agent",
        model="claude-opus-4-7",
        trace_id=_SHARED_TRACE_ID,
        client=mock_client,
    ) as t:
        t.set_tokens(prompt=5, completion=15)
        assert t.trace_id == _SHARED_TRACE_ID

    record, owns_trace = _captured(mock_client)
    assert record.trace_id == _SHARED_TRACE_ID
    assert owns_trace is False


def test_two_tracers_share_trace_id() -> None:
    """Two LLMTracer instances passed the same trace_id ship two SpanRecords
    with identical trace_id but distinct span_id — the multi-agent invariant."""
    mock_client = _make_mock_client()

    with LLMTracer(
        project="auto-sentinel",
        component="diagnosis-agent",
        model="claude-opus-4-7",
        trace_id=_SHARED_TRACE_ID,
        client=mock_client,
    ) as t1:
        t1.set_tokens(prompt=1, completion=2)

    with LLMTracer(
        project="auto-sentinel",
        component="report-agent",
        model="claude-opus-4-7",
        trace_id=_SHARED_TRACE_ID,
        client=mock_client,
    ) as t2:
        t2.set_tokens(prompt=3, completion=4)

    assert mock_client.send.call_count == 2
    first_call, second_call = mock_client.send.call_args_list

    def _unpack(call: object) -> tuple[SpanRecord, bool]:
        args, kwargs = call  # type: ignore[misc]
        record = args[0] if args else kwargs["record"]
        owns_trace = kwargs.get("owns_trace")
        if owns_trace is None and len(args) > 1:
            owns_trace = args[1]
        return record, owns_trace

    r1, owns1 = _unpack(first_call)
    r2, owns2 = _unpack(second_call)

    assert r1.trace_id == _SHARED_TRACE_ID
    assert r2.trace_id == _SHARED_TRACE_ID
    assert r1.span_id != r2.span_id
    assert owns1 is False
    assert owns2 is False


def test_cost_breakdown_records_currency() -> None:
    """set_cost_breakdown(currency=...) labels the SpanRecord with that currency
    and auto-sums cost_usd from the input/output split, so downstream metadata
    can disambiguate CNY (Ark/GLM) from USD figures within one schema."""
    mock_client = _make_mock_client()

    with LLMTracer(
        project="auto-sentinel",
        component="diagnosis-agent",
        model="doubao-pro",
        client=mock_client,
    ) as t:
        t.set_tokens(prompt=100, completion=200)
        t.set_cost_breakdown(input_cost=0.3, output_cost=1.2, currency="CNY")

    record, _ = _captured(mock_client)
    assert record.cost_currency == "CNY"
    assert record.input_cost_usd == 0.3
    assert record.output_cost_usd == 1.2
    assert record.cost_usd == pytest.approx(1.5)


def test_cost_breakdown_currency_defaults_to_cny() -> None:
    """currency defaults to CNY — the Ark/GLM billing currency that drove the
    signature change — when the caller omits it."""
    mock_client = _make_mock_client()

    with LLMTracer(
        project="auto-sentinel",
        component="diagnosis-agent",
        model="doubao-pro",
        client=mock_client,
    ) as t:
        t.set_tokens(prompt=1, completion=1)
        t.set_cost_breakdown(input_cost=0.1, output_cost=0.1)

    record, _ = _captured(mock_client)
    assert record.cost_currency == "CNY"


def test_no_cost_call_defaults_currency_to_usd() -> None:
    """Auto-compute path (no cost call): cost_currency stays USD, matching the
    Langfuse Models pricing table so auto-priced figures are not mislabeled."""
    mock_client = _make_mock_client()

    with LLMTracer(
        project="devdocs-rag",
        component="rag-chain",
        model="claude-sonnet-4-6",
        client=mock_client,
    ) as t:
        t.set_tokens(prompt=10, completion=20)

    record, _ = _captured(mock_client)
    assert record.cost_currency == "USD"


@pytest.mark.parametrize(
    "bad_trace_id",
    [
        "",
        "too-short",
        "G" * 32,
        "A" * 32,
        "a" * 31,
        "a" * 33,
        "  " + "a" * 30,
        "a" * 32 + "\n",
        "a" * 31 + "Z",
    ],
)
def test_invalid_trace_id_raises(bad_trace_id: str) -> None:
    """Malformed trace_id is rejected at __init__ with a ValueError that names
    the format requirement, so callers see the failure at construction time
    rather than at flush time inside Langfuse."""
    with pytest.raises(ValueError, match="32 lowercase hex"):
        LLMTracer(
            project="auto-sentinel",
            component="diagnosis-agent",
            model="claude-opus-4-7",
            trace_id=bad_trace_id,
            client=_make_mock_client(),
        )
