# 技术决策：DocGraph API 与鉴权清单（T-009）

> 任务：T-009 DocGraph API 与鉴权清单 ｜ 批次 0 ｜ 依赖 T-000 ｜ 无人值守度 C（需外部系统）
> 执行日期：2026-09-28 ｜ 取证方式：**源码静态审计**（DocGraph 服务未启动，未能取 `GET /openapi.json`）
> 被审计对象：`<data-root>\DocGraph` @ `059eb517f85c9cb005c664488a08450e228606ff`

## 1. 结论先行

1. **DocGraph 现网是 FastAPI 单体**：`backend/app/main.py`，`title="基于知识图谱的自动文档审查智能体 API"`，`version="1.0.0"`，默认 `app_port=8000`，**9 个 router + 2 个 app 级路由，共 55 个端点**。
2. **没有任何鉴权层**。全部端点的唯一依赖是 `db: Session = Depends(get_db)`；全仓无 `HTTPBearer` / `OAuth2` / `APIKeyHeader` / `Security(...)`。**这意味着 Adapter 不能假设「带 token 就能访问」，鉴权必须由部署侧前置网关承担**——本次清单按「无鉴权」登记，并把「现网是否已有网关鉴权」列为**未实测**（C 类）。
3. **任务模型可直接映射**：`提交 = POST /api/reviews/start` → `轮询 = GET /api/reviews/{task_id}` → `取结果 = GET /api/reviews/{task_id}/by-rule`（或 `/by-doc`）。字段级映射见 §5。
4. **两个必须规避的坑**：
   - **图构建任务是进程内内存态**（`services/graph_build_progress.py` 的模块级 `_build_tasks` 字典），**重启即丢、多实例不共享**；Adapter 不得把它作为持久状态源。
   - `graph.py` 的 router 前缀是 `/api/rules`（与 `rules.py` **同前缀**），路由按注册顺序解析，存在歧义风险；Adapter 调用时须逐条用真实路径验证。
5. **无用量接口**。全仓无 token/计费端点 → DocGraph 侧用量只能由 Adapter 本地估算（`source=adapter_estimate`）或留 `null`，符合总览 §2.1 第 15 条。

## 2. 取证来源与命令

| # | 目的 | 命令 |
| --- | --- | --- |
| 1 | 应用与路由注册 | `Get-Content "<data-root>\DocGraph\backend\app\main.py"` |
| 2 | router 前缀 | `Select-String -Path "...\app\routers\*.py" -Pattern "APIRouter\("` |
| 3 | 端点清单 | `Select-String -Path "...\app\routers\*.py" -Pattern "@router\.(get|post|put|delete|patch)\("` |
| 4 | 鉴权面 | `Select-String -Path "...\app\**\*.py" -Pattern "Depends\(|HTTPBearer|APIKeyHeader|oauth2|Security\("` |
| 5 | 响应模型 | `Get-Content "...\app\schemas\review.py"`、`contract.py`、`graph.py` |
| 6 | 状态机 | `Select-String -Path "...\app\services\review_service.py" -Pattern "status *= "`；`...\app\models\review_task.py`、`review_result.py` |
| 7 | 审计基线 | `git -C "<data-root>\DocGraph" rev-parse HEAD` → `059eb517f85c9cb005c664488a08450e228606ff` |

未执行的取证（见 §6）：`GET /openapi.json`（服务未启动，需 PG + Neo4j，本机 Docker daemon 未运行）。

## 3. 逐项判定表

### 3.1 服务基线

