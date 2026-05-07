# Runbook — LLMOps Dashboard Incident Response

## Langfuse UI is not reachable (http://localhost:3000)

**Check**: Is the container running?
```bash
docker compose -f infra/docker-compose.langfuse.yml ps
```

**Fix — containers stopped**:
```bash
docker compose -f infra/docker-compose.langfuse.yml up -d
```

**Fix — port 3000 conflict**:
Change the host port in `docker-compose.langfuse.yml`:
```yaml
ports:
  - "3001:3000"   # use 3001 instead
```
Then update `LANGFUSE_HOST=http://localhost:3001` in `.env`.

**Fix — Postgres unhealthy**:
```bash
docker compose -f infra/docker-compose.langfuse.yml logs postgres
docker compose -f infra/docker-compose.langfuse.yml restart postgres
```

---

## Traces not appearing in Langfuse UI after running dummy_traced_app.py

**Step 1** — Confirm containers are healthy:
```bash
docker compose -f infra/docker-compose.langfuse.yml ps
# Both langfuse and langfuse-postgres should be "running"
```

**Step 2** — Confirm `.env` is set:
```bash
cat .env | grep LANGFUSE
# Should show real key values, not the example placeholders
```

**Step 3** — Check Langfuse logs for incoming requests:
```bash
docker compose -f infra/docker-compose.langfuse.yml logs langfuse --tail 50
```

**Step 4** — Re-run the demo with debug logging:
```bash
LANGFUSE_DEBUG=1 uv run python examples/dummy_traced_app.py
```

**Step 5** — Check the API keys are for the correct Langfuse project:
- Langfuse keys are project-scoped
- In the UI: Settings → API Keys — confirm the project matches

---

## mypy or ruff failures in CI

**Ruff lint failure**:
```bash
uv run ruff check . --fix   # auto-fix safe issues
uv run ruff format .         # fix formatting
```

**mypy strict failure**:
- Add missing type hints to function signatures
- For third-party libraries without stubs: add to `[[tool.mypy.overrides]]` with `ignore_missing_imports = true`
- Never use `# type: ignore` without a comment explaining why

---

## SpanRecord validation errors

```
pydantic.ValidationError: 1 validation error for SpanRecord
  prompt_tokens: Input should be a valid integer
```

**Fix**: Ensure `t.set_tokens()` is called inside the `with` block:
```python
with LLMTracer(...) as t:
    response = client.messages.create(...)
    t.set_tokens(prompt=response.usage.input_tokens, ...)  # <- must be inside
```

---

## Alert rule tests failing

If a new rule was added to `rules.yaml` without a matching test:
1. Add a test class in `tests/test_alerting_rules.py` (see existing examples)
2. Test `evaluate()` for values above, at, and below the threshold

---

## Docker Postgres data loss after `docker compose down`

Named volume `langfuse_postgres_data` persists data across restarts.
Only `docker compose down -v` removes the volume (data loss).

**To reset local state intentionally**:
```bash
docker compose -f infra/docker-compose.langfuse.yml down -v
docker compose -f infra/docker-compose.langfuse.yml up -d
# Re-create Langfuse account and API keys
```

---

## Phase 3 alerting not firing (future)

Once Phase 3 is implemented, check:
1. Rules are loading: enable `DEBUG` logging and look for "Loaded N alert rules"
2. Metric polling is running (check background task status)
3. Notifier credentials are set in `.env` (`SLACK_WEBHOOK_URL`, etc.)
