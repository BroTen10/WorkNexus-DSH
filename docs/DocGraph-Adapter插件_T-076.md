# P4 DocGraph Adapter 收尾（T-076）

## 1. 结论先行

1. 批次 5（T-070~T-076）已全部实现并提交；`verify_t076_p4.py` 汇总 5 个子门禁、Python/TypeScript 全量回归、控制面端到端与中断隔离核查，结果 **13 [OK] / 0 [FAIL]**。
2. DocGraph 保持独立服务：Adapter 只走 T-009 清单里的 HTTP 端点（`/api/health`、`/api/reviews/start`、`/api/reviews/{id}`、`/by-rule`），不复制其数据库/图谱/业务逻辑，不使用内存态建图端点。
3. 交付面：连接配置与四类健康/错误处理、任务提交与台账、五态状态轮询（有上限与退避）、结构化结果视图、权限/审计/用量三件套、Agent 会话引用。
4. 诚实边界：远端**无取消端点** → 取消只做平台侧标记并显式返回 `remoteSupported: false`；DocGraph **无用量端点** → 用量按任务记录但 Token 与成本留 `null`（`source=adapter_estimate`）。
5. §4.4.4 五条验收均有可执行证据；真实现网联调（网关鉴权、真实合同/文档、真实结果结构）与 GUI 交互未闭环，登记为 B/C 类，**不宣称批次 5 真机全绿**。
6. 裁决：批次 5 的自动化退出条件成立，T-090（P6A ACP）具备开工条件；真机联调另行闭环。

## 2. §4.4.4 五条验收证据

| # | 验收 | 证据 | 判定 |
| --- | --- | --- | --- |
| 1 | 管理员配置连接后健康检查通过 | `docs/DocGraph连接配置_T-070.md`；`verify_t070_docgraph_client.py` = 6 [OK]（含 `status: ok` 与不可达两种口径） | 通过（自动化；真实实例 B 类） |
| 2 | 授权用户可在项目空间提交任务 | `docs/DocGraph任务提交_T-071.md`；`test_docgraph_submit.py` 5 passed（成员 202 / 非成员 404 + denied 审计 / viewer 只读） | 通过 |
| 3 | 任务状态和结果可查看 | `docs/DocGraph任务状态_T-072.md` + `docs/DocGraph结果查看_T-073.md`；轮询 5 用例、结果 3 用例、控制面 `GET /jobs/{id}` 实测 | 通过 |
| 4 | DocGraph 停止时基础会话、企业管理、知识库仍可运行 | `verify_t076_p4.py` 端到端真实调用：健康检查 OK、`/knowledge-bases` 与 `/knowledge-bindings` 仍 200；插件侧降级断言（健康 false、轮询 unknown） | 通过 |
| 5 | 禁用 DocGraph Adapter 后其他功能不受影响 | `plugins/docgraph` 无 IPC、无会话接管、模块无副作用（`DOCGRAPH_PAGES` 冻结、引用/结果均为纯函数）；P2/P3 回归用例全绿 | 通过（自动化口径；真机禁用 B 类） |

## 3. 附加核查

| 范围 | 结论 |
| --- | --- |
| §4.4.2 集成原则 | 只做 Adapter；不拆散 DocGraph；不做深度双层拆分；HTTP 通信；不可用不影响其他插件 |
| §5.2 插件声明 | 官方 `dsh.bundle.patch` + 三个 UI 槽位 + `space.read`/`docgraph.submit`/`docgraph.read` |
| §5.4 失败隔离 | 健康检查不抛错、轮询失败降级、控制面不代理远端调用 |
| §6.2 审计 | `docgraph.submit` / `docgraph.view` / `docgraph.cancel` 三类；拒绝路径写 `denied` |
| §6.3 用量 | 任务级记录，`source=adapter_estimate`，Token/成本留 `null`（无远端来源，不填假数） |
| §11 负向清单 | 不重构 DocGraph 核心（§11.8）、不新增第二套会话/插件/凭据机制（§11.1/11.2/11.12/11.13） |

## 4. 验证证据表

| # | 命令 | 结果 |
| --- | --- | --- |
| V-1 | `python scripts/verify_t076_p4.py` | **13 [OK] / 0 [FAIL]** |
| V-2 | `pytest services/api/tests -q` | **78 passed** |
| V-3 | TypeScript 全量回归 | contracts / host-core / plugin-runtime / kernel-dsh / enterprise-admin / knowledge / docgraph 均 exit 0 |
| V-4 | `python scripts/check_task_split.py --stats` | **8 [OK] / 0 [FAIL]** |

## 5. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 DocGraph 实例的 `/openapi.json` 与运行时路由表比对（T-009 B-1）。
- B-2：`by-rule` / `by-doc` 在任务不存在时的真实错误码（T-009 B-2）。
- B-3：真实文档上传/选择 → 提交 → 状态 → 结果 → 会话引用的完整 GUI 链路。
- B-4：平台侧取消后远端任务的实际状态（需运维在 DocGraph 侧观察）。
- B-5：真机禁用 Adapter 后 P1/P2/P3 仍可运行。

**需外部输入（C 类）**

- C-1：**现网是否已在前置网关做鉴权**（决定 Token 是否必填）。
- C-2：DocGraph 现网地址、可用合同/文档数据与结果样本。

**超出本次范围**

- O-1：不做 DocGraph 规则解析、图谱构建、OCR 质量评估与人工闭环回写。
- O-2：不做后台自动化编排（属 P6A）、不做第二套会话/插件/凭据机制。

## 6. 复现命令

```powershell
cd "<repo-root>"
python scripts/verify_t076_p4.py
python scripts/check_task_split.py --stats
cd services/api; .venv\Scripts\python.exe -m pytest tests -q
```

## 7. 下一步

1. 批次 6（T-080~T-083 IPD Demo）依赖条件已满足，可继续推进。
2. T-076 完成后 T-090（P6A ACP 后台自动化）具备开工条件（总览 §1.2 G10）。
