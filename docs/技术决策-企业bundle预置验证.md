# 技术决策：企业 bundle 预置与 protected 可行性验证（T-005）

> 任务：T-005 企业 bundle 预置与 protected 可行性验证 ｜ 批次 0 ｜ 依赖 T-004 ｜ 无人值守度 B（含真机 GUI 项）
> 执行日期：2026-09-28 ｜ 探针脚本：`scripts/probe_bundle_preload.py` ｜ 探针摘要：`.dsh-check/t005-probe-summary.json`

## 1. 结论先行

1. **「企业 bundle 预置」可行，且实测确认它进入 profile 的 bundle 段**：`dsh --profile ent --dump-config` 输出两个 bundle 层——
   `# == @deepseek-ai/dsh-base` 与 `# == @worknexus/ent-core`，企业层位于官方层**之后**（顺序实测）。
2. **实测得到两条硬约束（此前未知）**：
   - **bundle 必须在自身 `package.json` 声明 `dsh.bundle.patch`**，否则被跳过：
     原始报错 `dsh: skipping profile bundle "@worknexus/ent-core": Error: dsh: profile bundle "@worknexus/ent-core" declares no dsh.bundle in its package.json`。
   - **bundle patch 用 `- insert:` 新增行**；直接写 `- id: <新 id>` 会报 `patch: entry "<id>" not found`（因为该写法是「覆盖已存在的行」）。
3. **bundle 清单本身属 profile 层，不属用户覆盖层**：企业 bundle 段在 `--dump-default-config`（「不含用户层」的默认树）中**同样出现**——说明用户层无法通过覆盖把它从 bundle 段里摘掉，只能通过恢复流程改 profile。
4. **但 `protected` 语义未获证实——风险成立**：实测**用户层 patch 可以把企业 bundle 的条目置为 `disabled: true`**（`user_layer_can_disable_ent_entry = true`）。也就是说「预置」成立，但「**不可被禁用**」**不成立**。
5. **因此按需求书 §5.4 第 6 条与 DG-13 处置**：
   - **未获批准前硬要求继续成立**（T-005 卡片原文）；
   - 本文件提交**降级申请**（§5），并给出 3 条缓解方案（§4），**不擅自改写需求书**；
   - 降级申请登记为 **C 类待批准**，不阻塞批次 1。

## 2. 取证来源与命令

| # | 目的 | 命令 |
| --- | --- | --- |
| 1 | 探针全量执行 | `python scripts/probe_bundle_preload.py`（结果 `11 [OK] / 0 [FAIL]`，退出码 0） |
| 2 | 组合树 bundle 段 | `$env:DSH_HOME=".dsh-check\t005"; node <dsh>\lib\bin.js --profile ent --dump-config` |
| 3 | 默认树（无用户层） | 同上，参数换 `--dump-default-config` |
| 4 | profile 与 bundle 模式 Schema | 同上，参数换 `--dump-config-schema` |
| 5 | 官方 bundle 声明样例 | `@deepseek-ai/dsh-base/package.json` 的 `dsh.bundle.patch`；`dsh-base/cordis.patch.yml` 的 `- insert:` 语义注释 |
| 6 | 第三方 先例 | `%APPDATA%\ThirdPartyApp\prod\harness\profiles\web\package.json`（`dsh.profile.bundles` + `link:`） |

**参照物声明**：探针使用的 dsh 运行时为**本机 第三方 内置副本 `0.1.7-alpha.2`（第三方打包产物）**，**不是**锁定基线 `dsh-v0.2.0-rc.1`（与 T-001 R-4 一致）。结论按「机制层面」使用；到 0.2.0-rc.1 上需在 T-023/T-029 复验。

## 3. 逐项判定表

### 3.1 预置机制（Step 1）

| # | 观察项 | 实测结果 | 判定 |
| --- | --- | --- | --- |
| P-1 | 企业 bundle 能否进入 profile bundle 段 | 组合树出现 `# == @worknexus/ent-core` 段 | **成立** |
| P-2 | 企业段顺序 | `base@0 → ent@1`（官方之后） | **成立** |
| P-3 | 用户层能否把它从 bundle 段摘除 | 默认树（不含用户层）中企业段仍在 | **不能摘除**（bundle 清单属 profile 层） |
| P-4 | 声明要求 | 必须 `dsh.bundle.patch`（缺失即 skip） | **成立**（新发现的硬约束） |
| P-5 | patch 语义 | `- insert:` 新增；`- id:` 覆盖 | **成立** |
| P-6 | `link:` 注入 | 需在 profile 的 `node_modules` 下可解析（探针用目录联接/复制模拟） | **成立**（与 第三方 先例一致） |
| P-7 | bundle 解析失败时的行为 | 只打印 `skipping profile bundle ...` **警告**，其余 profile 正常组合 | **失败隔离成立**（对 §5.4 是有利证据） |

### 3.2 protected 语义（Step 2）

| # | 观察项 | 实测结果 | 判定 |
| --- | --- | --- | --- |
| R-1 | 用户层能否 disabled 企业条目 | 写入用户层 `cordis.patch.yml`（`- id: ent-core-probe` + `disabled: true`）后，组合树中该行变为 disabled | **能** |
| R-2 | 官方原生恢复对话框的行为 | **未测**（需真机 GUI 与故障注入，见 §6 B-1） | **未验证** |
| R-3 | `protected` 是否被 Loader 识别为保护位 | **未观察到保护语义**：探针声明了 `dsh.protected` / `dsh.hostInfrastructure`，行为与未声明时一致 | **未证实** |

