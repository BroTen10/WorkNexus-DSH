# IPD 样例项目状态与 Agent 示例（T-082）

## 1. 结论先行

1. `plugins/ipd/src/pages/ProjectView.tsx` 渲染样例项目的**当前阶段**与四阶段状态列表（已完成 / 进行中 / 未开始），满足 P5-F04。
2. 样例数据为 2 个本地静态项目（`src/data/sample-projects.json`，`demo: true` + 「示例数据」标注），不接真实项目管理系统。
3. `src/prompts.ts` 提供两个预置 IPD 场景 prompt（阶段总结、评审材料准备），变量用 `{{var}}` 占位：缺变量返回 `missing-variable`，未知模板返回 `unknown-template`，不静默填假值（P5-F05）。
4. 文案明确标注「这是 IPD Demo 的示例场景」并禁止编造，**不承诺真实流程自动化**（§4.5.3 明确不做流程引擎）。
5. 裁决：预置 prompt 使用占位变量而非写死项目名 — 理由是同一模板要复用于不同样例项目/阶段 — 错判代价：调用方必须传变量，否则会得到显式错误而不是可用文本。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `plugins/ipd/src/data/sample-projects.json` | 新增 | 2 个样例项目与阶段状态 |
| `plugins/ipd/src/pages/ProjectView.tsx` | 新增 | `ProjectView` / `SAMPLE_PROJECTS` / 类型 |
| `plugins/ipd/src/prompts.ts` | 新增 | 预置 prompt 模板与 `renderIpdPrompt` |
| `plugins/ipd/test/project-view.test.tsx` | 新增 | 2 用例：当前阶段渲染、阶段列表与示例标注 |
| `plugins/ipd/test/prompts.test.ts` | 新增 | 3 用例：变量渲染、缺变量/未知模板、不承诺自动化 |
| `scripts/verify_t082_ipd_project.py` | 新增 | 单任务门禁 |
| `docs/IPD项目视图_T-082.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 插件测试 | `vitest run` = **11 passed**（project-view 2 + prompts 3） | 通过 |
| V-2 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-3 | 单任务门禁 | `python scripts/verify_t082_ipd_project.py` = **5 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真机项目视图渲染与官方 UI 槽位适配。
- B-2：预置 prompt 在真实会话中的效果（演示性质，不作硬指标）。

**需外部输入（C 类）**

- C-1：客户真实项目命名与阶段状态口径。

**超出本次范围**

- O-1：不做真实流程引擎、审批流、PLM/ERP 集成、甘特图排程。
- O-2：不接真实项目数据源。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm --filter @worknexus/plugin-ipd test
python scripts/verify_t082_ipd_project.py
```

## 6. 下一步

1. T-083：P5 收尾门禁（§4.5.4 四条 + 失败隔离 + §11 负向清单）。