| 项 | 值 | 来源 |
| --- | --- | --- |
| 框架 / 入口 | FastAPI ／ `backend/app/main.py` | 命令 1 |
| 标题 / 版本 | 基于知识图谱的自动文档审查智能体 API ／ `1.0.0` | 命令 1 |
| 描述 | 出口代理贸易单证自动审查 - MVP（多规则集） | 命令 1 |
| 默认端口 | `app_port = 8000`（`app_host = 0.0.0.0`） | `app/config.py` |
| CORS | 白名单：`localhost:5173`、`127.0.0.1:5173`、`localhost:3000`、`localhost:8800`（**已收紧，不再 `*`**） | `app/config.py` |
| 健康检查 | `GET /api/health` → `{"status":"ok","version":"1.0.0"}` | 命令 1 |
| 审计提交 | `059eb51 chore: 统一 DeepSeek 模型名配置为 deepseek-flash`（HEAD） | 命令 7 |
| 存储 | PostgreSQL（契约/规则/任务/结果） + Neo4j（图谱） | `config.py`、`routers/graph.py` |

### 3.2 端点清单（55 条）

**鉴权列统一为「无」** —— 所有端点仅依赖 `get_db`。按 §2.1 第 4 条裁决，未实测部分标「未验证」，**不推测**。

#### contracts（前缀 `/api/contracts`）

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 | 幂等 |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/contracts/upload` | 文件夹上传（multipart） | `contract_id` / `contract_no` / `alias_list` / `file_count` / `classified` | 422 | 否（每次新建合同） |
| GET | `/api/contracts` | — | `ContractBrief[]`：`id`/`rule_set_id`/`contract_no`/`alias_list`/`upload_time`/`status`/`file_count` | — | 是 |
| GET | `/api/contracts/{contract_id}` | — | `ContractDetail`（含 `documents[]`、`note`） | 404 | 是 |
| DELETE | `/api/contracts/{contract_id}` | — | `{}` | 404 | 否 |
| PUT | `/api/contracts/{contract_id}/aliases` | `contract_no`, `alias_list` | `ContractBrief` | 404/422 | 是 |
| PUT | `/api/contracts/documents/{doc_id}/doc-type` | `doc_type` | `DocumentBrief` | 404/422 | 是 |
| PUT | `/api/contracts/documents/{doc_id}/ocr-fields` | `extracted_fields`, `has_stamp` | `DocumentBrief` | 404/422 | 是 |
| GET | `/api/contracts/documents/{doc_id}/file` | — | 文件流 | 404 | 是 |
| GET | `/api/contracts/documents/{doc_id}/ocr` | — | `DocumentBrief`（含 `ocr_text`/`ocr_layout`） | 404 | 是 |

#### reviews（前缀 `/api/reviews`）——**Adapter 主链路**

| 方法 | 路径 | 请求关键字段 | 响应关键字段 | 错误码 | 幂等 |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/reviews/start` | `contract_id`(UUID,必填), `snapshot_id`(UUID,选填；不传用最新快照) | `ReviewTaskSummary`：`id`/`contract_id`/`status`/`progress`/`stage`/`start_time`/`end_time`/`error`/`summary` | **400**（`ValueError` 如合同不存在/无快照） | **否**（每次产生新任务） |
| GET | `/api/reviews` | `contract_id?`、`rule_set_id?`、`limit?`(1..500,默认100) | `ReviewTaskListItem[]`（含 `contract_no`） | 422 | 是 |
| GET | `/api/reviews/{task_id}` | — | `ReviewTaskSummary` | **404**「任务不存在」 | 是 |
| GET | `/api/reviews/{task_id}/by-rule` | — | `{task_id, results: ReviewResultItem[], summary}` | 未验证 | 是 |
| GET | `/api/reviews/{task_id}/by-doc` | — | `{task_id, docs:[{document, results}], summary}` | 未验证 | 是 |
| PATCH | `/api/reviews/results/{result_id}/status` | `status`(open/confirmed/fixed/closed), `note?` | `ReviewResultItem` | **400** | 是 |

#### rules（前缀 `/api/rules`）与 graph（前缀 `/api/rules`，**同前缀**）