**关键判断**：R-1 说明**「条目可被禁用」这一风险至少在用户层已成立**。原生恢复流程是否也把企业 bundle 列为「可禁用的第三方 bundle」仍属未验证（B-1）；但只要「任意一层可禁用」，需求书 §5.4 第 6 条的硬要求就无法仅靠 bundle 预置满足。

## 4. 缓解方案（Step 3）

按有效性排序，供 T-023/T-029/T-035 与 DG-13 决策使用：

| # | 方案 | 做法 | 有效性 | 代价 |
| --- | --- | --- | --- | --- |
| M-1 | **bundle 段预置 + 契约骨架常驻** | 企业 bundle 进 `dsh.profile.bundles`（已实测可行）；Host Core 契约骨架作为 bundle 内 `- insert:` 的最小行集 | 保证「预置存在」与「失败隔离」 | 低（本方案即当前计划） |
| M-2 | **企业入口的存在性校验 + 一次性恢复入口** | 客户端启动时校验企业 bundle 段是否完整；缺失/被禁用时，给**一次性恢复入口**（重建 profile 的企业 bundle 段），且**不丢企业数据** | 覆盖 R-1 风险：用户或恢复流程关掉后仍可恢复 | 中（需 T-023 实现 + T-052 验证） |
| M-3 | **企业功能与官方会话解耦** | 企业侧能力（企业管理/知识库/DocGraph/IPD）全部落在企业插件内；即使入口被禁用，官方 DSH 会话与工作区**照常可用**（对齐 §3.5 第 4 条降级要求） | 把「被禁用」的后果降级为「企业功能不可见」而非「客户端不可用」 | 低（设计约束，随 P2 实施） |

**推荐组合：M-1 + M-2 + M-3**。其中 M-2 是**唯一直接对冲 R-1 的方案**，T-023 的 DoD 应包含它。

## 5. 降级申请（DG-13）

> 触发条件依据：需求书 §5.4 第 6 条 + 总览 DG-13——「T-005 若证明『内置 bundle 不被原生恢复禁用』不可行，必须提交降级申请并获**决策人批准**」。

**申请内容**（**仅申请，尚未生效**；未获批准前硬要求继续成立）：

1. 把 P1-F16 与需求书 **§4.1.5 第 8 条**改写为：
   > 「企业 bundle 随发行版预置在 profile 的 bundle 段；**被禁用/缺失时提供一次性恢复入口，且不丢企业数据**」。
2. 同步登记到 **需求书 §13.4** 与 **`内部准入评审记录` 决策变更区**。

**批准状态**：**待批准（C 类）**。批准人未指定（见 §6 C-1）。

## 6. 未验证项与边界

**需真机复核（B 类）**

- B-1：**官方原生恢复对话框是否把企业预置 bundle 列为「可禁用的第三方 bundle」**。缺什么：可运行的桌面端 + 故障注入（README 第 81/139 行指出恢复流程使用 `$DSH_HOME/profiles/desktop`）。怎么补：T-020 构建完成后，注入一次 Host 启动失败并观察恢复对话框。影响哪条验收：**§4.1.5 第 8 条**（Host Core 不可拆卸）。
- B-2：`protected` 是否在 0.2.0-rc.1 上有 Loader 级保护语义（本探针在 0.1.7-alpha.2 上未观察到）。
- B-3：真实 `pnpm link`/`link:` 安装路径下的解析行为（探针用目录联接模拟；T-023 需用真实安装复验）。

**需外部输入（C 类）**

- C-1：**降级申请的批准人**。缺什么：决策人角色确认。怎么补：由用户明确。影响哪条验收：§4.1.5 第 8 条的口径。
- C-2：企业 bundle 的最终命名与命名空间（探针用 `@worknexus/ent-core` 占位）。怎么补：T-031 企业插件声明规范定稿时确定。

**超出本次范围**

- O-1：不实现企业 bundle 的实体内容（归 T-023/T-029）。
- O-2：不测企业数据在禁用后的保留行为（归 T-023/T-052）。

## 7. 对后续任务的约束

1. **T-023**（企业 bundle 预置与失败隔离）：必须落实 **M-2**（存在性校验 + 一次性恢复入口 + 不丢数据），并在 DoD 中包含「禁用后恢复」断言；bundle 必须声明 `dsh.bundle.patch`，patch 用 `- insert:`。
2. **T-029**（Host Core 契约骨架 bundle）：包名与命名空间待 T-031 定稿；骨架必须是**预置 bundle**（不得依赖用户安装外部插件，§3.2 落地约束）。
3. **T-031**（企业插件声明规范）：必须包含 `dsh.bundle.patch` 声明要求、`protected` / `host-infrastructure` 字段的**启用与否**说明（本探针未证实其保护语义，规范需按「声明即文档」处理，不得声称有强制力）。
4. **T-035**（运行模式门控）：个人模式隐藏企业入口（G16）与 M-3 一致；不得因为企业侧被禁用而影响官方会话。
5. **T-052**（插件治理与失败隔离验证）：把「企业条目被 disabled → 恢复入口可用 → 企业数据不丢」列为断言。
6. **T-012**：DG-13 登记为「申请已提交、待批准」；**未获批准前，§4.1.5 第 8 条按硬要求执行**。

## 8. 复现命令

```powershell
cd "<repo-root>"
python scripts/probe_bundle_preload.py          # 期望 11 [OK] / 0 [FAIL]，退出码 0
Get-Content -Raw ".dsh-check\t005-probe-summary.json"
# 手工复核两个树的差异
$h = "$env:APPDATA\ThirdPartyApp\prod\harness\profiles\node_modules\@deepseek-ai\dsh\lib\bin.js"
$env:DSH_HOME = "$PWD\.dsh-check\t005"
node $h --profile ent --dump-default-config | Select-String "# =="
node $h --profile ent --dump-config         | Select-String "# =="
```
