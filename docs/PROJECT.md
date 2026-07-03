# LLMOps Dashboard — Project Context & Status

> 项目上下文 + 进度快照。**维护规则：每次代码 PR 落地，顺手更新「当前状态」段和涉及的决策段。**
> 权威进度以 `git log` / `DEBT.md` / CLAUDE.md 的 Phase roadmap 为准，本文件是快照 + 上下文入口。
> 矩阵全局上下文见 `~/Repo/PORTFOLIO.md`（本地文件，不入库）。

---

## 当前状态（快照 2026-07-03）

- ✅ Phase 1 完成 + 增量演进已合并：PR #1 trace_id 外部注入（PR-0）、PR #2
  `set_cost_breakdown` currency 对齐 auto-sentinel、PR #3 DEBT.md、PR #4 currency-display
  findings、PR #5 非 USD project currency registry。main 与远端同步（2026-07-03 本地已 sync）。
- ✅ **Phase 2 · auto-sentinel + devdocs-rag 双双实测通过（2026-07-03）**：auto-sentinel
  真实 incident 单父 4-generation trace 树 + devdocs-rag SSE 流式 trace（tokens 621+383、
  cost ¥0.0081 精确对账）均落库；streaming token 债清掉，trace-ownership 坑（注入 trace_id
  无父 trace = 孤儿 generation）写进 onboarding。剩余：devcontext-mcp（另一会话推进中）。
- ✅ **Phase 3 · Alerting engine 上线（2026-07-03）**：`alerting/engine.py` 补齐触发逻辑——
  Langfuse public API 窗口拉取（observations + trace tags 两次列表调用内存 join）→ 逐 span
  规则评估（project_filter / 窗口过滤）→ notifier 派发（Slack webhook 实现，未配置回落 log）。
  `python -m llmops_dashboard.alerting` 一把跑。真实数据验证：6h 窗口回放里 `zero_tokens`
  规则精确命中当天那条客户端断连的 0-token span，零误报。flush-retry 债查实为伪命题
  （SDK 内建指数退避），已按实情销账。Phase 3 剩余（可选）：multi-model eval、A/B routing。
- ❌ **Phase 4 已砍**（2026-07-03 决策）：Terraform/AWS 不做，`infra/terraform/` 维持 stub，
  DEBT 里 Postgres 凭据条目长期 parked。
- 开放技术债见 `DEBT.md`（Postgres 凭据硬编码→Phase 4、langfuse-setup shim→v3 迁移时删、
  `_usd` 字段 misnomer→Phase 2 锚点、streaming token counts 未验证→接 devdocs-rag 时）。

---

## 项目是什么

自托管 LLM observability 平台：项目 1/2/3 产生的所有 LLM 调用统一收口到自建 Langfuse 实例，
集中监控 token / cost / latency / trace 树。业务项目用自研 `LLMTracer` 库主动 push 上报
（dashboard 从不拉取），新项目接入成本 O(1)。这是 portfolio 的 dogfooding 收口层。

## 三层架构

| 层 | 模块 |
|----|------|
| Instrumentation（业务项目消费） | `src/llmops_dashboard/instrumentation/{schema,tracer,client}.py` |
| Backend（存储与查询） | `infra/docker-compose.langfuse.yml`（Langfuse v2 + Postgres） |
| Dashboard（告警 + eval + A/B） | `alerting/` `eval/` `ab_testing/` |

## 关键设计与决策

- **Push 模式**：业务项目调 LLMTracer 上报；dashboard 不拉（pull 破坏 multi-tenancy）。
- **LLMTracer 用法**：
  ```python
  with LLMTracer(project=..., component=..., model=..., trace_id=...) as t:
      response = client.complete(...)
      t.set_tokens(prompt=..., completion=...)
      t.set_cost_breakdown(input_cost=..., output_cost=..., currency="CNY")
  ```
- **Tag-based multi-tenancy**：每条 trace 必带 `project:<name>` + `component:<name>`。
- **trace_id 外部注入（PR-0）**：32-char lowercase hex（OTel 兼容），业务项目在入口自生成后
  透传进来，LLMTracer 不自生成。与 auto-sentinel 的 trace_id == job_id 约定配套。
- **原生货币计量**：`set_cost_breakdown(*, input_cost, output_cost, currency="CNY")`
  keyword-only；cost 按模型计费货币原生记账，零汇率换算。与 auto-sentinel 005-pr5 约定一致，
  两仓签名已对齐。
- **Langfuse v2 ModelUsage 无 currency 槽（已知限制）**：cost 必须经 `ModelUsage` 传
  （塞 metadata 会显示 $0.00），但它没有 currency 字段 → 单一 Langfuse project 内跨币种聚合
  数值无意义。规避：`cost_currency` 字段 + metadata 透出 + project tag 隔离 +
  "勿在单一 project 内混币种" 告警。`SpanRecord` 的 `_usd` 后缀 misnomer 是 Phase 2 锚点
  （见 DEBT.md），破坏性 schema 迁移故意不做。
- **Forward-compatibility**：用 Langfuse v2（Postgres only），不用 v3（需 ClickHouse + Redis）。
  deliberate trade-off；v3 迁移时要删掉 `langfuse-setup` shim（见 DEBT.md）。

## 技术栈

Langfuse v2.95（self-hosted）/ PostgreSQL 16 / Python 3.11 + context manager /
Pydantic v2 + pydantic-settings / langfuse SDK v2.60 / Docker Compose / pytest /
GitHub Actions / uv

## Phase roadmap 与跨项目接入顺序

Phase 1 skeleton ✅ → **Phase 2 wire real projects**（auto-sentinel 先行，严格串行：
项目 1 → 项目 2 Phase 6 → 项目 3 Phase 2，不并行）→ Phase 3 alerting/eval →
Phase 4 Terraform/AWS。

Phase 2 auto-sentinel 接入第一步：5 个 LLM agent 的调用各加 LLMTracer wrap →
Langfuse UI 验证 tag 分组、cost 非 0、单父 trace 树。
