"""Phase 3 — AlertEngine triggering logic (window fetch → evaluate → notify).

Hermetic: span data comes from an injected fake fetcher and notifications are
captured by a recording notifier — no Langfuse backend, no Slack webhook.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from llmops_dashboard.alerting.engine import AlertEngine, AlertEvent, ObservedSpan
from llmops_dashboard.alerting.notifiers import BaseNotifier, LogNotifier, SlackNotifier
from llmops_dashboard.alerting.rules import AlertRule

NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _span(
    *,
    minutes_ago: float = 0.5,
    project: str | None = "devdocs-rag",
    latency_ms: float = 100.0,
    cost: float = 0.001,
    prompt_tokens: int = 50,
    completion_tokens: int = 100,
) -> ObservedSpan:
    return ObservedSpan(
        trace_id="a" * 32,
        name="rag-api",
        model="ep-test",
        project=project,
        start_time=NOW - timedelta(minutes=minutes_ago),
        latency_ms=latency_ms,
        cost=cost,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


class RecordingNotifier(BaseNotifier):
    def __init__(self) -> None:
        self.calls: list[tuple[AlertRule, float, dict[str, str]]] = []

    def notify(self, rule: AlertRule, value: float, context: dict[str, str]) -> None:
        self.calls.append((rule, value, context))


def _rule(**overrides: object) -> AlertRule:
    base: dict[str, object] = {
        "name": "high_latency",
        "metric": "latency_ms",
        "operator": ">",
        "threshold": 5000,
        "window_minutes": 5,
        "notifier": "log",
        "severity": "warning",
    }
    base.update(overrides)
    return AlertRule.model_validate(base)


def _engine(
    rules: list[AlertRule], spans: list[ObservedSpan], notifier: RecordingNotifier
) -> AlertEngine:
    return AlertEngine(
        rules,
        fetcher=lambda window_start: [s for s in spans if s.start_time >= window_start],
        notifiers={"log": notifier, "slack": notifier, "email": notifier},
    )


def test_violating_span_fires_alert_event() -> None:
    notifier = RecordingNotifier()
    engine = _engine([_rule()], [_span(latency_ms=6000)], notifier)
    events = engine.run_once(now=NOW)
    assert len(events) == 1
    assert isinstance(events[0], AlertEvent)
    assert events[0].value == 6000
    assert len(notifier.calls) == 1


def test_conforming_span_fires_nothing() -> None:
    notifier = RecordingNotifier()
    engine = _engine([_rule()], [_span(latency_ms=100)], notifier)
    assert engine.run_once(now=NOW) == []
    assert notifier.calls == []


def test_span_outside_rule_window_is_ignored() -> None:
    notifier = RecordingNotifier()
    old_span = _span(minutes_ago=10, latency_ms=9999)
    engine = _engine([_rule(window_minutes=5)], [old_span], notifier)
    assert engine.run_once(now=NOW) == []


def test_project_filter_only_matches_tagged_project() -> None:
    notifier = RecordingNotifier()
    rule = _rule(name="auto_sentinel_high_latency", threshold=8000, operator=">=")
    rule = AlertRule.model_validate({**rule.model_dump(), "project_filter": "auto-sentinel"})
    spans = [
        _span(project="devdocs-rag", latency_ms=9000),
        _span(project="auto-sentinel", latency_ms=9000),
        _span(project=None, latency_ms=9000),
    ]
    engine = _engine([rule], spans, notifier)
    events = engine.run_once(now=NOW)
    assert len(events) == 1
    assert events[0].span.project == "auto-sentinel"


def test_zero_tokens_rule_catches_disconnect_spans() -> None:
    """The devdocs-rag DEBT case: client disconnect ships a token-less span."""
    notifier = RecordingNotifier()
    rule = _rule(name="zero_tokens", metric="prompt_tokens", operator="==", threshold=0)
    engine = _engine([rule], [_span(prompt_tokens=0, completion_tokens=0)], notifier)
    events = engine.run_once(now=NOW)
    assert len(events) == 1
    assert events[0].value == 0


def test_cost_spike_rule_uses_cost_metric() -> None:
    notifier = RecordingNotifier()
    rule = _rule(name="cost_spike", metric="cost_usd", operator=">", threshold=0.10)
    engine = _engine([rule], [_span(cost=0.5), _span(cost=0.01)], notifier)
    events = engine.run_once(now=NOW)
    assert len(events) == 1
    assert events[0].value == 0.5


def test_unknown_metric_is_skipped_not_crashed() -> None:
    notifier = RecordingNotifier()
    rule = _rule(name="bogus", metric="no_such_field")
    engine = _engine([rule], [_span()], notifier)
    assert engine.run_once(now=NOW) == []


def test_multiple_rules_multiple_spans() -> None:
    notifier = RecordingNotifier()
    rules = [
        _rule(),
        _rule(name="cost_spike", metric="cost_usd", operator=">", threshold=0.10),
    ]
    spans = [_span(latency_ms=6000, cost=0.5), _span(latency_ms=100, cost=0.01)]
    engine = _engine(rules, spans, notifier)
    events = engine.run_once(now=NOW)
    assert {(e.rule.name, e.value) for e in events} == {
        ("high_latency", 6000),
        ("cost_spike", 0.5),
    }
    assert len(notifier.calls) == 2


def test_default_notifier_resolution_falls_back_to_log() -> None:
    """slack/email rules without configured webhook/SMTP resolve to LogNotifier."""
    engine = AlertEngine([_rule(notifier="slack")], fetcher=lambda _ws: [])
    resolved = engine.resolve_notifier(_rule(notifier="slack"))
    assert isinstance(resolved, LogNotifier)
    resolved_email = engine.resolve_notifier(_rule(notifier="email"))
    assert isinstance(resolved_email, LogNotifier)


# --- SlackNotifier (real implementation, fake webhook client) ---


class _FakeWebhookClient:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, *, text: str) -> object:
        self.sent.append(text)
        return type("Resp", (), {"status_code": 200})()


def test_slack_notifier_sends_webhook_text() -> None:
    fake = _FakeWebhookClient()
    notifier = SlackNotifier("https://hooks.slack.example/x", client=fake)
    notifier.notify(_rule(severity="critical"), 6000, {"trace_id": "t" * 32})
    assert len(fake.sent) == 1
    assert "high_latency" in fake.sent[0]
    assert "CRITICAL" in fake.sent[0]
