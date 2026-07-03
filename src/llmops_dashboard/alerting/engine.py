"""Phase 3 — alert triggering engine: windowed fetch → evaluate → notify.

The engine is transport-agnostic: span data arrives through a `fetcher`
callable (window_start → list[ObservedSpan]), so tests inject fixtures and
production uses `langfuse_fetcher`, which reads the Langfuse public API
(observations joined with trace tags — two list calls, no N+1).

Evaluation is per-span: each span violating a rule inside that rule's window
produces one AlertEvent and one notification. Aggregate metrics (windowed
sums / rates) are a deliberate later extension — per-span keeps the semantics
identical to AlertRule.evaluate(value) as already tested in
tests/test_alerting_rules.py.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

from llmops_dashboard.alerting.notifiers import BaseNotifier, LogNotifier, SlackNotifier
from llmops_dashboard.alerting.rules import AlertRule
from llmops_dashboard.config import settings

logger = logging.getLogger(__name__)

_PROJECT_TAG_PREFIX = "project:"


class ObservedSpan(BaseModel):
    """One generation observed in the backend, normalised for rule evaluation."""

    trace_id: str
    name: str = ""
    model: str = ""
    project: str | None = None
    start_time: datetime
    latency_ms: float = 0.0
    cost: float = 0.0  # native billing currency units (CNY for Ark projects)
    prompt_tokens: int = 0
    completion_tokens: int = 0


class AlertEvent(BaseModel):
    """A rule violation: which rule, which span, and the offending value."""

    rule: AlertRule
    span: ObservedSpan
    value: float


# Maps AlertRule.metric names (rules.yaml vocabulary) to ObservedSpan fields.
# `cost_usd` is the historical rules.yaml name; it reads ObservedSpan.cost,
# which is in the span's native billing currency (see the `_usd` misnomer
# entry in DEBT.md).
_METRIC_FIELDS: dict[str, str] = {
    "latency_ms": "latency_ms",
    "cost_usd": "cost",
    "cost": "cost",
    "prompt_tokens": "prompt_tokens",
    "completion_tokens": "completion_tokens",
}

Fetcher = Callable[[datetime], list[ObservedSpan]]


class AlertEngine:
    """Evaluates declarative AlertRules against observed spans and notifies."""

    def __init__(
        self,
        rules: list[AlertRule],
        *,
        fetcher: Fetcher | None = None,
        notifiers: dict[str, BaseNotifier] | None = None,
    ) -> None:
        self._rules = rules
        self._fetcher: Fetcher = fetcher if fetcher is not None else langfuse_fetcher
        self._notifiers = notifiers

    def resolve_notifier(self, rule: AlertRule) -> BaseNotifier:
        """Return the notifier for a rule, falling back to LogNotifier.

        slack → SlackNotifier only when SLACK_WEBHOOK_URL is configured;
        email → LogNotifier (EmailNotifier is still a stub). Fallbacks log the
        alert rather than raising, so an unconfigured channel never silently
        swallows a violation.
        """
        if self._notifiers is not None and rule.notifier in self._notifiers:
            return self._notifiers[rule.notifier]
        if rule.notifier == "slack" and settings.slack_webhook_url:
            return SlackNotifier(settings.slack_webhook_url)
        if rule.notifier != "log":
            logger.warning(
                "notifier %r not configured for rule %s — falling back to log",
                rule.notifier,
                rule.name,
            )
        return LogNotifier()

    def run_once(self, now: datetime | None = None) -> list[AlertEvent]:
        """One evaluation pass: fetch the widest rule window, evaluate, notify."""
        if not self._rules:
            return []
        now = now or datetime.now(tz=UTC)
        widest = max(rule.window_minutes for rule in self._rules)
        spans = self._fetcher(now - timedelta(minutes=widest))

        events: list[AlertEvent] = []
        for rule in self._rules:
            field = _METRIC_FIELDS.get(rule.metric)
            if field is None:
                logger.warning("rule %s has unknown metric %r — skipping", rule.name, rule.metric)
                continue
            window_start = now - timedelta(minutes=rule.window_minutes)
            for span in spans:
                if span.start_time < window_start:
                    continue
                if rule.project_filter is not None and span.project != rule.project_filter:
                    continue
                value = float(getattr(span, field))
                if rule.evaluate(value):
                    event = AlertEvent(rule=rule, span=span, value=value)
                    events.append(event)
                    self.resolve_notifier(rule).notify(
                        rule,
                        value,
                        {
                            "trace_id": span.trace_id,
                            "project": span.project or "",
                            "component": span.name,
                            "model": span.model,
                        },
                    )
        logger.info(
            "alert pass complete: %d rules, %d spans, %d events",
            len(self._rules),
            len(spans),
            len(events),
        )
        return events


def langfuse_fetcher(window_start: datetime) -> list[ObservedSpan]:
    """Fetch generations since `window_start` from the Langfuse public API.

    Two list calls: observations (usage / cost / timing) + traces (tags →
    project), joined on trace_id in memory. Pagination capped defensively.
    """
    auth = (settings.langfuse_public_key, settings.langfuse_secret_key)
    base = settings.langfuse_host.rstrip("/")
    iso = window_start.isoformat()

    def _pages(path: str, params: dict[str, str], key_limit: int = 10) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, key_limit + 1):
            resp = httpx.get(
                f"{base}{path}",
                params={**params, "page": str(page), "limit": "100"},
                auth=auth,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            items.extend(data)
            if len(data) < 100:
                break
        return items

    trace_project: dict[str, str | None] = {}
    for trace in _pages("/api/public/traces", {"fromTimestamp": iso}):
        project = None
        for tag in trace.get("tags") or []:
            if isinstance(tag, str) and tag.startswith(_PROJECT_TAG_PREFIX):
                project = tag[len(_PROJECT_TAG_PREFIX) :]
        trace_project[str(trace["id"])] = project

    spans: list[ObservedSpan] = []
    for obs in _pages("/api/public/observations", {"fromStartTime": iso, "type": "GENERATION"}):
        start_raw = obs.get("startTime")
        end_raw = obs.get("endTime")
        if not isinstance(start_raw, str):
            continue
        start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        latency_ms = 0.0
        if isinstance(end_raw, str):
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            latency_ms = (end - start).total_seconds() * 1000
        usage = obs.get("usage") or {}
        trace_id = str(obs.get("traceId") or "")
        spans.append(
            ObservedSpan(
                trace_id=trace_id,
                name=str(obs.get("name") or ""),
                model=str(obs.get("model") or ""),
                project=trace_project.get(trace_id),
                start_time=start,
                latency_ms=latency_ms,
                cost=float(obs.get("calculatedTotalCost") or 0.0),
                prompt_tokens=int(usage.get("input") or 0),
                completion_tokens=int(usage.get("output") or 0),
            )
        )
    return spans


__all__ = ["AlertEngine", "AlertEvent", "Fetcher", "ObservedSpan", "langfuse_fetcher"]
