# DocGraph 结果查看（T-073）

## 1. 结论先行

1. `plugins/docgraph/src/pages/JobResult.tsx` 交付结果视图：结构化命中渲染为「规则 / 结论 / 严重度 / 说明」表格，并提供原文跳转链接（P4-F05）。
2. `result` 三态（`pass` / `fail` / `unverifiable`）**原样保留**，中文标签只是展示层映射，不归一成二态（T-009 §5 字段映射约束）。
3. 缺失字段保留 `null` 并显式显示「未知」，不编造取值（`severity` / `source` 同上）。
4. 结构未知时回退到原始 JSON（`<pre>`），而不是空白页——满足「结果结构未知 → 渲染原始 JSON」的裁决。
5. 不把正文写入本地未加密存储：视图层无任何 `localStorage` / `sessionStorage` / 文件写入调用（负向门禁断言）。
6. 裁决：查看结果的审计（`docgraph.view`）由 T-074 的控制面接口承担，本任务不重复实现 — 理由是审计是服务端权威面，插件只做展示 — 错判代价：若插件被绕过直接读远端，则缺少审计记录（已列入 T-074 的接口约束）。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `plugins/docgraph/src/pages/JobResult.tsx` | 新增 | `JobResult` / `normalizeFindings` / `findSourceUrl` |
| `plugins/docgraph/test/result.test.tsx` | 新增 | 3 用例：结构化渲染与链接、三态与缺失字段、原始 JSON 兜底 |
| `scripts/verify_t073_docgraph_result.py` | 新增 | 单任务门禁 |
| `docs/DocGraph结果查看_T-073.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 插件测试 | `vitest run` = **16 passed**（result 3） | 通过 |
| V-2 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-3 | 单任务门禁 | `python scripts/verify_t073_docgraph_result.py` = **6 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真实 `by-rule` 响应的字段名与嵌套结构（T-009 登记为未验证）。
- B-2：原文跳转在真实文档服务上的可达性与权限。

**需外部输入（C 类）**

- C-1：可用的 DocGraph 实例与一份真实审查结果样本。

**超出本次范围**

- O-1：不做结果编辑/回写（人工闭环 `PATCH /rules/results/{id}/status` 属 DocGraph 自身能力，本期只读）。
- O-2：不在客户端缓存正文。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm --filter @worknexus/plugin-docgraph test
python scripts/verify_t073_docgraph_result.py
```

## 6. 下一步

1. T-074：权限、审计与用量三件套（`docgraph.view` / `docgraph.cancel` / 任务级用量）。
