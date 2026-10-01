# 企业 bundle 预置与失败隔离（T-023）

> 任务：T-023 企业 bundle 预置与失败隔离 ｜ 批次 1 ｜ 依赖 T-021、T-005 ｜ 无人值守度 B
> 执行日期：2026-09-29 ｜ 门禁：`python scripts/verify_t023_bundle.py` = **9 [OK] / 0 [FAIL]**

## 1. 结论先行

1. **企业基座 bundle 已落地并可被真实装配**：`bundles/ent-core` 作为第一方 bundle 包，在隔离 DSH_HOME 下被参照 dsh 装配成独立 bundle 段——组合树实测为
   `['@deepseek-ai/dsh-base', '@worknexus/ent-core']`，**企业段位于官方段之后**，退出码 0。
2. **T-005 的两条硬约束已内建**：`package.json` 声明 `dsh.bundle.patch`（缺失即被 skip）；`cordis.patch.yml` 只用 `- insert:`（直写 `- id:` 会报 `patch: entry … not found`）。两条都写进了包内 README 与门禁 B2/B3。
3. **「预置」成立、「不可拆卸」是行为性保障而非标记**：企业 bundle 段出现在 `--dump-default-config`（profile 层，用户层无法摘除）；但 `dsh.protected` / `dsh.hostInfrastructure` **仍未证实有 Loader 强制力**，因此不宣称强制保护。
4. **失败隔离双路径均通过**：
   - **解析失败**：一行指向不存在的模块时，`dsh` 只打印 `skipping …` 警告，**退出码仍为 0**，官方段完整；
   - **启动失败**：启用故意抛错的 `@worknexus/ent-core/failing` 后，装配仍成功，官方段与企业段均在。
   （以上为**装配层**证据；Boot 层隔离需真机 Electron，登记为 B-1。）
5. **一次性恢复入口已实现**：`scripts/verify_t023_bundle.py --restore <DSH_HOME>` 只重写 `dsh.profile.bundles`（官方在前、企业在后），**不动会话/设置/凭据/工作区**；门禁 B8 用「破坏 → 恢复 → 校验其他数据仍在」证明了这一点。这正对应 T-005 的缓解方案 **M-2**。
6. **失败隔离的代价可控**：`ent-core` 的插件入口刻意做成**零依赖、零副作用**（不注册服务、不订阅事件、不改官方行为），因此企业侧被禁用时官方会话链路不缺失任何依赖（T-005 M-3）。

## 2. 改动清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `bundles/ent-core/package.json` | 新增 | bundle 声明：`dsh.bundle.patch`、`dshCompatibility`、`protected`/`hostInfrastructure` 标注 |
| `bundles/ent-core/cordis.patch.yml` | 新增 | 两行 `insert`：`ent-core-skeleton`（T-029 契约骨架挂载点）+ `ent-core-health` |
| `bundles/ent-core/index.js` | 新增 | 健康探针插件（零副作用；不接控制面、不载业务数据） |
| `bundles/ent-core/skeleton.js` | 新增 | Host Core 契约骨架挂载点（T-029 接入 `packages/contracts`） |
| `bundles/ent-core/failing.js` | 新增 | 故意失败的插件，**不随发行版启用**，仅供失败隔离门禁 |
| `bundles/ent-core/README.md` | 新增 | 包内手册：硬约束表、失败隔离说明、`protected` 真相、恢复入口 |
| `scripts/verify_t023_bundle.py` | 新增 | 门禁 B1~B8（含真实探针）+ `--restore` 恢复入口 |
| `docs/企业bundle预置_T-023.md` | 新增 | 本文件 |

**差异集条目**：本次**未改动上游文件**（`bundles/`、`scripts/` 均在我方仓库），差异集为空。

## 3. 验证证据表

| # | 断言 | 原始输出 | 判定 |
| --- | --- | --- | --- |
| V-1 | B1 包结构 | 缺项 = 无（6 个文件齐备） | 通过 |
| V-2 | B2 `dsh.bundle.patch` 声明与落点 | `./cordis.patch.yml` 存在 | 通过 |
| V-3 | B3 patch 语义 | 使用 `- insert:`；本包 id = `['ent-core-skeleton','ent-core-health']`；不引用官方行 id | 通过 |
| V-4 | B4 组合树（真实探针） | `['@deepseek-ai/dsh-base', '@worknexus/ent-core']`，exit 0 | 通过 |
| V-5 | B5 默认树含企业段 | 出现在 `--dump-default-config` | 通过 |
| V-6 | B6 解析失败隔离 | 退出码 0；官方段仍在；输出含 `skipping` 警告 | 通过 |
| V-7 | B7 启动失败隔离（装配层） | 退出码 0；官方段与企业段均在 | 通过 |
| V-8 | B8 恢复入口 | 破坏后恢复为 `['@deepseek-ai/dsh-base','@worknexus/ent-core']`；`worknexus.{spaceId,orgId}` 原样保留 | 通过 |
| V-9 | 全量门禁 | `9 [OK] / 0 [FAIL]`，退出码 0 | 通过 |

