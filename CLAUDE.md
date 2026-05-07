# READ THIS FIRST

This is the AI Native Portfolio capstone: a self-hosted LLM observability platform that unifies all LLM calls
from the previous 3 portfolio projects (auto-sentinel, devdocs-rag, devcontext-mcp) into Langfuse.

---

## CRITICAL DO/DON'T (Top 50 lines — read before touching anything)

### DO
- Use `uv` for all Python tooling (not pip, not poetry)
- Run `uv run ruff check . && uv run mypy src/` before every commit
- Keep `push-based` architecture: business projects call LLMTracer → Langfuse; dashboard never pulls from them
- Use Pydantic V2 model_validate / model_dump (NOT .dict() or .parse_obj())
- Add type hints to every function signature — mypy enforces this
- Tag every trace with `project` + `component` — this is how multi-tenancy works without schema changes
- Keep all alerting rules in `alerting/rules.yaml` (declarative) — never hardcode thresholds in Python
- Write tests for every AlertRule you add to rules.yaml
- Use `logging` (not `print`) everywhere inside `src/`
- Store secrets in `.env` (gitignored); expose via `pydantic-settings` Config class

### DON'T
- DON'T call `print()` inside `src/` — use `logging.getLogger(__name__)`
- DON'T break backward compatibility in SpanRecord: no field deletions, no type changes
- DON'T add required fields to SpanRecord — only `Optional` with defaults
- DON'T make dashboard pull data from business projects (pull model breaks multi-tenancy)
- DON'T write complete Terraform HCL in Phase 1 — terraform/ is a stub until Phase 4
- DON'T call real LLM APIs in tests or examples/dummy_traced_app.py
- DON'T commit .env, *.tfstate, or *.tfstate.backup (already gitignored)
- DON'T use .dict() or .parse_obj() — they're Pydantic V1 APIs
- DON'T hardcode LANGFUSE_HOST or API keys — always read from env/config
- DON'T skip the `tags` field on traces — filtering in Langfuse UI depends on it

---

## Project Overview

**Goal**: Self-hosted Langfuse as unified LLM observability platform, plus a reusable instrumentation
library (`LLMTracer`) that any project can plug into in < 5 minutes.

**Portfolio position**: Project 4 of 4 (capstone). Ingests telemetry from:
- `auto-sentinel` — AI-powered code review / security analysis
- `devdocs-rag` — RAG documentation assistant
- `devcontext-mcp` — MCP server providing dev context to Claude

---

## Architecture: Three Layers

```
Layer 1: instrumentation/   — pip-installable library (LLMTracer wrapper)
Layer 2: backend/           — local Langfuse + Postgres via docker compose
Layer 3: dashboard/         — alerting + eval + A/B testing (Phase 3)
```

### Push-based data flow (CRITICAL CONSTRAINT)

```
Business Project
  └─ calls LLMTracer context manager
       └─ on __exit__, sends SpanRecord → langfuse SDK → Langfuse backend
                                                         └─ Dashboard reads Langfuse API (read-only)
```

The dashboard NEVER makes outbound calls to business projects. This keeps the architecture clean and
avoids coupling.

---

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Current | Skeleton + LLMTracer library + docker compose + dummy demo + CI |
| 2 | 🔜 Next | Wire real LLM calls in auto-sentinel / devdocs-rag / devcontext-mcp |
| 3 | 📋 Planned | Alerting rules + multi-model eval + A/B prompt routing |
| 4 | 🔮 Optional | Terraform AWS deployment (stub only until then) |

---

## Repository Structure

```
llmops-dashboard/
├── pyproject.toml              # Dependencies + tool config
├── infra/
│   ├── docker-compose.langfuse.yml   # Local Langfuse + Postgres
│   └── terraform/                    # Phase 4 stub — DO NOT flesh out yet
├── .env.example                # Template for required env vars
├── .github/workflows/ci.yml    # ruff + mypy + pytest
├── src/llmops_dashboard/
│   ├── config.py               # pydantic-settings env config
│   ├── instrumentation/        # THE LIBRARY — what business projects import
│   │   ├── schema.py           # SpanRecord Pydantic V2 model
│   │   ├── tracer.py           # LLMTracer context manager
│   │   └── client.py           # Langfuse SDK wrapper
│   ├── eval/                   # Phase 3 (stub in Phase 1)
│   ├── alerting/               # Phase 3 (YAML rules + Pydantic schema)
│   └── ab_testing/             # Phase 3 (stub in Phase 1)
├── examples/
│   └── dummy_traced_app.py     # Phase 1 demo — simulates 3 projects, no real LLM
├── tests/
│   ├── test_smoke.py
│   ├── test_schema.py
│   └── test_alerting_rules.py
└── docs/
    ├── onboarding.md           # 5-step guide for new projects
    ├── runbook.md              # Incident response
    └── schema_versioning.md    # Schema evolution policy
```

---

## Trace Schema (SpanRecord) — Pydantic V2

