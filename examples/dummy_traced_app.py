"""Phase 1 end-to-end demo.

Simulates LLM calls from 3 different portfolio projects without hitting real APIs.
Run this after `docker compose up -d` and you'll see 3 traces in the Langfuse UI.

Usage:
    cp .env.example .env
    # Edit .env with your Langfuse API keys from http://localhost:3000
    uv run python examples/dummy_traced_app.py
"""

from __future__ import annotations

import logging
import random
import time

from llmops_dashboard.instrumentation import LLMTracer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def fake_llm_call(model: str, prompt_complexity: str = "medium") -> dict[str, int]:
    """Simulate a real LLM API call with realistic latency and token counts."""
    latency_map = {"low": (0.1, 0.3), "medium": (0.5, 1.5), "high": (2.0, 4.0)}
    lo, hi = latency_map.get(prompt_complexity, (0.5, 1.5))
    time.sleep(random.uniform(lo, hi))

    return {
        "input_tokens": random.randint(200, 1500),
        "output_tokens": random.randint(100, 800),
    }


def cost_estimate(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough per-token cost estimates (USD per 1M tokens)."""
    pricing: dict[str, tuple[float, float]] = {
        "claude-opus-4-7": (15.0, 75.0),
        "claude-sonnet-4-6": (3.0, 15.0),
        "gpt-4o": (5.0, 15.0),
        "gemini-1.5-pro": (3.5, 10.5),
    }
    in_rate, out_rate = pricing.get(model, (5.0, 15.0))
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000


def simulate_auto_sentinel() -> None:
    """Simulate auto-sentinel's AI code review pipeline."""
    logger.info("--- Simulating auto-sentinel: diagnosis-agent ---")

    with LLMTracer(
        project="auto-sentinel",
        component="diagnosis-agent",
        model="claude-opus-4-7",
        tags={"env": "demo", "pr_number": "42", "repo": "acme/backend"},
        metadata={"trigger": "push", "diff_lines": 287},
    ) as t:
        usage = fake_llm_call("claude-opus-4-7", prompt_complexity="high")
        t.set_tokens(prompt=usage["input_tokens"], completion=usage["output_tokens"])
        t.set_cost(cost_estimate("claude-opus-4-7", usage["input_tokens"], usage["output_tokens"]))

    logger.info("auto-sentinel trace sent: trace_id=%s", t.trace_id)


def simulate_devdocs_rag() -> None:
    """Simulate devdocs-rag's retrieval-augmented generation pipeline."""
    logger.info("--- Simulating devdocs-rag: rag-retrieval-chain ---")

    with LLMTracer(
        project="devdocs-rag",
        component="rag-retrieval-chain",
        model="claude-sonnet-4-6",
        tags={"env": "demo", "query_type": "api-reference"},
        metadata={"retrieved_chunks": 5, "rerank_score": 0.87},
    ) as t:
        usage = fake_llm_call("claude-sonnet-4-6", prompt_complexity="medium")
        t.set_tokens(prompt=usage["input_tokens"], completion=usage["output_tokens"])
        t.set_cost(
            cost_estimate("claude-sonnet-4-6", usage["input_tokens"], usage["output_tokens"])
        )

    logger.info("devdocs-rag trace sent: trace_id=%s", t.trace_id)


def simulate_devcontext_mcp() -> None:
    """Simulate devcontext-mcp's context generation for Claude."""
    logger.info("--- Simulating devcontext-mcp: context-builder ---")

    with LLMTracer(
        project="devcontext-mcp",
        component="context-builder",
        model="claude-sonnet-4-6",
        tags={"env": "demo", "tool": "get_project_context"},
        metadata={"files_scanned": 43, "symbols_extracted": 212},
    ) as t:
        usage = fake_llm_call("claude-sonnet-4-6", prompt_complexity="low")
        t.set_tokens(prompt=usage["input_tokens"], completion=usage["output_tokens"])
        t.set_cost(
            cost_estimate("claude-sonnet-4-6", usage["input_tokens"], usage["output_tokens"])
        )

    logger.info("devcontext-mcp trace sent: trace_id=%s", t.trace_id)


def main() -> None:
    logger.info("=== LLMOps Dashboard — Phase 1 Dummy Demo ===")
    logger.info("Sending 3 traces to Langfuse...")

    simulate_auto_sentinel()
    simulate_devdocs_rag()
    simulate_devcontext_mcp()

    logger.info("")
    logger.info("Done! Open http://localhost:3000 and filter by tags:")
    logger.info("  project:auto-sentinel")
    logger.info("  project:devdocs-rag")
    logger.info("  project:devcontext-mcp")


if __name__ == "__main__":
    main()
