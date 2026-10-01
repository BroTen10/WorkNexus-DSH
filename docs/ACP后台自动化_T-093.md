# P6A ACP 后台自动化收尾（T-093）

## 1. 结论先行

1. 批次 7（T-090~T-093）已全部实现并提交；`verify_t093_p6a.py` 汇总 3 个子门禁、Python/TypeScript 全量回归、控制面端到端与隔离核查，结果 **11 [OK] / 0 [FAIL]**。
2. 交付面：`AgentTransport` 企业适配层（复用官方 ACP 客户端能力面）、后台任务管理（创建/查看/取消/恢复/关闭）、权限请求策略、审计与用量。
3. 官方事实已实测取证：服务器 `pnpm dsh --profile acp`、官方客户端 `@deepseek-ai/dsh-subagent-acp`、ACP v1 能力面与不支持清单（删除/fork/转录回放/附加目录）。
4. 诚实边界：远端不支持的能力显式返回 `acp-unsupported`；平台侧「关闭」是新终态（迁移 0005），不等于取消；真实 ACP 联调（真实服务器+客户端、真实进程退出、真实 permission 事件）为 B 类。
5. **ACP 未用于替换普通用户的交互会话**（§4.6.1 第 6 条）：控制面不代理运行时，插件声明 `backgroundOnly`，主链路零依赖（负向扫描通过）。
6. 裁决：批次 7 自动化退出条件成立；真机联调与 GUI 审批提示登记 B/C 类，**不宣称批次 7 真机全绿**。

## 2. §4.6.1 六项功能与四条验收

| 编号 | 要求 / 验收 | 证据 | 判定 |
| --- | --- | --- | --- |
| 功能 1 | `AcpTransport` 实现 `AgentTransport` 契约 | `docs/ACP企业适配_T-090.md`；契约测试 3 项 + 5 项企业适配用例 | 通过（协议层复用官方） |
| 功能 2 | 后台任务创建、状态查询、取消、恢复、关闭 | `docs/后台任务管理_T-091.md`；端到端创建/查看/取消/恢复/关闭 | 通过 |
| 功能 3 | 任务与用户、空间、插件关联 | `test_jobs.py` 断言 `userId` / `spaceId` / `pluginId` | 通过 |
| 功能 4 | 所有 ACP 权限请求必须有企业侧策略或管理员确认 | `docs/ACP治理_T-092.md`；三判定 + 403 结构化原因 + denied 审计 | 通过 |
| 功能 5 | ACP 会话必须进入审计与用量体系 | `acp.job.*` / `acp.permission.request` 审计 + 任务级用量（Token 留空） | 通过 |
| 功能 6 | ACP 不用于替换普通用户的交互会话 | 控制面无运行时代理；插件 `backgroundOnly`；负向扫描无主链路引用 | 通过 |
| 验收 1 | 至少一个后台自动化任务可通过 ACP 完成 | 任务创建→队列→（真机）执行的链路已交付；真实 ACP 执行 B 类 | 自动化口径通过 |
| 验收 2 | 任务可从后台列表查看和取消 | 端到端 `GET /jobs`、`POST /jobs/{id}/cancel` | 通过 |
| 验收 3 | 会话恢复、关闭、取消行为符合预期 | `resume` 回队列并累加次数、`close` 幂等且为终态、`closed` 不可恢复（409） | 通过 |
| 验收 4 | ACP 插件禁用后 P1~P5 不受影响 | 端到端真实调用 P2/P3 接口仍 200；全量回归 87 passed；插件零 IPC/零全局副作用 | 通过（真实禁用 B 类） |

## 3. 验证证据表

| # | 命令 | 结果 |
| --- | --- | --- |
| V-1 | `python scripts/verify_t093_p6a.py` | **11 [OK] / 0 [FAIL]** |
| V-2 | `pytest services/api/tests -q` | **87 passed** |
| V-3 | TypeScript 全量回归 | contracts / host-core / plugin-runtime / kernel-dsh / enterprise-admin / knowledge / docgraph / ipd / acp 均 exit 0 |
| V-4 | `python scripts/check_task_split.py --stats` | **8 [OK] / 0 [FAIL]** |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 `pnpm dsh --profile acp` 服务器 + 官方客户端 `dsh-subagent-acp` 端到端联调。
- B-2：真实进程异常退出时的失败上报与任务状态收敛。
- B-3：真实 `session/request_permission` 流程与企业策略的对接、GUI 审批提示呈现。
- B-4：真机禁用 ACP 插件后 P1~P5 仍可运行。

**需外部输入（C 类）**

- C-1：企业默认模型/推理强度、MCP 服务器清单与工具白名单最终口径。

**超出本次范围**

- O-1：不自研 JSON-RPC / ACP 协议实现；不用 ACP 替换交互主链路（§8、§11.1/11.2、§4.6.1 第 6 条）。
- O-2：不做多级审批流与 SSO（P6C 触发条件未成立）。

## 5. 复现命令

```powershell
cd "<repo-root>"
python scripts/verify_t093_p6a.py
python scripts/check_task_split.py --stats
cd services/api; .venv\Scripts\python.exe -m pytest tests -q
```

## 6. 下一步

1. 批次 8（P6B 插件市场与企业治理，T-100~T-105）为全计划最后一批。
