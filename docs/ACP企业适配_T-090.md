# 复用官方 ACP 的企业适配（T-090）

## 1. 结论先行

1. `packages/kernel-dsh/src/acp-transport.ts` 交付 `createAcpTransport()`：在**官方 ACP 之上**做企业侧适配，实现需求书 §6.4 的 `AgentTransport` 最小接口。
2. **Step 0 取证结论（本次实测）**：官方 ACP 服务器由 `pnpm dsh --profile acp` 启动（`@deepseek-ai/dsh-acp`，stdio JSON-RPC 的 ACP v1）；官方仓库内已有客户端 `@deepseek-ai/dsh-subagent-acp`，因此**复用官方客户端能力面而非重新解析协议**。
3. 能力面（官方公布）：`session/new`、`session/list`、`session/resume`、`session/close`、`session/set_config_option`、`session/prompt`、`session/cancel`、`session/update`、`session/request_permission`。
4. 官方**不支持**：`session/load`、删除、fork、转录回放、附加目录、SSE、终端的客户端文件系统操作与 elicitation —— 这些都通过 `requestUnsupportedCapability()` 显式返回 `unsupported`，不发请求、不伪装（§6.4 第 4 条）。
5. 企业侧职责仅四项：任务与用户/空间/插件关联（`enterprise` 句柄）、权限策略前置（`policy.canRunTool`）、审计与用量上报（`audit` / `usage` 钩子）、异常映射（进程/协议异常 → 任务失败事件 + `acp.job.failed` 审计，**不静默丢失**）。
6. 只用于后台自动化：不接管交互主链路（§4.6.1 第 6 条）；企业审计钩子抛错不影响任务链路（与 T-032 同口径）。
7. 裁决：`AgentTransport` 采用**注入式客户端端口**（`AcpClientPort`）而非直接依赖上游 workspace 包 — 理由是上游包在本仓库不可安装（workspace 内部依赖），且 P1 明确「不实现本接口」，适配层必须可替换 — 错判代价：真机联调时需要把 `dsh-subagent-acp` 的真实客户端适配到该端口（登记为 B 类）。
8. 裁决：契约测试辅助文件命名为 `test/transport.contract.ts`（派发卡写的是 `transport.contract.test.js`）— 理由是 vitest 会把 `*.test.*` 当测试文件收集，导出型辅助文件会被判「无测试」而失败 — 错判代价：与派发卡文件名不一致，已在门禁与本文档登记。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `packages/kernel-dsh/src/acp-transport.ts` | 新增 | `AgentTransport` 实现 + 企业适配 + 不支持能力显式拒绝 |
| `packages/kernel-dsh/test/transport.contract.ts` | 新增 | 可复用的 `AgentTransport` 契约测试辅助 |
| `packages/kernel-dsh/test/fake-acp-client.ts` | 新增 | 官方 ACP 客户端桩（只含官方公布能力面） |
| `packages/kernel-dsh/test/acp-transport.test.ts` | 新增 | 8 用例：契约 3 项 + 审计/用量、异常映射、策略拒绝、不支持能力、审计失败隔离 |
| `scripts/verify_t090_acp_transport.py` | 新增 | 单任务门禁 |
| `docs/ACP企业适配_T-090.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件（`repos/deepseek-harness` 仅读取取证），差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | kernel-dsh 测试 | `vitest run` = **11 passed**（acp-transport 8） | 通过 |
| V-2 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-3 | 单任务门禁 | `python scripts/verify_t090_acp_transport.py` = **6 [OK] / 0 [FAIL]** | 通过 |
| V-4 | 上游零改动 | 仅读取 `repos/deepseek-harness/packages/acp` 与 `subagent/subagent-acp` 取证 | 通过（静态证据） |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 `pnpm dsh --profile acp` 服务器 + 官方客户端 `dsh-subagent-acp` 的端到端联调（本次用注入式桩验证适配层语义）。
- B-2：进程异常退出（崩溃/被杀）时的真实失败上报与任务状态收敛。
- B-3：真实 `session/request_permission` 流程与企业策略的对接。

**需外部输入（C 类）**

- C-1：企业侧模型/推理强度默认策略与 MCP 服务器清单。

**超出本次范围**

- O-1：不自研 JSON-RPC 传输层、不复刻 ACP 协议、不实现第二套会话机制（§8、§11.1/11.2）。
- O-2：不用 ACP 替换普通用户的交互会话（§4.6.1 第 6 条）。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm --filter @worknexus/kernel-dsh test
python scripts/verify_t090_acp_transport.py
```

## 6. 下一步

1. T-091：后台任务管理（`/api/v1/jobs` 创建/列表/取消/恢复/关闭 + 审计）。