**参照物声明**：探针使用的 dsh 为**本机 第三方 内置副本 `0.1.7-alpha.2`**（第三方打包产物），不是锁定基线 `dsh-v0.2.0-rc.1`（与 T-001 R-4、T-005 一致）。装配语义需在 0.2.0-rc.1 上复验（见 §4 B-2）。

## 4. 未验证项与边界

**需真机复核（B 类）**

- B-1：**Boot 层失败隔离**——真实 Electron 启动时某插件 `apply()` 抛错，Host Core 与官方会话是否仍可用。本次证据只到装配层（`--dump-config`）。缺什么：Electron 二进制 + GUI。怎么补：真机 `pnpm run dev:desktop` 后注入故障。影响哪条验收：**§4.1.5 第 8 条**（Host Core 不可拆卸）、§5.4（失败隔离）。
- B-2：在锁定基线 `dsh-v0.2.0-rc.1` 上复验 bundle 装配语义（`dsh.bundle.patch`、`- insert:`、bundle 段顺序）。缺什么：该版本的可运行 dsh（本次仅检出源码，未下 Electron 二进制）。怎么补：用检出构建出的 `apps/cli` 或真机发行版复跑 `--dump-config`。
- B-3：**原生恢复对话框是否把企业 bundle 列为可禁用第三方**（T-005 B-1 未测）。影响 §4.1.5 第 8 条。

**需外部输入（C 类）**

- C-1：企业 bundle 的最终命名与命名空间（当前 `@worknexus/ent-core` 为占位）。怎么补：T-031 企业插件声明规范定稿时确定。
- C-2：DG-13 降级申请的批准人（T-005 已提交申请）。

**超出本次范围**

- O-1：不实现八类契约的实体类型（归 T-029/T-030）。
- O-2：不实现企业管理 UI 形式的恢复入口（归 T-050）。
- O-3：不做安装包内 bundle 的打包与签名（归 T-028）。

## 5. 裁决记录

| # | 裁决：<决定> — <理由> — <错判代价> |
| --- | --- |
| R-1 | 企业 bundle 放我方仓库的 `bundles/ent-core`（新建 `bundles/` 顶层目录），而不是塞进上游树或 `packages/`——`repos/` 已忽略、上游树不入库；`packages/` 承载 npm 包（T-029 的 `packages/contracts`），而 bundle 是**发行物**而非库——若混在 `packages/`，后续 T-023/T-029 的边界会模糊（返工约 0.3 人日） |
| R-2 | 不宣称 `protected` 有强制力，改为「profile 层不可摘除 + 一次性恢复入口」——T-005 实测未观察到 Loader 级保护，且用户层可禁用条目——若宣称强制力，会形成虚假保证（合规与客户预期风险） |
| R-3 | 恢复入口做成**只重写 bundles 清单**的脚本，并在 T-050 前一直以脚本形态交付——需求要求「被禁用时提供一次性恢复入口且**不丢企业数据**」；只改 bundle 清单天然不触碰会话/设置/凭据/工作区——若写成「重建整个 profile」，会丢企业数据，直接违反需求 |
| R-4 | 失败隔离分「解析失败」与「启动失败」两条断言，且**只声明到装配层**——本次无法跑 Boot 层；把范围说清楚比含糊通过更有价值——若把装配层结论当成 Boot 层结论，会在真机出现未预期的阻断 |
| R-5 | `failing.js` 随包交付但**不写进** `cordis.patch.yml`——它必须存在（门禁要用），但绝不能随发行版启用——若误启用，企业客户端启动即抛错 |

## 6. 复现命令

```powershell
cd "<repo-root>"
python scripts/verify_t023_bundle.py

# 单看组合树
$env:DSH_HOME = "$PWD\.dsh-check\t023"
$bin = "$env:APPDATA\ThirdPartyApp\prod\harness\profiles\node_modules\@deepseek-ai\dsh\lib\bin.js"
node $bin --profile ent --dump-config | Select-String "# =="

# 恢复入口（只重写 bundles 清单）
python scripts/verify_t023_bundle.py --restore "$PWD\.dsh-check\t023"
```

## 7. 下一步

1. **T-024**（企业入口挂载）：入口注册必须走运行模式判定；P1 只交付个人模式，**四个企业入口必须隐藏且不报错**。
2. **T-029**（契约骨架）：`packages/contracts` 的八类契约类型接入 `bundles/ent-core/skeleton.js` 的挂载点。
3. **T-052**（插件治理与失败隔离验证）：把「企业条目被 disabled → 恢复入口可用 → 企业数据不丢」升级为验收断言，并补 Boot 层证据（B-1）。
