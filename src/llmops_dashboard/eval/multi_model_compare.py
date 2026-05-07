"""Multi-model comparison eval — Phase 3 implementation.

Compares outputs and costs across GPT-4o, Claude Opus, Claude Sonnet, and Gemini
for the same prompt inputs. Results are tracked in Langfuse for side-by-side analysis.
"""

from __future__ import annotations

from typing import Any


class MultiModelEval:
    """Run the same prompt against multiple models and record results to Langfuse."""

    def run(
        self,
        prompt: str,
        models: list[str],
        dataset_name: str,
    ) -> dict[str, Any]:
        raise NotImplementedError("MultiModelEval is Phase 3 — not yet implemented")

    def compare(self, run_id: str) -> dict[str, Any]:
        raise NotImplementedError("MultiModelEval is Phase 3 — not yet implemented")
