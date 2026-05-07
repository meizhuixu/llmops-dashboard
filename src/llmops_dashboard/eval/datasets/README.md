# Eval Datasets — Phase 3

This directory stores evaluation datasets for multi-model comparison runs.

## Format

Each dataset is a JSONL file where each line is a JSON object:

```json
{"id": "q1", "prompt": "Explain what a context manager is in Python", "expected": "..."}
{"id": "q2", "prompt": "Write a SQL query to find duplicate emails", "expected": "..."}
```

## Planned Datasets

| File | Purpose |
|------|---------|
| `code_review.jsonl` | Auto-Sentinel code review prompts |
| `rag_retrieval.jsonl` | DevDocs RAG retrieval quality |
| `mcp_context.jsonl` | DevContext MCP context generation |

Phase 3 will populate these datasets and run `MultiModelEval` against them.
