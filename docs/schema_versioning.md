# Schema Versioning Policy

`SpanRecord` is a shared contract between all business projects and the LLMOps Dashboard.
Breaking changes silently drop data or cause runtime errors in all connected projects.

---

## Rules

### ALLOWED: Add optional fields with defaults

```python
# Before
class SpanRecord(BaseModel):
    trace_id: str
    ...

# After — backward compatible
class SpanRecord(BaseModel):
    trace_id: str
    ...
    environment: str | None = None          # new Optional field — safe
    request_id: str = Field(default="")     # new field with default — safe
```

**Why it's safe**: Existing callers don't set these fields, so they get the default.
Old serialized records still validate because the fields are optional.

### FORBIDDEN: Delete fields

```python
# NEVER do this — existing callers still send prompt_tokens
class SpanRecord(BaseModel):
    trace_id: str
    # prompt_tokens: int  <- deleted!  This breaks all existing senders
```

**Why it breaks**: Callers built against the old schema send the deleted field.
Langfuse records already in storage reference the old field.

### FORBIDDEN: Change field types

```python
# NEVER do this
class SpanRecord(BaseModel):
    latency_ms: float  # was int — existing callers send ints which coerce unpredictably
```

**Why it breaks**: Even if Pydantic coerces successfully, downstream queries
(e.g. alerting rules comparing `latency_ms > 5000`) may behave differently.

### FORBIDDEN: Rename fields

Renaming is equivalent to deleting the old field and adding a new required field.
Both sides break.

---

## Versioning Process

1. **Propose the change** in a PR with a description of why it's needed
2. **Get review** from at least one other contributor
3. **Update `docs/schema_versioning.md`** with what changed and in which version
4. **Add a migration note** if any downstream projects need to update their `set_*` calls
5. **Bump the minor version** in `pyproject.toml` (e.g. `0.1.0` → `0.2.0`)

---

## Change History

| Version | Date | Change |
|---------|------|--------|
| 0.1.0 | 2026-05-06 | Initial schema: trace_id, span_id, project, component, model, prompt_tokens, completion_tokens, latency_ms, cost_usd, tags, metadata |

---

## FAQ

**Q: What if I need to rename a field for clarity?**

Add the new name as an optional alias, keep the old name as primary. Once all callers migrate, consider deprecating (but keep in schema for at least 2 minor versions).

**Q: Can I add a required field?**

No — a required field without a default breaks all existing callers who don't set it.
If you truly need a required field, add it as `Optional[T] = None` first, migrate all callers, then promote it to required in a major version bump.

**Q: What counts as a major version?**

Any breaking schema change: field deletion, type change, rename, or new required field.
Major versions are avoided; the goal is full backward compatibility forever.
