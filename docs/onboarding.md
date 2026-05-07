# Onboarding a New Project to LLMOps Dashboard

Estimated time: **< 5 minutes** for a working trace in Langfuse.

---

## Prerequisites

- Langfuse running locally (or remotely): `docker compose -f infra/docker-compose.langfuse.yml up -d`
- A Langfuse API key pair (create in Settings → API Keys at http://localhost:3000)

---

## 5-Step Integration

### Step 1 — Add the dependency

```bash
# From your project root (assumes uv toolchain)
uv add llmops-dashboard@file:///path/to/llmops-dashboard

# Or install in editable mode during development
uv add --editable /path/to/llmops-dashboard
```

> **Note**: Once published to a private registry, replace with:
> `uv add llmops-dashboard`

### Step 2 — Set environment variables

Add to your project's `.env` (or export directly):

```bash
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-your-key-here
LANGFUSE_SECRET_KEY=sk-lf-your-key-here
```

The library reads these automatically via `pydantic-settings`. No code changes needed.

### Step 3 — Wrap your LLM calls

```python
from llmops_dashboard.instrumentation import LLMTracer

with LLMTracer(
    project="your-project-name",       # e.g. "auto-sentinel"
    component="your-component-name",   # e.g. "diagnosis-agent"
    model="claude-sonnet-4-6",         # exact model identifier
    tags={"env": "production"},        # optional — for filtering in UI
    metadata={"pr_number": "42"},      # optional — arbitrary context
) as t:
    # Your existing LLM call
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    # Report usage
    t.set_tokens(
        prompt=response.usage.input_tokens,
        completion=response.usage.output_tokens,
    )
    t.set_cost(0.003)  # estimated cost in USD
# Latency is measured automatically. SpanRecord sent to Langfuse on __exit__.
```

**That's the full integration.** The context manager handles timing, schema validation, and sending.

### Step 4 — Verify in Langfuse UI

1. Open http://localhost:3000
2. Navigate to **Traces**
3. Filter by tag: `project:your-project-name`
4. You should see your trace with latency, token counts, and cost

If no trace appears, check:
- `.env` has correct keys (not the example placeholders)
- Docker compose is running: `docker compose -f infra/docker-compose.langfuse.yml ps`
- Langfuse logs: `docker compose -f infra/docker-compose.langfuse.yml logs langfuse`

### Step 5 — (Optional) Add project-specific alert rules

Open `src/llmops_dashboard/alerting/rules.yaml` and add a rule scoped to your project:

```yaml
- name: your_project_high_latency
  metric: latency_ms
  operator: ">"
  threshold: 3000
  window_minutes: 5
  notifier: slack
  severity: warning
  project_filter: your-project-name
```

Then add a test in `tests/test_alerting_rules.py`:

```python
def test_your_project_high_latency_triggers() -> None:
    rule = _get_rule("your_project_high_latency")
    assert rule.evaluate(3001) is True
    assert rule.evaluate(3000) is False
```

Alert triggering logic is Phase 3 — your rule is ready to activate when that ships.

---

## Schema Reference

All traces follow `SpanRecord` (defined in `src/llmops_dashboard/instrumentation/schema.py`):

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `trace_id` | `str` | auto-generated | `"550e8400-e29b-41d4-a716-..."` |
| `span_id` | `str` | auto-generated | `"f47ac10b-58cc-4372-a567-..."` |
| `project` | `str` | yes | `"auto-sentinel"` |
| `component` | `str` | yes | `"diagnosis-agent"` |
| `model` | `str` | yes | `"claude-opus-4-7"` |
| `prompt_tokens` | `int` | yes (via `set_tokens`) | `450` |
| `completion_tokens` | `int` | yes (via `set_tokens`) | `212` |
| `latency_ms` | `int` | auto-computed | `1847` |
| `cost_usd` | `float` | yes (via `set_cost`) | `0.0089` |
| `tags` | `dict[str, str]` | no | `{"env": "prod"}` |
| `metadata` | `dict[str, Any]` | no | `{"pr_number": "42"}` |

> **If validation fails**: ensure you call `t.set_tokens()` and `t.set_cost()` inside the `with` block.

## Versioning Policy

See [schema_versioning.md](schema_versioning.md) for the full schema evolution policy.

**TL;DR**: New fields can only be added as `Optional` with a default. No deletions, no type changes.

---

## Integration Checklist

- [ ] Dependency added to pyproject.toml
- [ ] `.env` has `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- [ ] At least one `LLMTracer` wraps an LLM call
- [ ] `t.set_tokens()` called inside the `with` block
- [ ] `t.set_cost()` called inside the `with` block
- [ ] Trace visible in Langfuse UI (filter by `project:your-project`)
- [ ] (Optional) Alert rule added to `rules.yaml` with a test
