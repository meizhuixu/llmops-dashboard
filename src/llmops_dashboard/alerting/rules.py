"""AlertRule Pydantic V2 schema + YAML loader.

Triggering logic (evaluating traces against rules) is Phase 3.
This module only handles definition and parsing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_RULES_FILE = Path(__file__).parent / "rules.yaml"

Operator = Literal[">", ">=", "<", "<=", "=="]
Severity = Literal["info", "warning", "critical"]
Notifier = Literal["slack", "email", "log"]


class AlertRule(BaseModel):
    """Declarative alert rule — all thresholds live in rules.yaml, not in code."""

    name: str
    metric: str = Field(description="SpanRecord field to evaluate (e.g. 'latency_ms', 'cost_usd')")
    operator: Operator
    threshold: float
    window_minutes: int = Field(default=5, ge=1)
    notifier: Notifier = "log"
    severity: Severity = "warning"
    project_filter: str | None = Field(
        default=None,
        description="If set, rule only applies to traces with this project tag",
    )

    def evaluate(self, value: float) -> bool:
        """Return True if `value` violates this rule."""
        ops: dict[str, bool] = {
            ">": value > self.threshold,
            ">=": value >= self.threshold,
            "<": value < self.threshold,
            "<=": value <= self.threshold,
            "==": value == self.threshold,
        }
        return ops[self.operator]


def load_rules(path: Path = _RULES_FILE) -> list[AlertRule]:
    """Parse rules.yaml and return validated AlertRule list."""
    if not path.exists():
        logger.warning("Alert rules file not found: %s", path)
        return []

    with path.open() as fh:
        raw = yaml.safe_load(fh) or []

    rules = [AlertRule.model_validate(item) for item in raw]
    logger.info("Loaded %d alert rules from %s", len(rules), path)
    return rules
