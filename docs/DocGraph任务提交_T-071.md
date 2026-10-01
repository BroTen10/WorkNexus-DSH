# DocGraph 任务提交（T-071）

## 1. 结论先行

1. 控制面新增 `POST /api/v1/docgraph/tasks` 与 `GET /api/v1/docgraph/tasks?spaceId=`：从**项目空间**提交文档分析/审查任务，任务记录落在本地 `BackgroundJob`（`job_type=docgraph.<mode>`）。
2. 权限是**空间成员 + 动作权限**双校验：`require_space_action()` 先取空间归属（`visible_project_space_ids`），再按服务端矩阵校验 `docgraph.submit` / `docgraph.read`；任一不满足即 404。
3. 拒绝路径**写 `denied` 审计**（`result='denied'`）后才返回 404，既满足 §6.2 第 6 类审计要求，也不泄漏资源存在性（与 T-045 同口径）。
4. 提交写审计 `docgraph.submit`（成功路径）；payload 记录 `spaceId` / `documentId` / `contractId` / `mode` / `remoteTaskId`（初始为 `null`）。
5. 控制面**不代理远端调用**：DocGraph 不可达由插件侧 T-070 健康检查暴露；提交与本地状态不受影响（P4-F03 与 §5.4 第 3 条一致）。
6. 裁决：`remoteTaskId` 由插件客户端在调用 `POST /api/reviews/start` 后回填，本任务不实现回填端点 — 理由是 T-072 的状态轮询走插件客户端直连，控制面只作任务台账 — 错判代价：控制面视图暂时看不到远端任务号，需 T-074 的查看接口补充展示。
7. 裁决：普通成员可提交、viewer 只能读 — 依据服务端矩阵（`member` 含 `docgraph.submit`，`viewer` 只含 `docgraph.read`）— 错判代价：若业务要求 viewer 也能提交，需要修改矩阵（属 Host Core 契约变更，另行评审）。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `services/api/app/routers/docgraph.py` | 新增 | 提交/列表接口 + 空间权限与拒绝审计 |
| `services/api/app/main.py` | 修改 | 注册 docgraph 路由 |
| `plugins/docgraph/src/pages/SubmitTask.tsx` | 新增 | 提交页声明（analysis / review） |
| `plugins/docgraph/src/index.ts` | 修改 | 导出提交页 |
| `plugins/docgraph/test/client.test.ts` | 修改 | 页面清单断言更新为两个页面 |
| `services/api/tests/test_docgraph_submit.py` | 新增 | 5 用例：成员提交+审计、非成员 404+denied 审计、viewer 只读、未登录 401、不可达不阻塞提交 |
| `docs/DocGraph任务提交_T-071.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 提交用例 | `pytest tests/test_docgraph_submit.py -q` = **5 passed** | 通过 |
| V-2 | 全量回归 | `pytest tests -q` = **74 passed** | 通过 |
| V-3 | 插件回归 | `vitest run` = **8 passed**；typecheck exit 0 | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实文档上传/选择链路与任务提交的真实远端联动。
- B-2：空间成员在 GUI 内提交的完整交互。

**需外部输入（C 类）**

- C-1：DocGraph 现网地址、网关鉴权与可用合同/文档数据。

**超出本次范围**

- O-1：不做 DocGraph 规则解析、图谱构建、OCR 质量评估（T-009 O-1）。
- O-2：不绕过空间权限提交，不使用内存态建图端点。

## 5. 复现命令

```powershell
cd "<repo-root>"
cd services/api; .venv\Scripts\python.exe -m pytest tests/test_docgraph_submit.py -q
cd ../..; pnpm --filter @worknexus/plugin-docgraph test
```

## 6. 下一步

1. T-072：状态轮询（五态、上限与退避、失败不崩）。