| 方法 | 路径 | 说明 | 幂等 |
| --- | --- | --- | --- |
| GET | `/api/rules` | 规则列表 | 是 |
| POST | `/api/rules` | 新建规则（201） | 否 |
| POST | `/api/rules/import-batch` | 批量导入规则 | 否 |
| PUT | `/api/rules/{rule_id}` | 更新规则 | 是 |
| DELETE | `/api/rules/{rule_id}` | 删除规则 | 否 |
| DELETE | `/api/rules` | 清空规则 | 否 |
| POST | `/api/rules/confirm` | 规则确认 | 否 |
| GET | `/api/rules/defect-summary` | 缺陷汇总 | 是 |
| GET | `/api/rules/snapshots` | 图谱快照列表 | 是 |
| GET | `/api/rules/snapshots/{snapshot_id}` | 单快照 | 是 |
| POST | `/api/rules/detect-conflicts` | 规则冲突检测 | 是 |
| POST | `/api/rules/build-graph-async` | 异步建图 → `AsyncBuildResponse` | 否 |
| GET | `/api/rules/build-graph-status/{task_id}` | **内存态**建图状态 | 是 |
| GET | `/api/rules/build-graph-tasks` | **内存态**建图任务列表 | 是 |
| POST | `/api/rules/import-document` | 规则文档导入 | 否 |
| GET | `/api/rules/import-tasks/{task_id}` | 导入任务 | 是 |
| GET | `/api/rules/graph` | 图谱数据 `GraphData` | 是 |
| GET | `/api/rules/graph/ontology` | 本体 | 是 |
| GET | `/api/rules/graph/{graph_id}` | 指定图谱 | 是 |
| PUT | `/api/rules/graph/confirm` | 图谱确认 | 是 |

#### rule-sets（前缀 `/api/rule-sets`）

| 方法 | 路径 | 说明 | 幂等 |
| --- | --- | --- | --- |
| GET | `/api/rule-sets` | 规则集列表 | 是 |
| POST | `/api/rule-sets` | 新建（201） | 否 |
| GET | `/api/rule-sets/{rule_set_id}` | 详情 | 是 |
| PUT | `/api/rule-sets/{rule_set_id}` | 更新 | 是 |
| DELETE | `/api/rule-sets/{rule_set_id}` | 删除 | 否 |
| POST | `/api/rule-sets/{rule_set_id}/set-default` | 设为默认 | 是 |

#### rule-parse-skills（前缀 `/api/rule-sets/{rule_set_id}/skills`）

| 方法 | 路径 | 说明 | 幂等 |
| --- | --- | --- | --- |
| GET | `""` | 技能列表 | 是 |
| POST | `""` | 新建（201） | 否 |
| POST | `/learn` | 学习 | 否 |
| GET | `/{skill_id}` | 详情 | 是 |
| PUT | `/{skill_id}` | 更新 | 是 |
| DELETE | `/{skill_id}` | 删除 | 否 |

#### ocr（前缀 `/api/ocr`）

| 方法 | 路径 | 说明 | 幂等 |
| --- | --- | --- | --- |
| POST | `/api/ocr/documents/{doc_id}` | 单文档 OCR（201）→ `OcrTaskOut` | 否 |
| POST | `/api/ocr/contracts/{contract_id}` | 合同批量 OCR（201） | 否 |
| GET | `/api/ocr/tasks` | OCR 任务列表 | 是 |
| GET | `/api/ocr/tasks/{task_id}` | OCR 任务详情 | 是 |

#### doc-types（前缀 `/api/doc-types`）

| 方法 | 路径 | 说明 | 幂等 |
| --- | --- | --- | --- |
| GET | `/api/doc-types` | 列表 | 是 |
| GET | `/api/doc-types/{type_id}` | 详情 | 是 |
| POST | `/api/doc-types` | 新建（201） | 否 |
| PUT | `/api/doc-types/{type_id}` | 更新 | 是 |
| DELETE | `/api/doc-types/{type_id}` | 删除 | 否 |
| POST | `/api/doc-types/{type_id}/confirm` | 确认 | 是 |
| POST | `/api/doc-types/{type_id}/reject` | 驳回 | 是 |
| POST | `/api/doc-types/analyze-sample` | 样本分析 | 否 |
| POST | `/api/doc-types/detect-from-rules` | 从规则推断类型 | 是 |

