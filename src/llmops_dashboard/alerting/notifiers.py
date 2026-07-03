"""Alert notifier stubs — Phase 3 implementation.

SlackNotifier and EmailNotifier send alert payloads when rules are triggered.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from llmops_dashboard.alerting.rules import AlertRule

logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    @abstractmethod
    def notify(self, rule: AlertRule, value: float, context: dict[str, str]) -> None: ...


class SlackNotifier(BaseNotifier):
    """Sends alert text to a Slack incoming webhook (Phase 3).

    `client` is an injection seam for tests (anything with
    `send(*, text: str)`); production lazily builds a slack_sdk
    WebhookClient. Send failures are logged, never raised — alerting must
    not take down the evaluation pass.
    """

    def __init__(self, webhook_url: str, client: Any | None = None) -> None:
        self._webhook_url = webhook_url
        self._client = client

    def notify(self, rule: AlertRule, value: float, context: dict[str, str]) -> None:
        if self._client is None:
            from slack_sdk.webhook import WebhookClient

            self._client = WebhookClient(self._webhook_url)
        text = (
            f":rotating_light: [{rule.severity.upper()}] {rule.name} — "
            f"{rule.metric} {rule.operator} {rule.threshold} (observed {value}) "
            f"| {context}"
        )
        try:
            self._client.send(text=text)
        except Exception:
            logger.exception("Slack notification failed for rule %s", rule.name)


class EmailNotifier(BaseNotifier):
    def __init__(self, smtp_host: str, smtp_port: int, from_addr: str, to_addr: str) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._from_addr = from_addr
        self._to_addr = to_addr

    def notify(self, rule: AlertRule, value: float, context: dict[str, str]) -> None:
        raise NotImplementedError("EmailNotifier is Phase 3 — not yet implemented")


class LogNotifier(BaseNotifier):
    """Fallback notifier — logs the alert. Usable in Phase 1 for smoke testing."""

    def notify(self, rule: AlertRule, value: float, context: dict[str, str]) -> None:
        logger.warning(
            "ALERT [%s] rule=%s metric=%s value=%s threshold=%s context=%s",
            rule.severity.upper(),
            rule.name,
            rule.metric,
            value,
            rule.threshold,
            context,
        )