Defined in `src/llmops_dashboard/instrumentation/schema.py`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trace_id | str | yes | UUID for the root trace |
| span_id | str | yes | UUID for this span |
| project | str | yes | Business project name (e.g. "auto-sentinel") |
| component | str | yes | Sub-component (e.g. "diagnosis-agent") |
| model | str | yes | Model identifier (e.g. "claude-opus-4-7") |
| prompt_tokens | int | yes | Input token count |
| completion_tokens | int | yes | Output token count |
| latency_ms | int | yes | Wall-clock latency in milliseconds |
| cost_usd | float | yes | Estimated cost in USD |
| tags | dict[str, str] | no | Arbitrary string tags for filtering |
| metadata | dict[str, Any] | no | Arbitrary metadata (JSON-serializable) |

### Schema Evolution Policy

- **ALLOWED**: Add new `Optional` field with a default value
- **FORBIDDEN**: Delete existing fields, change field types, rename fields
- See `docs/schema_versioning.md` for full versioning policy

---

## LLMTracer Usage Pattern

```python
from llmops_dashboard.instrumentation import LLMTracer

with LLMTracer(
    project="auto-sentinel",
    component="diagnosis-agent",
    model="claude-opus-4-7",
    tags={"env": "production", "version": "2.0"},
) as t:
    response = anthropic_client.messages.create(...)
    t.set_tokens(
        prompt=response.usage.input_tokens,
        completion=response.usage.output_tokens,
    )
    t.set_cost(0.015)
# On __exit__: latency_ms computed automatically, SpanRecord sent to Langfuse
```

---

## Environment Variables

All required vars are in `.env.example`. Copy to `.env` and fill in:

```
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
SLACK_WEBHOOK_URL=https://hooks.slack.com/...   # Phase 3
```

Get Langfuse keys from the local UI at http://localhost:3000 after `docker compose up -d`.

---

## Running Locally

### 1. Start Langfuse backend

```bash
docker compose -f infra/docker-compose.langfuse.yml up -d
# UI available at http://localhost:3000
# Default login: admin@example.com / password (change after first login)
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Run the dummy demo

```bash
cp .env.example .env
# Edit .env with your Langfuse API keys (from the local UI)
uv run python examples/dummy_traced_app.py
# Then open http://localhost:3000 and filter by project tag
```

### 4. Run CI checks

```bash
uv run ruff check .
uv run mypy src/
uv run pytest
```

---

## Alerting Rules (Phase 3 preview)

Rules live in `alerting/rules.yaml`. Schema is `AlertRule` (Pydantic V2).

```yaml
- name: high_latency
  metric: latency_ms
  operator: ">"
  threshold: 5000
  window_minutes: 5
  notifier: slack
  severity: warning
```

Rules are parsed at startup by `alerting/rules.py`. The actual triggering logic is Phase 3.

Every rule in rules.yaml **must** have a corresponding test in `tests/test_alerting_rules.py`.

---

## Connecting New Projects (Phase 2 workflow)

1. `uv add llmops-dashboard@file:///path/to/llmops-dashboard`
2. Set env vars (`LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`)
3. Wrap LLM calls with `LLMTracer`
4. Verify traces in Langfuse UI (filter by `project` tag)
5. (Optional) Add project-specific alert rules to `alerting/rules.yaml`

Full guide: `docs/onboarding.md`

---

## Terraform (Phase 4 — Optional Stretch)

`infra/terraform/` is a **stub placeholder** until Phase 4.

Phase 4 goal: provision Langfuse on AWS (ECS + RDS + ElastiCache) via Terraform.
`terraform plan` must pass. `terraform apply` is intentionally NOT run (cost control).

See `infra/terraform/README.md` for the planned module structure.

---

## CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`):

1. `uv run ruff check .` — linting
2. `uv run mypy src/` — type checking
3. `uv run pytest` — unit tests

No deploy step in Phase 1. Phase 2+ adds integration tests against local Langfuse.

---

## Key Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| Self-hosted Langfuse | No vendor lock-in, full data ownership, free for local dev |
| Push-based architecture | Decouples business projects from dashboard; avoids network dependencies |
| Pydantic V2 for schema | Type safety + serialization + validation in one; catches bugs at import time |
| YAML for alert rules | Declarative, version-controlled, non-engineers can modify thresholds |
| Tag-based multi-tenancy | Zero dashboard config when onboarding new projects |
| `uv` over pip/poetry | Faster, lockfile-based, modern Python packaging |

---

## Common Pitfalls

### Langfuse UI is blank after running dummy_traced_app.py
- Check `.env` has correct `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`
- Keys are project-scoped in Langfuse — make sure you're looking at the right project in the UI
- Run `docker compose logs langfuse` to see if traces are arriving

### mypy errors on Pydantic models
- Always use `from __future__ import annotations` at top of file
- Use `model_validate(data)` not `Model(**data)` when constructing from dicts

### SpanRecord validation fails
- All required fields must be set before LLMTracer exits
- Call `t.set_tokens()` and `t.set_cost()` inside the `with` block

### Docker compose port conflict
- Langfuse default port is 3000. If occupied, change `ports` in docker-compose.langfuse.yml
- Postgres is on 5432 (internal only)

---

## Contact / Ownership

Project: AI Native Portfolio — LLMOps Dashboard
Author: Meizhui Xu (xu.meiz@northeastern.edu)
Inspired by: Log alerting system built at Rankai.ai, evolved for LLM-native observability
