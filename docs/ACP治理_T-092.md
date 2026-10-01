# ACP 权限、审计与用量（T-092）

## 1. 结论先行

1. ACP 权限请求落地为 `POST /api/v1/jobs/{job_id}/permission-request`：**企业策略或管理员确认**（需求书 §4.6.1 功能 4），判定顺序为「只读工具自动放行 → 写类工具需 `admin`/`owner` 确认 → 其余默认拒绝（fail closed）」。
2. 拒绝返回 403 且带结构化原因（`requires_admin_approval` / `policy.default_deny`），同时在审计中记为 `denied`；放行则记 `success`（`acp.permission.request`）。
3. ACP 会话进入**审计与用量**体系（功能 5）：任务创建写 `acp.job.start`，并写入任务级用量记录 `acp:<jobId>`（`source=adapter_estimate`，Token/成本留 `null`，真实值由 T-090 的 `usage` 钩子上报）。
4. 插件侧 `src/approval.ts` 提供**与控制面同形**的工具策略（客户端只做 UI 预判，最终裁决在控制面），并声明审批在企业 UI/控制面完成——官方未提供审批弹窗（§4.6.2 约束）。
5. 裁决：写类工具对 `admin`/`owner` 视为「管理员确认」并自动放行，而非要求二次弹窗 — 理由是官方无审批对话框、审批必须落在企业侧，且本阶段没有独立审批流（T-102 的审批模型用于插件安装）— 错判代价：管理员身份即隐式确认，若需要双人复核须引入独立审批流（已登记为后续项）。
6. 裁决：未知工具默认拒绝而不是放行 — 依据 §3.5 默认拒绝与最小权限 — 错判代价：新工具需显式加入策略表才能使用。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `services/api/app/routers/jobs.py` | 修改 | 权限请求端点 + 策略表 + 任务级用量记录 |
| `services/api/app/services/audit.py` | 修改 | 审计白名单补 `acp.permission.request` |
| `services/api/tests/test_acp_governance.py` | 新增 | 4 用例：策略三种判定、审计与用量、非成员拒绝审计、未知任务 404 |
| `plugins/acp/src/approval.ts` | 新增 | 工具策略（与控制面同形）+ 审批提示声明 |
| `plugins/acp/src/index.ts` | 修改 | 导出审批模块 |
| `plugins/acp/test/approval.test.ts` | 新增 | 3 用例：只读放行、写类需管理员、未知默认拒绝 |
| `scripts/verify_t092_acp_governance.py` | 新增 | 单任务门禁 |
| `docs/ACP治理_T-092.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 定向用例 | `pytest tests/test_acp_governance.py tests/test_jobs.py -q` = **9 passed** | 通过 |
| V-2 | 全量回归 | `pytest tests -q` = **87 passed** | 通过 |
| V-3 | 插件测试 | `vitest run` = **5 passed**；typecheck exit 0 | 通过 |
| V-4 | 单任务门禁 | `python scripts/verify_t092_acp_governance.py` = **6 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 `session/request_permission` 事件与企业策略的端到端联动（T-090 已实现策略前置，真机待复核）。
- B-2：GUI 审批提示的呈现位置与体验。
- B-3：真实 ACP 会话的 token 用量上报（当前控制面留空，真实值由适配层 `usage` 钩子提供）。

**需外部输入（C 类）**

- C-1：企业工具白名单/黑名单的最终口径（当前为三项只读 + 四项写类）。

**超出本次范围**

- O-1：不做双人复核/多级审批流（属 P6C 深度治理范围）。
- O-2：不使用 ACP 替换普通用户交互会话。

## 5. 复现命令

```powershell
cd "<repo-root>"
cd services/api; .venv\Scripts\python.exe -m pytest tests -q
cd ../..; pnpm --filter @worknexus/plugin-acp test
python scripts/verify_t092_acp_governance.py
```

## 6. 下一步

1. T-093：P6A 收尾门禁（§4.6.1 四项验收 + 禁用隔离 + §11 负向清单）。
