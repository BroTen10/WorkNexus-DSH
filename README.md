# WorkNexus-DSH（个人版宿主）

> 基于官方 **DSH（DeepSeek Harness）** 桌面端的个人版宿主仓：保留客户端壳、品牌与安装器差异集、基础 profile、插件市场与三个预置插件；企业 bundle、企业插件与控制面不在本仓。

WorkNexus-DSH 不是对 DSH 内核的替代实现。进程与运行时管理、profile 初始化、插件装载与生命周期、更新与恢复、诊断、凭据存储、会话交互一律采用官方设计；个性化差异只落在品牌、安装器、更新源与预置清单等白名单内，并以可枚举、可回滚的补丁形式登记。

## 设计原则

| 原则 | 含义 |
| --- | --- |
| **上游优先（G0）** | 需求与官方实现冲突时以官方为准，并在决策文档登记让位原因 |
| **白名单差异** | 只改产品名与标识、品牌素材、欢迎页/关于页文案、更新源与通道、签名与流程、预置 bundle 清单、个人侧默认配置与页面入口 |
| **禁止改动** | 会话执行、工具调用、插件加载、更新算法、恢复策略、安全基线 |
| **差异可核验** | `git diff --stat` 与差异集清单不一致即视为任务失败 |

## 本仓包含

| 目录 | 用途 |
| --- | --- |
| `apps/desktop/` | 桌面壳补丁落点（身份装配、profile 补齐等） |
| `patches/` | 对上游的差异集补丁（品牌、安装器、更新、profile 清理、第三方声明） |
| `scripts/` | 个人版出包、预置包取回、品牌素材、门禁 |
| `configs/` | 桌面更新源与第三方预置锁文件 |
| `docs/` | 个人版文档、交付说明与决策记录 |
| `repos/` | 上游检出（**不入库**，仅保留 `.gitkeep` 占位） |

本仓**不包含**：企业 bundle、企业插件、HostCore 契约、控制面服务。这些在独立的 `WorkNexus-Enterprise` 仓中维护，企业版使用独立的 `worknexus-enterprise` profile。

## 环境要求

- Node.js `>= 24`，pnpm `11.28.5`
- Python `>= 3.11`
- Windows + PowerShell（桌面端出包链路的当前验证环境）

## 快速开始

```powershell
# 取回 dshmarket + 三个预置插件及其闭包（86 个 tgz）
python scripts/pack_presets.py

# 出包前置检查（不执行打包）
python scripts/package_desktop_win_unsigned.py --dry-run

# 个人版宿主门禁与插件市场更新门禁
python scripts/verify_t143_personal_only.py
python scripts/verify_t126_plugin_update_path.py
```

上游桌面壳回归在本地 `repos/deepseek-harness` 内执行：

```powershell
cd repos\deepseek-harness
corepack pnpm run typecheck
corepack pnpm run lint
corepack pnpm run test
```

## 出包

```powershell
python scripts/pack_presets.py
python scripts/package_desktop_win_unsigned.py
```

产物位于 `repos\deepseek-harness\apps\desktop\.desktop-build\targets\win-x64\unsigned-artifacts\`。当前 Windows 产物为 `worknexus-dsh-0.2.1-rc.2-win-x64-unsigned.exe`。

## 质量门禁

仓库当前有 **14 个可复跑门禁脚本**：9 个任务/宿主门禁（T-020 / T-021 / T-022 / T-027 / T-107 / T-108 / T-125 / T-126 / T-143）与 5 个差异集门禁（09 / 11 / 12 / 13 / 14）。统一形态为：先探活、再跑探针、逐项输出 `[OK]`/`[FAIL]`，出现任一 `[FAIL]` 即退出码 1。

```powershell
python scripts/verify_t143_personal_only.py
python scripts/verify_t126_plugin_update_path.py
python scripts/verify_diffset14_third_party_notices.py
```

预置包与声明相关脚本：

```powershell
python scripts/pack_presets.py --verify-only
python scripts/fetch_third_party_bundles.py --verify-only
python scripts/gen_worknexus_notices.py --check
```

## 上游跟随

- 锁定对象：官方桌面发行版 tag（当前基线 `dsh-v0.2.1-rc.2`，提交 `687f282e`）。
- 每个上游正式版本至少一次 rebase/同步演练，不长期分叉。
- 上游改动只通过 `patches/diffset-*.patch` 以补丁形式进入本仓，逐集登记文件数与字节数，便于审计与回滚。

## 第三方组件与合规

本发行版在官方 bundle 之外预置了插件市场 `dshmarket`（当前 **1.66.42**）与三个市场插件（`dsh-better-sidebar` 0.25.0、`dsh-claude-style` 0.13.2、`@linxin666/dsh-client-ui-skill-explorer` 0.4.6），并随包提供运行依赖 `undici` 7.29.1。

上游生成的 `THIRD_PARTY_NOTICES.md` 只扫上游 workspace，不覆盖以 tgz 分层预置的组件；本发行版另附根文件 `WORKNEXUS-THIRD-PARTY-NOTICES.md`（差异集 14），内容由 `scripts/gen_worknexus_notices.py` 从 `configs/vendor/third-party-bundles.lock.json` 与 `configs/vendor/licenses/*` 确定性生成，并随安装包落盘到 `resources/`。

## 文档入口

唯一入口是 [`docs/开发文档索引.md`](docs/开发文档索引.md)。常用文档：

- 差异集：[`docs/差异集清单.md`](docs/差异集清单.md)
- 插件市场跟版：[`docs/插件市场跟版_1.66.42_T-144.md`](docs/插件市场跟版_1.66.42_T-144.md)
- 插件市场更新修复：[`docs/插件市场更新失败修复_T-126.md`](docs/插件市场更新失败修复_T-126.md)
- 个人版宿主清理：[`docs/个人版宿主清理_T-143.md`](docs/个人版宿主清理_T-143.md)

企业内部的任务拆分、派发卡、执行账本、真机验收记录与证据、演练与迁移记录、历史归档不随公开发布。

## 开发约定

提交与改动纪律见 [`AGENTS.md`](AGENTS.md)：每任务一次提交、中文提交信息、上游改动单独提交并标注差异集编号、交付说明固定六段。

## 许可证

[MIT](LICENSE)。上游 DSH 组件遵循其自身许可（MIT），本仓库对上游的改动以补丁形式显式登记。