#### settings（前缀 `/api/settings`）与 app 级

| 方法 | 路径 | 说明 | 幂等 |
| --- | --- | --- | --- |
| GET | `/api/settings` | 读取设置 | 是 |
| PUT | `/api/settings` | 更新设置 | 是 |
| POST | `/api/settings/optimize-prompt` | 提示词优化 | 否 |
| GET | `/api/health` | 健康检查 | 是 |
| GET | `/api/constants/doc-types` | 文件类型与检查项（`main.py` 内联） | 是 |

### 3.3 状态枚举（实测自源码）

| 对象 | 取值 | 来源 |
| --- | --- | --- |
| `ReviewTask.status` | `pending`（模型默认） → `running` → `completed` / `failed` | `models/review_task.py:31`、`services/review_service.py:134/321/164` |
| `ReviewTask.progress` | 0–100 整数；`stage` 为可读阶段名 | `models/review_task.py:33/35` |
| `ReviewResult.result` | `pass` / `fail` / `unverifiable`（三态） | `services/review_service.py` 模块 docstring |
| `ReviewResult.status` | `open` / `confirmed` / `fixed` / `closed`（带 `status_history` 审计） | `models/review_result.py:40-42` |
| `ReviewResult.source` | `graph` / `llm` / `legacy` | `schemas/review.py` 注释 |
| 建图任务 `status` | `running` / `completed` / `failed`（**进程内内存**） | `services/graph_build_progress.py:43/205/226` |
| `Document.ocr_status` | `pending` / `done` / `failed` | `models/document.py:37`、`services/review_service.py:196/205/221` |
| `Contract.status` | 默认 `uploaded` | `models/contract.py:39` |

## 4. 裁决记录

| # | 裁决：<决定> — <理由> — <错判代价> |
| --- | --- |
| R-1 | 以**源码静态审计**生成清单并标注「/openapi.json 未实测」 — 总览 §2.1 第 4 条明确允许「以现网 openapi.json / 源码为准生成清单，标注未实测」；本机 Docker daemon 未运行，无法起 PG17+Neo4j — 若源码与运行实例存在偏差，字段级映射需在 T-073 联调时校正（成本：1 次联调往返） |
| R-2 | 鉴权按「无」登记，不假设存在 token 机制 — 全仓 grep 无任何安全依赖；凭空写 token 字段会造成假实现 — 若现网实为网关注入鉴权，Adapter 只需在配置层加 header，改动面很小 |
| R-3 | 明确禁止用 `/api/rules/build-graph-*` 作为持久状态源 — 该状态为模块级内存字典，重启即丢 — 若误用，客户会看到「任务消失」类故障，且多实例下行为不一致 |
| R-4 | 附加说明：`graph.py` 与 `rules.py` 共用 `/api/rules` 前缀 — 已实测前缀原文；同前缀路由按注册顺序（`rules` → `graph`）解析 — 若后续 DocGraph 新增冲突路径，Adapter 需按真实响应调整，不按文档猜测 |

## 5. 任务模型（供 T-071 ~ T-073 直接使用）

```
提交任务  POST /api/reviews/start
          body: {"contract_id": "<uuid>", "snapshot_id": "<uuid|null>"}
          → 200 {"id": "<task_uuid>", "contract_id": "...", "status": "pending|running",
                 "progress": 0, "stage": "...", "start_time": "...", "end_time": null,
                 "error": null, "summary": {...}}
          → 400 {"detail": "<ValueError 原文>"}

轮询状态  GET /api/reviews/{task_id}
          → 200 同上结构（status 取 pending/running/completed/failed）
          → 404 {"detail": "任务不存在"}

取结果    GET /api/reviews/{task_id}/by-rule
          → 200 {task_id, results: [{id, rule_id, rule_text, doc_type, check_category,
                 doc_id, doc_name, related_docs[], result: pass|fail|unverifiable,
                 status, status_history[], severity, deviation, graph_source, graph_target,
                 source: graph|llm|legacy, confidence, issue_desc, detail, suggestion}],
                 summary}

人工闭环  PATCH /api/reviews/results/{result_id}/status
          body: {"status": "open|confirmed|fixed|closed", "note": "<可选>"}
```

