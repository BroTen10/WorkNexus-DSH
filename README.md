# WorkNexus-DSH

> 基于官方 **DSH（DeepSeek Harness）** 桌面端的企业办公套件发行版：客户端壳与内核行为跟随官方，本仓库只承载「**企业发行版 + 企业插件层**」。

WorkNexus-DSH 不是对 DSH 内核的替代实现。进程与运行时管理、profile 初始化、插件装载与生命周期、更新与恢复、诊断、凭据存储、会话交互一律采用官方设计；企业侧能力通过**差异集补丁**与**独立插件包**叠加，且每一处上游改动都必须落在白名单内、可枚举、可回滚。

## 设计原则

| 原则 | 含义 |
| --- | --- |
| **上游优先（G0）** | 需求与官方实现冲突时以官方为准，并在需求书登记让位原因 |
| **白名单差异** | 上游代码只允许改产品名与标识、品牌素材、欢迎页/关于页文案、更新源与通道、签名与流程、预置 bundle 清单、企业侧默认配置、企业侧页面入口 |
| **禁止改动** | 会话执行、工具调用、插件加载、更新算法、恢复策略、安全基线 |
| **差异可核验** | `git diff --stat` 与差异集清单不一致即视为任务失败 |

## 能力概览

- **企业发行版**：桌面端品牌化（产品名、图标、窗口标题、关于页）、企业更新源与通道、企业 bundle 预置、安装身份与签名流程。
- **Host Core 契约层**：身份、权限、空间、审计、用量、事件总线、运行模式门控、模型与凭据策略的统一契约。
- **企业插件层**：知识库、文档审查（DocGraph Adapter）、IPD 流程与项目视图、ACP 治理、插件市场治理、企业管理后台。
- **控制面服务**：FastAPI + PostgreSQL 的成员/角色/空间、审计与用量、预算策略、报表、后台任务、插件市场审批与版本锁定。
- **工程门禁**：59 个单任务真机门禁脚本 + 拆分自洽门禁，逐项输出 `[OK]`/`[FAIL]`，出现任一 `[FAIL]` 即退出码 1。

## 仓库结构

| 目录 | 用途 |
| --- | --- |
| `apps/` | 应用层（桌面发行版入口、Web 主链路相关） |
| `bundles/` | 企业预置 bundle（`ent-core`：默认 profile 组合与模型策略） |
| `configs/` | 企业侧默认配置与更新源模板（`*.env.example`，真实取值不入库） |
| `packages/` | 内部共享包：`contracts` / `host-core` / `kernel-dsh` / `plugin-runtime` / `ent-diagnostics` / `ent-entries` |
| `plugins/` | 企业业务插件：`knowledge` / `docgraph` / `ipd` / `acp` / `market` / `enterprise-admin` |
| `patches/` | 上游差异集补丁（01~08）+ 逐集 `git diff --stat` |
| `scripts/` | 门禁、校验、打包与探针脚本 |
| `services/api` | 控制面服务（FastAPI / SQLAlchemy / Alembic / pytest） |
| `docs/` | 需求、任务拆分、技术决策、交付说明与真机验收证据 |
| `repos/` | 本地上游检出（**不入库**，仅保留 `.gitkeep` 占位） |

## 环境要求

- Node.js `>= 24`，pnpm `11.25.0`（仓库声明 `packageManager`）
- Python `>= 3.11`（门禁脚本与控制面服务）
- Windows + PowerShell（桌面端出包链路的当前验证环境）

## 快速开始

```powershell
# 1) 安装工作区依赖
pnpm install

# 2) 类型检查 / 构建 / 单元测试
pnpm typecheck
pnpm build
pnpm test

# 3) 拆分自洽门禁（8 项检查，退出码 0 为通过）
python scripts/check_task_split.py --stats
```

控制面服务：

```powershell
cd services/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest
```

## 质量门禁

每个任务对应一个真机门禁脚本，形态统一：先探活、再跑探针、逐项打印 `[OK]`/`[FAIL]`，只要出现一处 `[FAIL]`，退出码即为 1。

```powershell
python scripts/verify_t025_model_policy.py     # 企业凭据与模型策略
python scripts/verify_t023_bundle.py           # 企业 bundle 预置
python scripts/verify_t107_client_brand.py     # 客户端品牌残留与打包冒烟
python scripts/check_task_split.py --stats     # 任务拆分自洽（8 项）
```

测试框架约定：`packages/*`、`plugins/*` 使用 **Vitest**；`services/api` 使用 **pytest**。上游既有测试不得删除或跳过。

## 上游跟随

- 锁定对象是上游桌面发行版的 tag（首个基线 `dsh-v0.2.0-rc.1`，当前 `dsh-v0.2.0-rc.2`）。
- 每个上游正式版本至少做一次 rebase/同步演练，不长期分叉。
- 上游只通过 `patches/diffset-*.patch` 以补丁形式改动，逐集登记文件数与字节数，便于审计与回滚。

## 文档入口

唯一入口是 [`docs/开发文档索引.md`](docs/开发文档索引.md)。常用基线：

- 需求基线：[`docs/WorkNexus-DSH-需求说明书-v1.2.md`](docs/WorkNexus-DSH-需求说明书-v1.2.md)
- 差异集：[`docs/差异集清单.md`](docs/差异集清单.md)
- 契约：[`docs/HostCore契约-v1.md`](docs/HostCore契约-v1.md)
- 技术决策：`docs/技术决策-*.md`
- 任务交付说明：`docs/<任务名>_T-<编号>.md`（固定六段：结论先行 / 改动清单 / 验证证据表 / 未验证项与边界 / 复现命令 / 下一步）

企业内部的任务拆分、派发卡、执行账本、真机验收记录与证据、演练与迁移记录、历史归档不随公开发布。

## 开发约定

提交与改动纪律见 [`AGENTS.md`](AGENTS.md)：每任务一次提交、中文提交信息、上游改动单独提交并标注差异集编号、交付说明固定六段。

## 许可证

[MIT](LICENSE)。上游 DSH 组件遵循其自身许可（MIT），本仓库对上游的改动以补丁形式显式登记。
