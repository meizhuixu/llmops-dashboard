# LLMOps Dashboard

**Self-hosted LLM observability for the AI Native Portfolio** — the capstone project that unifies
all LLM calls from [Auto-Sentinel](https://github.com/meizhuixu/auto-sentinel),
[DevDocs RAG](https://github.com/meizhuixu/devdocs-rag), and
[DevContext MCP](https://github.com/meizhuixu/devcontext-mcp) into a single Langfuse backend.

---

## Why This Exists

Three production-grade AI projects. Three separate LLM call stacks. No unified view of cost,
latency, or failure rates. This platform fixes that.

**Design principle**: Every AI system I build ships with observability from day one, not as an afterthought.

---

## Hero Features

| Feature | Status |
|---------|--------|
| Self-hosted Langfuse backend | ✅ Phase 1 |
| `LLMTracer` wrapper — < 5 min integration | ✅ Phase 1 |
| Pydantic V2 trace schema with validation | ✅ Phase 1 |
| Tag-based multi-tenancy (zero config) | ✅ Phase 1 |
| Multi-project trace aggregation | ✅ Phase 1 |
| Declarative YAML alert rules | ✅ Phase 1 (schema) |
| Alert triggering + Slack notifications | 🔜 Phase 3 |
| Multi-model eval (GPT-4o vs Claude vs Gemini) | 🔜 Phase 3 |
| Prompt A/B testing framework | 🔜 Phase 3 |
| Terraform AWS deployment | 🔮 Phase 4 (Optional) |

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │          Business Projects           │
                    │                                      │
  auto-sentinel ───►│  with LLMTracer(project=...) as t:  │
  devdocs-rag   ───►│      ...                            │
  devcontext-mcp───►│      t.set_tokens(...)              │
  future-project───►│      t.set_cost(...)                │
                    └────────────────┬────────────────────┘
                                     │ SpanRecord (Pydantic V2)
                                     │ PUSH (never pull)
                                     ▼
                    ┌─────────────────────────────────────┐
                    │         Langfuse Backend             │
                    │  (self-hosted docker compose)       │
                    │  + Postgres for persistence         │
                    └────────────────┬────────────────────┘
                                     │ read-only
                                     ▼
                    ┌─────────────────────────────────────┐
                    │           Dashboard Layer            │
                    │  alerting/ + eval/ + ab_testing/    │
                    │  (Phase 3)                          │
                    └─────────────────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed Mermaid diagrams.

---

## Quick Start

```bash
# 1. Start Langfuse backend
docker compose -f infra/docker-compose.langfuse.yml up -d

# 2. Install dependencies
uv sync

# 3. Configure (get keys from http://localhost:3000 after creating a project)
cp .env.example .env
# Edit .env with your Langfuse API keys

# 4. Run the end-to-end demo
uv run python examples/dummy_traced_app.py
# Open http://localhost:3000 → Traces → filter by project:auto-sentinel

# 5. Run CI checks
uv run ruff check . && uv run mypy src/ && uv run pytest
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Observability backend | [Langfuse](https://langfuse.com) (self-hosted, open-source) |
| Instrumentation | Python 3.11 + Pydantic V2 context manager |
| Database | PostgreSQL 16 |
| Container orchestration | Docker Compose (local), ECS Fargate (Phase 4) |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| Linting / typing | Ruff + mypy (strict) |
| Testing | pytest |
| IaC (Phase 4) | Terraform |
| Alerting (Phase 3) | Declarative YAML rules + Slack SDK |

---

## Onboarding a New Project

See [docs/onboarding.md](docs/onboarding.md) for the complete 5-step guide.

**TL;DR**:
```python
from llmops_dashboard.instrumentation import LLMTracer

with LLMTracer(project="my-project", component="my-agent", model="claude-sonnet-4-6") as t:
    response = client.messages.create(...)
    t.set_tokens(prompt=response.usage.input_tokens, completion=response.usage.output_tokens)
    t.set_cost(0.003)
```

---

## Version Compatibility Notes

| Component | Version | Why |
|-----------|---------|-----|
| Langfuse Server | `langfuse/langfuse:2` | v3 requires ClickHouse, which adds significant setup complexity for local dev |
| Langfuse Python SDK | `>=2.0.0,<3.0.0` | v4 SDK switched to OpenTelemetry/OTLP transport, incompatible with Server v2 REST API |

**This version pin is a deliberate trade-off**, not an oversight:

- **Langfuse v3 / SDK v4** introduced an OpenTelemetry-based architecture where the Python SDK exports via OTLP. This requires the server to have an OTLP endpoint (`/api/public/otel`), which only exists in Server v3+.
- **Server v3** requires ClickHouse in addition to Postgres, which turns a 2-container local setup into a 4+ container setup. The added complexity is not justified for Phase 1.
- **Trace ID format**: Even with the v2 SDK, trace IDs are generated as 32-character lowercase hex strings (`os.urandom(16).hex()`) — the OTel-compatible format. This makes future migration to the v3 stack drop-in compatible with no trace ID changes.

**Future migration path (tracked as Phase 4+ work)**:
1. Upgrade `infra/docker-compose.langfuse.yml` to add ClickHouse and Redis
2. Update server image to `langfuse/langfuse:latest`
3. Bump SDK constraint to `langfuse>=4.0.0`
4. Remove `<3.0.0` pin from `pyproject.toml`

No changes needed to `LLMTracer` or `SpanRecord` — the trace IDs and schema are already OTel-compatible.

---

## Story: From Rankai.ai to Here

At **Rankai.ai**, I built the company's log alerting system — a rule-based pipeline that monitored
application logs for anomalies, evaluated conditions against configurable thresholds, and dispatched
alerts to Slack when SLOs were breached. That system handled hundreds of events per second and became
the on-call team's primary early-warning tool.

The problem with LLMs is that traditional log monitoring misses the signals that matter most:
**token cost per request**, **prompt→completion latency**, **model degradation across versions**,
and **cost drift from prompt changes**. Log lines don't tell you that your Claude Opus bill just
spiked 3× because a PR doubled your average prompt length.

This platform is the direct evolution of that Rankai alerting system, rebuilt for the LLM era:

- **Same design philosophy**: declarative YAML rules, threshold-based evaluation, Slack dispatch
- **New primitives**: SpanRecord schema captures LLM-specific signals (tokens, cost, model)
- **New aggregation**: Langfuse gives a visual trace explorer that log systems never had
- **New scope**: multi-project observability across an entire AI portfolio, not a single app

The result is a system where adding observability to a new AI project takes **4 lines of code**,
and where the same alerting muscle from production log monitoring now catches LLM cost anomalies
before they hit the invoice.

---

## Project Status / Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Skeleton + LLMTracer library + docker compose + dummy demo + CI |
| **Phase 2** | 🔜 Next | Wire real LLM calls in auto-sentinel, devdocs-rag, devcontext-mcp |
| **Phase 3** | 📋 Planned | Alerting rule engine + Slack notifier + multi-model eval + A/B routing |
| **Phase 4** | 🔮 Optional | Terraform AWS deployment (ECS + RDS + ALB) — `terraform plan` only |

---

## Repository Structure

```
llmops-dashboard/
├── src/llmops_dashboard/
│   ├── instrumentation/    # LLMTracer + SpanRecord — the library
│   ├── alerting/           # YAML rules + Pydantic schema
│   ├── eval/               # Phase 3 stubs
│   └── ab_testing/         # Phase 3 stubs
├── infra/
│   ├── docker-compose.langfuse.yml
│   └── terraform/          # Phase 4 stub
├── examples/
│   └── dummy_traced_app.py # Phase 1 end-to-end demo
├── tests/
├── docs/
│   ├── onboarding.md
│   ├── runbook.md
│   └── schema_versioning.md
├── CLAUDE.md               # AI-assisted dev guide
└── ARCHITECTURE.md         # Mermaid diagrams
```

---

## Contributing

1. `uv sync` to install deps
2. `uv run ruff check . && uv run mypy src/ && uv run pytest` — all must pass
3. No `print()` in `src/` — use `logging`
4. Schema changes must follow [docs/schema_versioning.md](docs/schema_versioning.md)
5. Alert rules added to `rules.yaml` need tests in `tests/test_alerting_rules.py`
