# Technical Debt Register

Technical debt items for the LLMOps Dashboard (Project 4 capstone). `[ ]` = open, `[X]` = resolved.

When code changes surface a new debt item, Claude Code adds an entry inline. When an item is resolved, mark it `[X]` in the same commit that lands the fix — keep the entry (with its commit ref), do not delete it. Format is kept consistent with `auto-sentinel/DEBT.md`.

Debt here is anchored to the phase roadmap in `CLAUDE.md` (Phase 1 skeleton → Phase 2 wire real projects → Phase 3 alerting/eval → Phase 4 Terraform/AWS) rather than to sprints.

---

## Cross-Phase Debt (infra / migration layer)

- [ ] **Phase 4 — Postgres credentials hardcoded**: the Langfuse backend Postgres credentials are inlined in `infra/docker-compose.langfuse.yml`. Fine for local single-developer dev, but unacceptable once the stack moves to AWS. **何时修 (Phase 4)**: when the Terraform ECS + RDS deployment lands, source the DB credentials from AWS Secrets Manager (or SSM Parameter Store) and inject them as task-definition secrets — never bake them into the compose file or any committed config. Until Phase 4 starts, `infra/terraform/` stays a stub (per `CLAUDE.md`), so this is parked, not actionable yet.

- [ ] **Langfuse v3 migration — drop the `langfuse-setup` shim**: the local stack carries a `langfuse-setup` helper service to work around a Langfuse **v2.95 user↔project membership bug** (fresh installs do not reliably grant the bootstrap user project membership, leaving the UI unable to show traces). It is a band-aid pinned to the v2 line. **何时修 (Langfuse v3 migration)**: when the backend is upgraded to Langfuse v3, delete the `langfuse-setup` service entirely and verify bootstrap membership is created natively — do not carry the shim forward. Tracked here so the upgrade does not silently inherit dead workaround code.

---

## Instrumentation / Schema Debt

- [X] **Cost fields rendered as $0.00 in Langfuse**: costs were being passed through generation `metadata` instead of the Langfuse v2 SDK's `ModelUsage` TypedDict on the generation, so the UI showed `$0.00` for every trace despite costs being computed. The Langfuse v2 SDK only reads cost off `ModelUsage` (`input_cost` / `output_cost` / `total_cost`), not from arbitrary metadata. **Resolved** in commit `6059ad1` (2026-05-07): cost is now sent via the generation's `ModelUsage` object, and `set_cost_breakdown()` was introduced as the supported API (with `set_cost()` deprecated). Entry retained per the resolved-item policy.

- [ ] **`SpanRecord.input_cost_usd` / `output_cost_usd` are a currency misnomer**: the `_usd` suffix is baked into the field names, but `set_cost_breakdown(currency="CNY")` (the Ark/GLM default) stores non-USD figures in those same fields. The names are kept because schema renames are forbidden by the evolution policy (`docs/schema_versioning.md`, `CLAUDE.md`). The deeper hazard: Langfuse v2 `ModelUsage` has **no currency slot**, so cross-currency aggregation within one Langfuse project (CNY + USD summed) is meaningless. **Current mitigation (not a fix)**: the actual currency is carried on the `cost_currency` field and surfaced via generation metadata, tenants are separated by `project` tag, and `CLAUDE.md` already documents a "do not mix currencies within a single Langfuse project" warning. **何时修 (Phase 2 anchor; deferred)**: a true rename to currency-neutral field names (e.g. `input_cost` / `output_cost` + first-class currency) is a **breaking schema migration**, so it is intentionally not done now. This entry is the Phase 2 anchor — revisit when real multi-currency traffic from auto-sentinel (CNY) and Anthropic-billed projects (USD) lands in the same backend and forces the decision.

---

## Phase 2 Integration Anchors

- [ ] **Streaming token counts unverified**: `LLMTracer` requires `completion_tokens` to be known at `set_tokens()` time, but DevDocs RAG (Project 2, Phase 6) serves responses over SSE streaming, where the completion token count is only available **after** the stream closes. The current contract — set tokens before the `with` block exits — has not been exercised against a real streaming call, so the "set tokens after stream completes, before exit" pattern is unproven. **何时修 (Phase 2)**: when wiring DevDocs RAG's streaming calls, confirm the post-stream `set_tokens()` path produces correct `completion_tokens` and latency, and document the streaming usage pattern in `docs/onboarding.md` if it differs from the non-streaming flow.

- [X] **`set_cost_breakdown()` signature alignment with auto-sentinel** *(historical fact, not an open todo)*: the API is now `set_cost_breakdown(*, input_cost: float, output_cost: float, currency: str = "CNY")` — keyword-only, defaulting to CNY for Ark/GLM billing. This matches auto-sentinel's `005-pr5` cost-currency convention, so the cross-repo signature is **already aligned**; no synchronization work remains. Recorded here only so the Phase 2 auto-sentinel integration starts from a confirmed-consistent baseline (landed via commit `ad0d655`).