**字段映射约束**（写入 P4 Adapter 契约）：

| Adapter 概念 | DocGraph 字段 | 说明 |
| --- | --- | --- |
| `remote_task_id` | `ReviewTaskSummary.id` | 轮询主键 |
| `remote_status` | `status`（pending/running/completed/failed） | 直接透传，不二次发明状态 |
| `progress` / `stage` | 同名 | 透传 |
| `issue.result` | `result`（pass/fail/unverifiable） | **三态必须原样保留**，不得归一成二态 |
| `issue.severity` | `severity` ｜ 缺失 → `null` | 不得编造 |
| `issue.source` | `source`（graph/llm/legacy） | 用于可信度提示 |
| `usage.tokens` | **无对应字段** | 留 `null` 或 `adapter_estimate`（§2.1 第 15 条） |

## 6. 未验证项与边界

**需真机复核（B 类）**

- B-1：`GET /openapi.json` 与运行时实际路由表（用于比对源码审计结果）——需启动 PG17 + Neo4j + 后端。
- B-2：`by-rule` / `by-doc` 在「任务不存在」时的实际错误码（源码未显式抛错，本次登记为「未验证」）。
- B-3：`POST /api/contracts/upload` 的 multipart 字段名与大小上限（`max_file_size_mb = 50`）实际生效行为。

**需外部输入（C 类）**

- C-1：**现网部署是否已在前置网关做鉴权**（DocGraph 本体无鉴权）。缺什么：现网拓扑与网关配置。怎么补：向 DocGraph 运维索取部署说明或实测一次未授权请求。影响哪条验收：需求书 §4.4 关于「连接配置与最小权限」的表述、§7 非功能安全项。
- C-2：DocGraph 现网地址与可用测试账号（本次审计为本地源码，未联现网）。

**超出本次范围**

- O-1：不评估 DocGraph 的规则解析、图谱构建、OCR 质量等业务能力（仅接口面）。
- O-2：不做压力/并发测试。

## 7. 对后续任务的约束

1. **T-070**（连接配置与健康检查）：健康检查用 `GET /api/health`；鉴权配置项**必须允许留空**，并在 UI 明确标注「取决于部署侧网关」。
2. **T-071**（任务提交）：只允许 `POST /api/reviews/start`，禁止走内存态的 `build-graph-*`。
3. **T-072**（状态与结果）：轮询 `GET /api/reviews/{task_id}`，结果取 `by-rule`；`pass/fail/unverifiable` 三态原样透传。
4. **T-073**（审计与用量）：用量无远端来源，全部标 `adapter_estimate` 或 `null`；审计事件记录 `remote_task_id` 与 `contract_id`。
5. **T-074/T-075**（Agent 联动）：只读调用，禁止 Adapter 主动修改 DocGraph 规则集/图谱。
6. **联调前置**：先由人工补齐 C-1/C-2（网关鉴权与现网地址），否则 P4 只能停在契约桩 + 单测。

## 8. 复现命令

```powershell
$dg = "<data-root>\DocGraph"
git -C $dg rev-parse HEAD                     # 059eb517f85c9cb005c664488a08450e228606ff
Select-String -Path "$dg\backend\app\routers\*.py" -Pattern "APIRouter\("
Select-String -Path "$dg\backend\app\routers\*.py" -Pattern "@router\.(get|post|put|delete|patch)\("
Select-String -Path "$dg\backend\app\main.py" -Pattern "include_router|app_port|title="
# 鉴权面（应无输出）
Get-ChildItem "$dg\backend\app" -Recurse -Filter *.py |
  Select-String -Pattern "HTTPBearer|OAuth2|APIKeyHeader|Security\("
```
