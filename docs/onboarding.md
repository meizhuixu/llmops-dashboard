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

## Cost Reporting

There are three ways to report cost, in order of preference:

### Option A — (Recommended) Let Langfuse auto-compute from Model Pricing table

Don't call any cost method. Langfuse will compute cost from its built-in model pricing table
if the model name matches exactly.

```python
with LLMTracer(project="my-project", component="my-agent", model="claude-sonnet-4-6") as t:
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": prompt}],
    )
    t.set_tokens(
        prompt=response.usage.input_tokens,
        completion=response.usage.output_tokens,
    )
    # No set_cost* call → Langfuse auto-computes
```

**Prerequisite**: configure the model in Langfuse UI. See "First-time Model Pricing Setup" below.

### Option B — set_cost_breakdown(input_cost, output_cost, currency=...)

Pass your own pricing. Langfuse shows separate **input cost** and **output cost** columns.

`currency` (default `"CNY"`) labels the figures. Langfuse v2 has no currency field on
cost, so it is recorded in generation metadata only — the numbers are sent as-is.
The Langfuse Models pricing table is configured in **USD**, so **do not mix currencies
within one Langfuse project** if you rely on aggregate cost totals.

```python
with LLMTracer(...) as t:
    response = client.messages.create(...)
    t.set_tokens(prompt=response.usage.input_tokens, completion=response.usage.output_tokens)
    t.set_cost_breakdown(
        input_cost=response.usage.input_tokens * 15.0 / 1_000_000,   # $15/M for opus
        output_cost=response.usage.output_tokens * 75.0 / 1_000_000, # $75/M for opus
        currency="USD",
    )
```

### Option C — set_cost(total_usd) — Deprecated

For backward compatibility only. Shows a single total cost; no input/output split in UI.
A `DeprecationWarning` is emitted at runtime.

```python
t.set_cost(0.015)  # DeprecationWarning: use set_cost_breakdown or omit
```

---

## First-time Model Pricing Setup (Langfuse UI)

To enable auto-computed costs (Option A), add your models to Langfuse:

1. Open http://localhost:3000 → **Settings** → **Models**
2. Click **+ Add model**
3. Add each model used by your project:

| Model name (exact) | Input price (per 1M tokens) | Output price (per 1M tokens) |
|--------------------|---------------------------|------------------------------|
| `claude-opus-4-7` | $15.00 | $75.00 |
| `claude-sonnet-4-6` | $3.00 | $15.00 |
| `gpt-4o` | $2.50 | $10.00 |
| `gemini-1.5-pro` | $3.50 | $10.50 |

> **Model name must match exactly** what you pass to `LLMTracer(model=...)`.

4. Click **Save** for each entry.

After adding, re-run `examples/dummy_traced_app.py` — Trace 2 (devdocs-rag) should now show
a non-zero cost in the Langfuse UI even though no cost was passed by the application.

---

## Schema Reference

All traces follow `SpanRecord` (defined in `src/llmops_dashboard/instrumentation/schema.py`):

| Field | Type | Default | Example |
|-------|------|---------|---------|
| `trace_id` | `str` | auto-generated | `"a3f1...bc04"` (32-char hex) |
| `span_id` | `str` | auto-generated | `"1d2e...9f0a"` (16-char hex) |
| `project` | `str` | required | `"auto-sentinel"` |
| `component` | `str` | required | `"diagnosis-agent"` |
| `model` | `str` | required | `"claude-opus-4-7"` |
| `prompt_tokens` | `int` | required | `450` |
| `completion_tokens` | `int` | required | `212` |
| `latency_ms` | `int` | auto-computed | `1847` |
| `cost_usd` | `float` | `0.0` | `0.0089` |
| `input_cost_usd` | `float \| None` | `None` | `0.0015` |
| `output_cost_usd` | `float \| None` | `None` | `0.0074` |
| `tags` | `dict[str, str]` | `{}` | `{"env": "prod"}` |
| `metadata` | `dict[str, Any]` | `{}` | `{"pr_number": "42"}` |

> **If validation fails**: ensure `t.set_tokens()` is called inside the `with` block.

## Streaming Calls (verified pattern)

For SSE/streaming LLM calls, `completion_tokens` is only known once the stream
closes. The supported pattern — verified against a real Volcano Ark streaming
call from devdocs-rag (2026-07-03) — is: consume the stream fully inside the
`with` block, then call `set_tokens()` / `set_cost_breakdown()` **after the
last chunk but before the block exits** (the span ships on `__exit__`):

```python
with LLMTracer(project=..., component=..., model=...) as t:
    stream = await client.chat.completions.create(
        ..., stream=True, stream_options={"include_usage": True}
    )
    async for chunk in stream:
        ...  # yield/collect content deltas; the final chunk carries .usage
    t.set_tokens(prompt=usage.prompt_tokens, completion=usage.completion_tokens)
    t.set_cost_breakdown(input_cost=..., output_cost=..., currency="CNY")
```

Notes:
- OpenAI-compatible gateways only send the usage chunk when
  `stream_options={"include_usage": True}` is set.
- Reasoning-capable models (e.g. doubao-seed-2.0) count hidden reasoning
  tokens in `completion_tokens`, so the count can exceed the visible output.

## Trace Ownership (trace_id gotcha)

Pass `trace_id` to `LLMTracer` **only when something else creates the parent
trace** (the multi-agent pattern — e.g. auto-sentinel's `open_parent_trace()`
at the pipeline entry). With an injected `trace_id` the tracer runs in
`owns_trace=False` mode and emits *only* a generation; if no parent trace
exists, ingestion still accepts it (HTTP 201) but the span is an **orphan** —
invisible in trace queries and the UI. For standalone single-call clients,
omit `trace_id` and let the tracer self-generate and own the trace.

## Versioning Policy

See [schema_versioning.md](schema_versioning.md) for the full schema evolution policy.

**TL;DR**: New fields can only be added as `Optional` with a default. No deletions, no type changes.

---

## Integration Checklist

- [ ] Dependency added to pyproject.toml
- [ ] `.env` has `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- [ ] At least one `LLMTracer` wraps an LLM call
- [ ] `t.set_tokens()` called inside the `with` block
- [ ] Cost method called (or model pricing configured in Langfuse UI for auto-compute)
- [ ] Trace visible in Langfuse UI (filter by `project:your-project`)
- [ ] (Optional) Alert rule added to `rules.yaml` with a test
