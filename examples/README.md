# Examples

## dummy_traced_app.py — Phase 1 End-to-End Demo

Simulates LLM calls from 3 portfolio projects without hitting real APIs.
Run this to verify your local Langfuse setup is working end-to-end.

### Prerequisites

1. Start Langfuse:
   ```bash
   docker compose -f infra/docker-compose.langfuse.yml up -d
   ```
2. Open http://localhost:3000 and create an account + project
3. Copy API keys from Settings → API Keys
4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
   ```

### Run the demo

```bash
uv run python examples/dummy_traced_app.py
```

Expected output:
```
2026-05-06 10:00:00 INFO     root — === LLMOps Dashboard — Phase 1 Dummy Demo ===
2026-05-06 10:00:00 INFO     root — Sending 3 traces to Langfuse...
2026-05-06 10:00:00 INFO     root — --- Simulating auto-sentinel: diagnosis-agent ---
2026-05-06 10:00:02 INFO     root — auto-sentinel trace sent: trace_id=<uuid>
...
2026-05-06 10:00:05 INFO     root — Done! Open http://localhost:3000 and filter by tags:
```

### Verify in Langfuse UI

1. Open http://localhost:3000
2. Go to **Traces**
3. Filter by tag: `project:auto-sentinel`, `project:devdocs-rag`, or `project:devcontext-mcp`
4. You should see 1 trace per project, each with latency, token counts, and cost

### What the demo simulates

| Project | Component | Model | Complexity |
|---------|-----------|-------|------------|
| auto-sentinel | diagnosis-agent | claude-opus-4-7 | high (2–4s latency) |
| devdocs-rag | rag-retrieval-chain | claude-sonnet-4-6 | medium (0.5–1.5s) |
| devcontext-mcp | context-builder | claude-sonnet-4-6 | low (0.1–0.3s) |
