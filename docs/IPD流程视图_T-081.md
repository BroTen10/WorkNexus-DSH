# IPD 样例流程视图（T-081）

## 1. 结论先行

1. `plugins/ipd/src/pages/ProcessView.tsx` 渲染 IPD 样例流程：阶段 / 评审点 / 交付物 / 角色四要素齐全（P5-F02）。
2. 数据是 4 个阶段的**本地静态示例**（`src/data/sample-process.json`），页面顶部显式标注「【示例数据】」，`demo: true` 可被程序断言（P5-F03）。
3. 不接真实业务数据源：视图层无 `fetch` / axios / HTTP 调用，纯展示组件（负向门禁断言）。
4. 不承诺真实流程能力：没有流程引擎、审批流转、状态机（§4.5.3 明确不做）。
5. 裁决：样例内容取「概念 → 计划 → 开发 → 发布」四阶段与对应 CDCP/PDCP/TR/ADCP 评审点 — 理由是覆盖评审点与角色两类信息即可支撑 Demo 叙事 — 错判代价：若客户希望按自家流程定制阶段命名，需要替换示例数据并回归测试。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `plugins/ipd/src/data/sample-process.json` | 新增 | 4 阶段样例流程（含 demo 标注） |
| `plugins/ipd/src/pages/ProcessView.tsx` | 新增 | `ProcessView` / `SAMPLE_PROCESS` / 类型 |
| `plugins/ipd/test/process-view.test.tsx` | 新增 | 2 用例：四要素渲染、示例标注与静态数据 |
| `scripts/verify_t081_ipd_process.py` | 新增 | 单任务门禁 |
| `docs/IPD流程视图_T-081.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 插件测试 | `vitest run` = **6 passed**（process-view 2） | 通过 |
| V-2 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-3 | 单任务门禁 | `python scripts/verify_t081_ipd_process.py` = **5 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真机页面渲染与官方 UI 槽位适配（含示例标注的视觉呈现）。

**需外部输入（C 类）**

- C-1：客户真实的 IPD 阶段命名与交付物清单（当前为通用样例）。

**超出本次范围**

- O-1：不做流程引擎、审批流、PLM/ERP 集成、甘特图排程、复杂表单建模（§4.5.3）。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm --filter @worknexus/plugin-ipd test
python scripts/verify_t081_ipd_process.py
```

## 6. 下一步

1. T-082：样例项目状态视图 + 预置 prompt。
