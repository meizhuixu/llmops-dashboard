# Architecture

## Diagram 1: Push-Based Trace Flow

```mermaid
graph TD
    subgraph Business Projects ["Business Projects (Producers)"]
        AS["Auto-Sentinel<br/>diagnosis-agent<br/>code-review-chain"]
        DR["DevDocs RAG<br/>rag-retrieval-chain<br/>embedding-service"]
        DM["DevContext MCP<br/>context-builder<br/>symbol-extractor"]
        FP["Future Project N<br/>any-component"]
    end

    subgraph Library ["instrumentation/ (shared library)"]
        LT["LLMTracer<br/>context manager"]
        SR["SpanRecord<br/>Pydantic V2 schema"]
        LC["LangfuseClient<br/>SDK wrapper"]
    end

    subgraph Backend ["Langfuse Backend (docker compose)"]
        LF["Langfuse Server<br/>:3000"]
        PG["PostgreSQL 16<br/>:5433"]
    end

    subgraph Dashboard ["Dashboard Layer (Phase 3)"]
        AL["alerting/<br/>YAML rules engine"]
        EV["eval/<br/>multi-model compare"]
        AB["ab_testing/<br/>prompt router"]
    end

    AS -->|"with LLMTracer(...) as t"| LT
    DR -->|"with LLMTracer(...) as t"| LT
    DM -->|"with LLMTracer(...) as t"| LT
    FP -->|"with LLMTracer(...) as t"| LT

    LT -->|"validates"| SR
    SR -->|"send()"| LC
    LC -->|"HTTP POST (push)"| LF
    LF -->|"persists"| PG

    PG -->|"read-only API"| AL
    PG -->|"read-only API"| EV
    PG -->|"read-only API"| AB

    style Business Projects fill:#e8f5e9,stroke:#2e7d32
    style Library fill:#e3f2fd,stroke:#1565c0
    style Backend fill:#fff3e0,stroke:#e65100
    style Dashboard fill:#fce4ec,stroke:#880e4f
```

**Key constraint**: The arrows from Business Projects flow only INTO the library and backend.
Dashboard reads Langfuse read-only. Business projects are NEVER called by the dashboard.

---

## Diagram 2: Phase Evolution Roadmap

```mermaid
timeline
    title LLMOps Dashboard — Phase Roadmap

    section Phase 1 (Current)
        Skeleton + CI : pyproject.toml + ruff + mypy + pytest
        LLMTracer library : SpanRecord schema, context manager, Langfuse client
        Docker Compose : Local Langfuse + Postgres
        End-to-end demo : dummy_traced_app.py — 3 traces in Langfuse UI

    section Phase 2 (Next)
        Auto-Sentinel : Wire LLMTracer into real LLM calls
        DevDocs RAG : Wire LLMTracer into retrieval + generation
        DevContext MCP : Wire LLMTracer into context building
        Real traces : Production data flowing to Langfuse

    section Phase 3 (Planned)
        Alerting engine : YAML rules → metric evaluation → Slack dispatch
        Multi-model eval : GPT-4o vs Claude Opus vs Sonnet vs Gemini
        A/B prompt testing : Version routing + comparative analysis
        Cost dashboard : Per-project spend tracking

    section Phase 4 (Optional Stretch)
        Terraform modules : networking/ + ecs/ + rds/ + alb/
        AWS deployment : ECS Fargate + RDS Postgres + ALB + ACM
        CI gate : terraform plan must pass — no terraform apply
```

---

## Diagram 3: LLMTracer Internal Flow

```mermaid
sequenceDiagram
    participant App as Business Project
    participant LT as LLMTracer
    participant SR as SpanRecord
    participant LC as LangfuseClient
    participant LF as Langfuse Backend

    App->>LT: with LLMTracer(project, component, model) as t
    LT->>LT: record start_time = perf_counter_ns()
    Note over LT: __enter__ returns self

    App->>App: response = llm_client.messages.create(...)
    App->>LT: t.set_tokens(prompt=N, completion=M)
    App->>LT: t.set_cost(0.015)

    Note over App,LT: with block exits

    LT->>LT: latency_ms = (now - start) / 1_000_000
    LT->>SR: SpanRecord.model_validate({...})
    SR-->>LT: validated record (or ValidationError)
    LT->>LC: client.send(record)
    LC->>LF: langfuse.trace(id=trace_id, name=...)
    LC->>LF: trace.generation(id=span_id, model=..., usage=...)
    LC->>LF: langfuse.flush()
    LF-->>LC: 200 OK
```

---

## Diagram 4: Alert Rule Lifecycle (Phase 3)

```mermaid
flowchart LR
    YAML["alerting/rules.yaml<br/>(declarative config)"]
    PARSE["load_rules()<br/>→ list[AlertRule]"]
    POLL["Metric Poller<br/>(Phase 3 background task)"]
    EVAL["AlertRule.evaluate(value)"]
    NOTIF{"Notifier<br/>type?"}
    SLACK["SlackNotifier<br/>.notify()"]
    EMAIL["EmailNotifier<br/>.notify()"]
    LOG["LogNotifier<br/>.notify()"]

    YAML -->|"pydantic parse"| PARSE
    PARSE -->|"on startup"| POLL
    POLL -->|"fetch metric from Langfuse API"| EVAL
    EVAL -->|"threshold breached"| NOTIF
    NOTIF -->|"slack"| SLACK
    NOTIF -->|"email"| EMAIL
    NOTIF -->|"log"| LOG

    style YAML fill:#f3e5f5,stroke:#6a1b9a
    style POLL fill:#fff9c4,stroke:#f9a825
    style SLACK fill:#e8eaf6,stroke:#283593
```

Phase 1 implements: YAML → PARSE (schema only). POLL → EVAL → NOTIF is Phase 3.
