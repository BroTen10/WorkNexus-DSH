# DocGraph 连接配置与健康检查（T-070）

## 1. 结论先行

1. `plugins/docgraph` 以官方插件形态建立（`package.json` / `plugin.manifest.json` / `dsh.bundle.patch`），权限声明 `space.read` / `docgraph.submit` / `docgraph.read`。
2. `src/client.ts` 交付 `createDocGraphClient(config)`：**端点与错误码唯一来源是 T-009 清单**，不另行推测——健康 `GET /api/health`、提交 `POST /api/reviews/start`、状态 `GET /api/reviews/{id}`、结果 `GET /api/reviews/{id}/by-rule`。
3. 连接配置含地址 / Token / 超时 / 默认参数（`defaultSnapshotId`），Token 允许留空并标注 `authNote: 'gateway-dependent'`——因为 DocGraph 本体**没有鉴权层**，是否注入由部署侧网关决定（T-009 R-2 / C-1）。
4. 健康检查返回 `{ ok, detail }` 而非抛错；非 2xx 归一为类型化错误 `DocGraphHttpError`（`docgraph-http-<status>`），符合 T-009 的错误码口径。
5. 远端状态**原样透传**：`pending/running/completed/failed` → `queued/running/succeeded/failed`，未知值映射为 `unknown` 并保留 `rawStatus`，不猜测（P4-F04 前置）。
6. 裁决：**远端无取消端点**，`cancel()` 显式返回 `{ ok: false, supported: false, detail: 'docgraph-unsupported: …' }` 且**不发任何请求** — 依据 T-009 清单与总览 §2.1 第 14 条（未支持能力不伪装）— 错判代价：平台侧取消只能标记本地任务状态，远端任务仍在运行。
7. 裁决：凭据只接受官方凭据服务已解析的事实或一次性 `resolveToken()`，错误与描述信息全部过 `sanitizeDetail` — 依据 T-025 凭据边界 — 错判代价：若部署侧网关需要额外 header，需在配置层扩展（不影响本模块结构）。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `plugins/docgraph/package.json` | 新增 | 插件工作区包（contracts / host-core / plugin-runtime / react） |
| `plugins/docgraph/plugin.manifest.json` | 新增 | 官方 bundle 声明 + docgraph 权限 + 三个 UI 槽位 |
| `plugins/docgraph/cordis.patch.yml` | 新增 | 官方 bundle patch 声明 |
| `plugins/docgraph/tsconfig.json` | 新增 | 类型检查配置（ES2022 + DOM） |
| `plugins/docgraph/src/client.ts` | 新增 | 客户端：健康/提交/状态/结果/取消 + 错误与脱敏 |
| `plugins/docgraph/src/pages/Connection.tsx` | 新增 | 连接页声明（Token 可留空） |
| `plugins/docgraph/src/index.ts` | 新增 | 插件导出面 |
| `plugins/docgraph/test/client.test.ts` | 新增 | 8 用例：连接失败、健康口径、类型化错误、凭据不外泄、提交端点、状态映射与取消不支持、结果端点、manifest |
| `scripts/verify_t070_docgraph_client.py` | 新增 | 单任务门禁 |
| `pnpm-lock.yaml` | 修改 | 纳入 `plugins/docgraph` importer |
| `docs/DocGraph连接配置_T-070.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 插件测试 | `vitest run` = **8 passed** | 通过 |
| V-2 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-3 | 单任务门禁 | `python scripts/verify_t070_docgraph_client.py` = **6 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 DocGraph 实例的 `/openapi.json` 与实际路由表比对（T-009 B-1）。
- B-2：`by-rule` / `by-doc` 在「任务不存在」时的真实错误码（T-009 B-2，登记为未验证）。
- B-3：连接页面在官方 UI 槽位的真实渲染与凭据装配。

**需外部输入（C 类）**

- C-1：**现网部署是否在前置网关做鉴权**（决定 Token 是否必填）。
- C-2：DocGraph 现网地址与可用测试账号。

**超出本次范围**

- O-1：不复制 DocGraph 的数据库、图谱或业务逻辑（§4.4.2 第 2 条）。
- O-2：不调用内存态 `build-graph-*` 端点（T-009 §7 第 2 条）。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm install --offline
pnpm --filter @worknexus/plugin-docgraph test
pnpm --filter @worknexus/plugin-docgraph typecheck
python scripts/verify_t070_docgraph_client.py
```

## 6. 下一步

1. T-071：控制面任务提交（`POST /api/v1/docgraph/tasks`）+ 提交页面声明 + 空间权限与拒绝审计。
