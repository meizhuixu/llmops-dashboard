"""Phase 1 end-to-end demo — three cost-reporting patterns.

This script sends 3 traces to Langfuse, each demonstrating a different cost API:

  Trace 1 (auto-sentinel):
    set_cost_breakdown(input_cost, output_cost, currency=...) — RECOMMENDED
    Langfuse UI shows split input_cost + output_cost columns.

  Trace 2 (devdocs-rag):
    No cost call at all — Langfuse auto-computes cost from its Model Pricing table.
    Requires the model name to be configured in Langfuse Settings → Models.

  Trace 3 (devcontext-mcp):
    set_cost(total_usd) — DEPRECATED, kept for backward-compat verification.
    Console will print a DeprecationWarning.
    Langfuse shows total_cost only (no input/output split).

Usage:
    cp .env.example .env
    # Edit .env with your Langfuse API keys from http://localhost:3000
    uv run python examples/dummy_traced_app.py
"""

from __future__ import annotations

import logging
import random
import time
import warnings

from llmops_dashboard.instrumentation import LLMTracer

# Show DeprecationWarnings in console output for Trace 3 demo
warnings.filterwarnings("always", category=DeprecationWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Per-token pricing (USD per 1M tokens) — used for set_cost_breakdown demo
_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "gpt-4o": (2.5, 10.0),
}


def fake_llm_call(complexity: str = "medium") -> dict[str, int]:
    """Simulate an LLM API call with realistic latency and token counts."""
    latency_map = {"low": (0.1, 0.3), "medium": (0.5, 1.5), "high": (2.0, 4.0)}
    lo, hi = latency_map.get(complexity, (0.5, 1.5))
    time.sleep(random.uniform(lo, hi))
    return {
        "input_tokens": random.randint(200, 1500),
        "output_tokens": random.randint(100, 800),
    }


def _input_cost(model: str, tokens: int) -> float:
    in_rate, _ = _PRICING.get(model, (5.0, 15.0))
    return tokens * in_rate / 1_000_000


def _output_cost(model: str, tokens: int) -> float:
    _, out_rate = _PRICING.get(model, (5.0, 15.0))
    return tokens * out_rate / 1_000_000


# ---------------------------------------------------------------------------
# Trace 1: set_cost_breakdown — RECOMMENDED path
# ---------------------------------------------------------------------------
def simulate_auto_sentinel() -> None:
    """auto-sentinel: uses set_cost_breakdown for split cost reporting."""
    logger.info("--- [Trace 1] auto-sentinel: set_cost_breakdown (recommended) ---")
    model = "claude-opus-4-7"

    with LLMTracer(
        project="auto-sentinel",
        component="diagnosis-agent",
        model=model,
        tags={"env": "demo", "pr_number": "42", "repo": "acme/backend"},
        metadata={"trigger": "push", "diff_lines": 287},
    ) as t:
        usage = fake_llm_call("high")
        t.set_tokens(prompt=usage["input_tokens"], completion=usage["output_tokens"])
        t.set_cost_breakdown(
            input_cost=_input_cost(model, usage["input_tokens"]),
            output_cost=_output_cost(model, usage["output_tokens"]),
            currency="USD",
        )

    logger.info("auto-sentinel trace sent: trace_id=%s", t.trace_id)


# ---------------------------------------------------------------------------
# Trace 2: no cost call — Langfuse auto-compute path
# ---------------------------------------------------------------------------
def simulate_devdocs_rag() -> None:
    """devdocs-rag: omits cost — Langfuse auto-computes from Model Pricing table."""
    logger.info("--- [Trace 2] devdocs-rag: no cost call (auto-compute) ---")

    with LLMTracer(
        project="devdocs-rag",
        component="rag-retrieval-chain",
        model="claude-sonnet-4-6",
        tags={"env": "demo", "query_type": "api-reference"},
        metadata={"retrieved_chunks": 5, "rerank_score": 0.87},
    ) as t:
        usage = fake_llm_call("medium")
        t.set_tokens(prompt=usage["input_tokens"], completion=usage["output_tokens"])
        # No set_cost / set_cost_breakdown → Langfuse auto-computes if model is in pricing table

    logger.info("devdocs-rag trace sent: trace_id=%s", t.trace_id)


# ---------------------------------------------------------------------------
# Trace 3: set_cost (deprecated) — backward-compat verification
# ---------------------------------------------------------------------------
def simulate_devcontext_mcp() -> None:
    """devcontext-mcp: uses deprecated set_cost(total) — expect DeprecationWarning in console."""
    logger.info("--- [Trace 3] devcontext-mcp: set_cost (deprecated path) ---")
    model = "claude-sonnet-4-6"

    with LLMTracer(
        project="devcontext-mcp",
        component="context-builder",
        model=model,
        tags={"env": "demo", "tool": "get_project_context"},
        metadata={"files_scanned": 43, "symbols_extracted": 212},
    ) as t:
        usage = fake_llm_call("low")
        t.set_tokens(prompt=usage["input_tokens"], completion=usage["output_tokens"])
        total = _input_cost(model, usage["input_tokens"]) + _output_cost(
            model, usage["output_tokens"]
        )
        t.set_cost(total)  # ← DeprecationWarning expected here

    logger.info("devcontext-mcp trace sent: trace_id=%s", t.trace_id)


def main() -> None:
    logger.info("=== LLMOps Dashboard — Phase 1 Dummy Demo (cost fix validation) ===")
    logger.info("Sending 3 traces to Langfuse (3 different cost reporting patterns)...")

    simulate_auto_sentinel()
    simulate_devdocs_rag()
    simulate_devcontext_mcp()

    logger.info("")
    logger.info("Done! Open http://localhost:3000 → Traces and verify:")
    logger.info("  Trace 1 (auto-sentinel):   input_cost + output_cost both visible")
    logger.info("  Trace 2 (devdocs-rag):     cost auto-computed from model pricing table")
    logger.info("  Trace 3 (devcontext-mcp):  total_cost only (no split)")


if __name__ == "__main__":
    main()
