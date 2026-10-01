# DocGraph 任务状态跟踪（T-072）

## 1. 结论先行

1. `plugins/docgraph/src/status-poller.ts` 交付 `collectStatuses(client, jobId, options)`：按上限轮询并返回观察到的状态序列，覆盖排队 / 运行中 / 成功 / 失败 / 取消五态，未知状态映射为 `unknown`。
2. 轮询**有上限且有退避**：默认 `intervalMs=2000`、`backoffFactor=1.5`、`maxIntervalMs=15000`、`maxPolls=30`；等待函数可注入，便于测试与真机调参。
3. 轮询失败（网络/超时/远端 5xx）**不抛未捕获异常**：记为一次 `unknown` 观测并继续退避重试，直到上限，避免拖垮主界面。
4. `pages/JobList.tsx` 声明任务列表页与五态中文标签，未知状态显式显示「未知」，不猜测（P4-F04）。
5. 裁决：`unknown` 也参与终态判断之外的重试 — 理由是远端状态字段可能临时缺失，直接判失败会造成误报 — 错判代价：任务长期处于未知会持续轮询到上限（上限本身可控）。
6. 裁决：退避在**每次等待前**递增（先按当前间隔等待，再放大）— 理由是首轮等待不应被放大，否则首个状态延迟过高 — 错判代价：无（行为由用例锁定为 100→200→400→400）。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `plugins/docgraph/src/status-poller.ts` | 新增 | `collectStatuses` / `isTerminal` / 默认参数 |
| `plugins/docgraph/src/pages/JobList.tsx` | 新增 | 任务列表页声明 + 五态标签 |
| `plugins/docgraph/test/status-poller.test.ts` | 新增 | 5 用例：状态流转停止、上限停止、失败降级、退避序列、页面注册 |
| `plugins/docgraph/src/index.ts` | 修改 | 导出轮询模块与任务列表页 |
| `plugins/docgraph/test/client.test.ts` | 修改 | 页面清单断言更新为三个页面 |
| `scripts/verify_t072_docgraph_status.py` | 新增 | 单任务门禁 |
| `docs/DocGraph任务状态_T-072.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 失败测试先行 | `vitest run status-poller` → `Failed to load url ../src/status-poller.js` | 已确认 RED |
| V-2 | 插件测试 | `vitest run` = **13 passed** | 通过 |
| V-3 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-4 | 单任务门禁 | `python scripts/verify_t072_docgraph_status.py` = **6 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实远端状态字段（`pending/running/completed/failed`）与本地映射的一致性（T-009 已登记字段级未实测）。
- B-2：长任务轮询对主界面的真实影响与退避参数体验。

**需外部输入（C 类）**

- C-1：可用的 DocGraph 实例与长任务样本。

**超出本次范围**

- O-1：不做远端取消（远端无该端点，见 T-070 裁决）。
- O-2：不做任务队列调度、重试编排（属平台后台任务范围，P6A）。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm --filter @worknexus/plugin-docgraph test
python scripts/verify_t072_docgraph_status.py
```

## 6. 下一步

1. T-073：结果查看（结构化视图 + 原文跳转 + 原始 JSON 兜底）。
