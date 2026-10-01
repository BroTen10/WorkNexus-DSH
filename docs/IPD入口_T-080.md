# IPD 入口与插件注册（T-080）

## 1. 结论先行

1. `plugins/ipd` 以官方 UI 插件形态交付：`plugin.manifest.json`（`type: ui` + `dsh.bundle.patch`）、`package.json`、`cordis.patch.yml`。
2. 入口**双挂载**：菜单入口 `worknexus.ipd.menu` 与项目空间入口 `worknexus.ipd.process` / `worknexus.ipd.project`，共三个官方 UI 槽位（P5-F01）。
3. 门控：个人模式零入口（`visibleEntries('personal') === []`）；企业模式下入口可见性复用 Host Core 权限枚举 `space.read`（`entriesForActor`），未授权角色同样零入口（P5-F06 的前置落地）。
4. 禁用即注销：入口注册表是冻结的纯数据，注销时直接移除，不残留全局状态；插件不注册任何 IPC 或后台任务。
5. 裁决：入口种类（菜单 / 项目空间）由企业侧入口注册表表达，`uiSlots` 仍保持冻结 schema 的**字符串槽位** — 理由是 T-031 已冻结的声明规范不允许对象型槽位，改 schema 属契约变更 — 错判代价：`slot.kind === 'menu'` 这种判断要改读企业侧注册表（已在测试中按新口径断言）。
6. 裁决：入口放置采用「菜单 + 项目空间」双挂载 — 依据 T-080 裁决默认值（入口位置未定）— 错判代价：若产品只保留其一，需要改注册表并回归测试。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `plugins/ipd/package.json` | 新增 | 插件工作区包 |
| `plugins/ipd/plugin.manifest.json` | 新增 | `type: ui` + 三槽位 + `space.read` |
| `plugins/ipd/cordis.patch.yml` | 新增 | 官方 bundle patch 声明 |
| `plugins/ipd/tsconfig.json` | 新增 | 类型检查配置 |
| `plugins/ipd/src/index.ts` | 新增 | 入口注册表、模式门控、权限可见性、槽位常量 |
| `plugins/ipd/test/registration.test.ts` | 新增 | 4 用例：manifest、双挂载、门控、注销无残留 |
| `scripts/verify_t080_ipd_entry.py` | 新增 | 单任务门禁 |
| `pnpm-lock.yaml` | 修改 | 纳入 `plugins/ipd` importer |
| `docs/IPD入口_T-080.md` | 新增 | 本说明 |

**差异集条目**：未改动上游文件，差异集为空。

## 3. 验证证据表

| # | 断言 | 命令 / 结果 | 判定 |
| --- | --- | --- | --- |
| V-1 | 插件测试 | `vitest run` = **4 passed** | 通过 |
| V-2 | 类型检查 | `tsc -p tsconfig.json --noEmit` exit 0 | 通过 |
| V-3 | 单任务门禁 | `python scripts/verify_t080_ipd_entry.py` = **6 [OK] / 0 [FAIL]** | 通过 |

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：真机确认个人模式不可见、企业模式可见（菜单与项目空间两处）。
- B-2：权限不足时的入口隐藏体验。

**需外部输入（C 类）**

- C-1：官方 UI 槽位协议最终形态与菜单注册方式。
- C-2：IPD 场景命名与文案（当前为「IPD 示例」占位）。

**超出本次范围**

- O-1：不做真实 IPD 流程引擎、审批流、PLM/ERP 集成、甘特图排程、复杂表单建模（§4.5.3）。
- O-2：不新增插件管理 IPC。

## 5. 复现命令

```powershell
cd "<repo-root>"
pnpm install --offline
pnpm --filter @worknexus/plugin-ipd test
python scripts/verify_t080_ipd_entry.py
```

## 6. 下一步

1. T-081：样例流程视图（阶段 / 评审点 / 交付物 / 角色 + 本地示例数据）。
