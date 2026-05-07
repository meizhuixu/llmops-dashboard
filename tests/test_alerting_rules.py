"""AlertRule YAML parsing and evaluate() logic tests.

Every rule in alerting/rules.yaml must have at least one test here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmops_dashboard.alerting.rules import AlertRule, load_rules

RULES_FILE = Path(__file__).parent.parent / "src/llmops_dashboard/alerting/rules.yaml"


# --- YAML parsing ---


def test_load_rules_returns_list() -> None:
    rules = load_rules(RULES_FILE)
    assert isinstance(rules, list)
    assert len(rules) > 0


def test_all_rules_are_alert_rule_instances() -> None:
    rules = load_rules(RULES_FILE)
    for rule in rules:
        assert isinstance(rule, AlertRule)


def test_rules_have_required_fields() -> None:
    rules = load_rules(RULES_FILE)
    for rule in rules:
        assert rule.name
        assert rule.metric
        assert rule.operator
        assert rule.threshold is not None


def test_load_rules_missing_file_returns_empty_list(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent.yaml"
    result = load_rules(missing)
    assert result == []


def test_load_rules_empty_file_returns_empty_list(tmp_path: Path) -> None:
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")
    result = load_rules(empty_file)
    assert result == []


# --- Rules from rules.yaml ---


def _get_rule(name: str) -> AlertRule:
    rules = load_rules(RULES_FILE)
    for rule in rules:
        if rule.name == name:
            return rule
    pytest.fail(f"Rule '{name}' not found in rules.yaml")


class TestHighLatencyRule:
    def test_triggers_above_threshold(self) -> None:
        rule = _get_rule("high_latency")
        assert rule.evaluate(5001) is True

    def test_no_trigger_at_threshold(self) -> None:
        rule = _get_rule("high_latency")
        assert rule.evaluate(5000) is False

    def test_no_trigger_below_threshold(self) -> None:
        rule = _get_rule("high_latency")
        assert rule.evaluate(1000) is False

    def test_severity_is_warning(self) -> None:
        rule = _get_rule("high_latency")
        assert rule.severity == "warning"

    def test_notifier_is_slack(self) -> None:
        rule = _get_rule("high_latency")
        assert rule.notifier == "slack"


class TestCostSpikeRule:
    def test_triggers_above_threshold(self) -> None:
        rule = _get_rule("cost_spike")
        assert rule.evaluate(0.11) is True

    def test_no_trigger_at_threshold(self) -> None:
        rule = _get_rule("cost_spike")
        assert rule.evaluate(0.10) is False

    def test_severity_is_critical(self) -> None:
        rule = _get_rule("cost_spike")
        assert rule.severity == "critical"


class TestZeroTokensRule:
    def test_triggers_on_zero(self) -> None:
        rule = _get_rule("zero_tokens")
        assert rule.evaluate(0) is True

    def test_no_trigger_on_nonzero(self) -> None:
        rule = _get_rule("zero_tokens")
        assert rule.evaluate(1) is False


class TestAutoSentinelHighLatencyRule:
    def test_triggers_at_threshold(self) -> None:
        rule = _get_rule("auto_sentinel_high_latency")
        assert rule.evaluate(8000) is True

    def test_triggers_above_threshold(self) -> None:
        rule = _get_rule("auto_sentinel_high_latency")
        assert rule.evaluate(10000) is True

    def test_no_trigger_below_threshold(self) -> None:
        rule = _get_rule("auto_sentinel_high_latency")
        assert rule.evaluate(7999) is False

    def test_project_filter_set(self) -> None:
        rule = _get_rule("auto_sentinel_high_latency")
        assert rule.project_filter == "auto-sentinel"

    def test_severity_is_critical(self) -> None:
        rule = _get_rule("auto_sentinel_high_latency")
        assert rule.severity == "critical"


# --- AlertRule.evaluate() logic coverage ---


@pytest.mark.parametrize(
    ("operator", "threshold", "value", "expected"),
    [
        (">", 100, 101, True),
        (">", 100, 100, False),
        (">=", 100, 100, True),
        (">=", 100, 99, False),
        ("<", 100, 99, True),
        ("<", 100, 100, False),
        ("<=", 100, 100, True),
        ("<=", 100, 101, False),
        ("==", 100, 100, True),
        ("==", 100, 99, False),
    ],
)
def test_evaluate_operators(operator: str, threshold: float, value: float, expected: bool) -> None:
    rule = AlertRule(
        name="test",
        metric="latency_ms",
        operator=operator,  # type: ignore[arg-type]
        threshold=threshold,
    )
    assert rule.evaluate(value) is expected
