"""One-shot alert evaluation pass against the live Langfuse backend.

Usage:
    uv run python -m llmops_dashboard.alerting

Loads rules.yaml, fetches the widest rule window from Langfuse, evaluates,
and dispatches notifications (log fallback when slack/email unconfigured).
Exit code 0 = pass ran; the number of fired events is printed.
"""

from __future__ import annotations

import logging
import sys

from llmops_dashboard.alerting.engine import AlertEngine
from llmops_dashboard.alerting.rules import load_rules


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    rules = load_rules()
    engine = AlertEngine(rules)
    events = engine.run_once()
    print(f"alert pass: {len(rules)} rules evaluated, {len(events)} events fired")
    for event in events:
        print(
            f"  [{event.rule.severity.upper()}] {event.rule.name}: "
            f"{event.rule.metric}={event.value} (trace {event.span.trace_id[:8]}…, "
            f"project={event.span.project})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
