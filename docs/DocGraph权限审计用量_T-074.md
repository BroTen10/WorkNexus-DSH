# DocGraph 权限、审计与用量（T-074）

## 1. 结论先行

1. 权限（P4-F06）：提交/查看/取消统一走 `require_space_action()` / `require_job_access()`——必须是空间成员且拥有对应动作（`docgraph.submit` / `docgraph.read`），否则 404 并写 `denied` 审计。
2. 审计（P4-F07）：`docgraph.submit`（T-071）、`docgraph.view`（新增 `GET /jobs/{job_id}`）、`docgraph.cancel`（新增 `POST /jobs/{job_id}/cancel`）三类事件全部落审计；读取动作在审计里按 §6.2 归口为 `docgraph.view`（不做第二套审计通道）。
3. 用量（P4-F08）：提交任务时同步写入任务级用量记录 `usage_id=docgraph:<jobId>`，`source=adapter_estimate`，`prompt/completion/total tokens` 与 `estimated_cost` **留 `null`**——因为 DocGraph 没有用量端点，不填假数（总览 §2.1 第 15 条）。
4. 取消语义诚实：DocGraph 无取消端点（T-009），`cancel` 只标记**平台侧**任务状态，并在响应中显式返回 `remoteSupported: false` 与 `docgraph-unsupported` 说明。
5. `packages/host-core/src/docgraph-audit.ts` 提供审计事件与用量记录的纯函数构造（`ent` 前缀承载远端标识），供客户端/控制面共用同一形状。
6. 裁决：权限动作到审计动作做显式映射（`docgraph.read → docgraph.view`）— 理由是审计白名单按 §6.2 只列提交/查看/取消，不应把权限枚举当作审计枚举 — 错判代价：若后续新增 `docgraph.*` 权限动作，必须同步映射，否则会退化为按 `docgraph.view` 记账。
7. 裁决：平台侧取消不伪装成远端取消，也不重复入账 — 错判代价：远端任务仍在运行，运维需在 DocGraph 侧人工处置（已登记为 B/C 类）。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `services/api/app/routers/docgraph.py` | 修改 | 新增 `GET /jobs/{id}`、`POST /jobs/{id}/cancel`、提交时写用量记录、审计动作映射 |
| `services/api/app/services/audit.py` | 修改 | 审计白名单补 `docgraph.view` / `docgraph.result` |
| `packages/host-core/src/docgraph-audit.ts` | 新增 | 审计事件与用量记录纯函数 |
| `packages/host-core/src/index.ts` | 修改 | 导出审计辅助 |
| `packages/host-core/test/docgraph-audit.test.ts` | 新增 | 3 用例：四动作、ent 前缀字段、拒绝与空字段不猜 |
| `services/api/tests/test_docgraph_audit_usage.py` | 新增 | 4 用例：三类审计、任务级用量、非成员拒绝审计、未知任务 404 |
| `scripts/verify_t074_docgraph_audit_usage.py` | 新增 | 单任务门禁 |
| `docs/DocGraph权限审计用量_T-074.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 定向用例 | `pytest tests/test_docgraph_audit_usage.py tests/test_docgraph_submit.py -q` = **9 passed** | 通过 |
| V-2 | 全量回归 | `pytest tests -q` = **78 passed** | 通过 |
| V-3 | host-core | `vitest run` = **23 passed**；typecheck exit 0 | 通过 |
| V-4 | 单任务门禁 | `python scripts/verify_t074_docgraph_audit_usage.py` = **6 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 DocGraph 是否会返回用量/计费字段（T-009 判定为无）。
- B-2：远端任务在「平台侧取消」后的实际运行状态（需运维在 DocGraph 侧观察）。
- B-3：GUI 中权限拒绝的提示体验。

**需外部输入（C 类）**

- C-1：DocGraph 现网地址、网关鉴权与真实合同/文档数据。

**超出本次范围**

- O-1：不做 DocGraph 侧人工闭环（`PATCH /reviews/results/{id}/status`）的代理。
- O-2：不做用量成本模型（无单价来源，`estimated_cost` 留空）。

## 5. 复现命令

```powershell
cd "<repo-root>"
cd services/api; .venv\Scripts\python.exe -m pytest tests -q
cd ../..; pnpm --filter @worknexus/host-core test
python scripts/verify_t074_docgraph_audit_usage.py
```

## 6. 下一步

1. T-075：Agent 会话联动（结果引用/总结，只调用官方支持的能力）。
