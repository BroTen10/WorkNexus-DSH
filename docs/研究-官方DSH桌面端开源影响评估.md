# 研究：官方 DSH 桌面端开源对 WorkNexus-DSH 需求与任务的影响

| 项目 | 内容 |
| --- | --- |
| 研究日期 | 2026-09-28 |
| 触发来源 | 公众号「开源工具社」2026-09-26 16:02 《DeepSeek 官方出 Harness 桌面客户端了！附下载地址》 |
| 研究问题 | 官方是否已开源桌面客户端？如是，需求说明书与 71 个任务是否需要同步调整？ |
| 研究结论 | **需要调整，且属于基线性调整**：P1 的 15 个任务中有 10 个与上游重叠，建议把「自研 Electron 壳」改为「以上游桌面端为基线的企业发行版 + 企业插件层」 |
| 本文档状态 | 研究结论 + **DG-9 已决策**（2026-09-28）。需求说明书已升 v1.1、任务拆分已升 v2.0 并完成同步；决策记录见第 12 节 |

---

## 1. 结论先行

1. **文章属实，但已经滞后。** 官方桌面端确实在开源仓库里：`deepseek-ai/deepseek-harness` → `apps/desktop`，包名 `@deepseek-ai/dsh-desktop`，许可证 MIT，自述为「Electron desktop shell for a bundled dsh runtime and external plugins」。文章说最新是 `0.1.7-rc.2`（09-24），但**今天 2026-09-28 12:36 已发布 `dsh-v0.2.0-rc.1`，桌面安装包 12:57 已上传**。
2. **需求与任务需要同步调整，而且不是微调。** 我方 P1 计划里 T-011、T-012、T-014、T-015、T-016、T-017、T-018、T-019、T-021、T-023 这 10 个任务的目标，上游桌面端已经实现（含 Electron 安全基线、单实例、内置 Node/pnpm/Python、profile 初始化、更新协调、强制更新策略、崩溃恢复、诊断导出、目录选择、会话全链路）。按需求书自身「成熟度优先」「不重复建设」的原则，这些应当改为复用而非重写。
3. **P2 仍然成立，是真正的新增工作。** 上游 `packages/identity` 只是「每个 harness home 一个匿名关联 id，供遥测/反馈/DeepSeek 请求使用」，**没有组织、部门、项目空间、角色、审计、预算**这套企业体系。P2 的八类 Host Core 契约与企业管理插件不重复。
4. **文章有两处需要打折。** 其一，账号登录：仓库 README 的 Known limitations 原文写着 **"Account sign-in is not connected; the Sign in button is disabled."**，与文章「可以登录看余额用量充值」冲突，需实测安装包确认。其二，「7 个官方插件」与「输入 GitHub 仓库地址安装第三方插件」未在 README 中逐项确证，只能确认上游确有插件管理器与 Web 侧栏 Plugins 入口。
5. **同步已完成（2026-09-28）。** DG-9 拍板为「薄 fork + 严格跟随官方」后，需求说明书已升 v1.1、任务拆分已升 v2.0；`内部历史归档` 与两份旧计划文档保留为历史基线（并非未改动）。逐条改动依据见第 5、6 节，落地结果见第 12 节。

---

## 2. 核查方法与取证清单

所有取证在 2026-09-28 完成，只读。

| 取证项 | 方式 | 结果 |
| --- | --- | --- |
| 文章正文 | `curl` 抓取 `mp.weixin.qq.com/s/CwiNLFV9txARS6jWUYHX0A`，解析 `js_content` | 拿到全文 999 字，标题与账号名、发布时间已确认 |
| 官方仓库 | GitHub API `repos/deepseek-ai/deepseek-harness` | 存在；MIT；TypeScript；created 2026-08-13；pushed 2026-09-28 12:35 UTC；描述 "DeepSeek Harness: Everything is a Plugin."；homepage `https://deepseek.com/harness`；stars 238,520 / forks 28,654；topics：ai-agents, cordis, dsh, dsh-plugin |
| 仓库结构 | GitHub contents API：`/`、`/apps`、`/packages`、`/python`、`/docs` | monorepo；`apps/` = `cli`、**`desktop`**、**`desktop-host`**、`web`；`packages/` 约 60 个能力包 |
| 桌面端包信息 | `apps/desktop/package.json` | `@deepseek-ai/dsh-desktop`，version **0.2.0-rc.1**，license MIT，deps 含 `electron-updater ^6.8.9`；devDeps 含 `electron ^44.0.0`、`electron-builder ^26.15.3`、`pnpm 11.7.0` |
| 桌面端实现面 | `apps/desktop/src` 目录清单 | 含 `main.ts`(66KB)、`host-process.ts`、`runtime-tree.ts`、`single-instance.ts`、`tray.ts`、`crash-report.ts`、`fatal-recovery.ts`、`project-manager.ts`、`directory-picker.ts`、`account-backend.ts`、`update-coordinator.ts`、`update-journal.ts`、`update-schedule.ts`、`mandatory-update-policy.ts` 等 |
| 桌面端设计说明 | `apps/desktop/README.md`（108KB） | 「Key technical decisions」决策表、Installation ownership、Runtime and plugin activation、Updates、Known limitations 等章节（关键句见第 3 节） |
| 发布情况 | GitHub releases API | `dsh-v0.2.0-rc.1`（2026-09-28 12:36）、`dsh-v0.1.7-rc.2`（09-24）、`dsh-v0.1.7-rc.1`（09-23）、`dsh-v0.1.7-alpha.2`（09-22）等，**全部为 prerelease，且 assets=0**（安装包不在 GitHub，在官方下载域名） |
| 安装包真伪 | `curl -I` 官方下载域名 | win-x64 `0.1.7-rc.2` 返回 200，288,245,480 字节，Last-Modified 2026-09-24；win-x64 `0.2.0-rc.1` 返回 200，Last-Modified 2026-09-28 12:57；mac-arm64 `0.1.7-rc.2` dmg 返回 200 |
| 插件管理能力 | `packages/boot/plugin-manager/README.md`、`packages/client/ui-plugin-manager/README.md` | 官方插件管理器：启停插件条目、选择已安装 bundle、安装/移除外部 bundle，走内置 pnpm；Web 侧栏有 **Plugins** 入口 |
| 上游身份能力 | `packages/identity/README.md` | 只是匿名 harness-home 关联 id，供 telemetry/feedback/DeepSeek 请求使用，**不含企业组织体系** |
| 许可与品牌 | `LICENSE`、`BRAND_GUIDELINES.md` | MIT，Copyright (c) 2026 DeepSeek；品牌指引推荐用缩写 **DSH** 命名相关项目，**禁止在项目名里直接使用 "DeepSeek Harness" 全称商标**，允许在描述中写「built on DeepSeek Harness / compatible with DeepSeek Harness」 |
| 本机第三方参照 | `%APPDATA%\ThirdPartyApp\prod\harness\profiles\web\package.json` | 第三方厂商（第三方）正是用 `bundles: [@deepseek-ai/dsh-base, @deepseek-ai/dsh-web-app, lychee-workbench]` + `link:` 注入自有第一方 bundle，证明「厂商预置自有 bundle」路线可行 |

---

## 3. 文章说法逐条核查

| 文章说法 | 判定 | 依据 |
| --- | --- | --- |
| DeepSeek Harness 官方出了桌面客户端，在开源仓库里 | **成立** | `apps/desktop` = `@deepseek-ai/dsh-desktop`，MIT |
| 从下载域名找到更新清单和安装包 | **部分成立** | 安装包 200 可下；但在 `dsh-desk/bin/win-x64/` 下未找到 `latest.yml` / `latest.json`（均 404），「更新清单」文件路径未证实 |
| Windows 和 Apple 芯片 Mac 都能直接安装 | **成立** | win-x64 exe 与 mac-arm64 dmg 均 200；上游脚本另有 mac-x64 目标但未在下载目录证实发布 |
| 最新版本是 0.1.7-rc.2 | **已过期** | 2026-09-28 12:36 发布 `dsh-v0.2.0-rc.1`，12:57 上传对应 win-x64 安装包 |
| 已把 Node.js、pnpm 和 Python 运行环境打包进去，无需预装 | **成立** | README：「Desktop carries independent Python, Node.js and pnpm distributions」「The application must run without a system Node.js or pnpm installation」 |
| 桌面端和网页版共用同一套前端，也读写同一个 `~/.dsh` | **基本成立，需精确表述** | README：桌面端是「完整 dsh Web 应用的 Electron 壳」；「shares sessions, settings, credentials, workspaces, and storage under `$DSH_HOME`」，但**可执行包、插件激活、lockfile、node_modules 刻意分离** |
| 左侧新增「插件」入口，含 7 个官方插件 | **部分成立** | 确认存在 Web 侧栏 Plugins 入口（`ui-plugin-manager`）与插件管理器；「7 个」未逐项清点，未确证 |
| 可输入 GitHub 仓库地址安装第三方插件 | **未证实** | README 只说明「安装/移除外部 bundle」；是否接受 GitHub URL 需实测 |
| 左下角可登录 DeepSeek 账号，查看余额、用量、充值，登录后多一组模型 | **与官方文档冲突** | `apps/desktop/README.md` Known limitations 原文：**"Account sign-in is not connected; the Sign in button is disabled."**（README 同时描述了完整的浏览器 PKCE 登录流程与用量/充值嵌入页设计，属「已设计未接通」） |
| 目前是实验版本，官方没有正式公告，不建议当主力 | **成立** | 所有 release 均为 prerelease；README 明确签名、公证、更新托管、上一版本安装产物验证都「require the production release environment」 |

---

## 4. 官方桌面端的关键事实（决定需求调整的那几条）

以下均为 `apps/desktop/README.md` 原文要点，括号内为原文关键词。

**4.1 架构与承载方式**
桌面端是「完整 dsh Web 应用的 Electron 壳」：Electron 以 RunAsNode 子进程启动共享 profile runner，立即加载打包后的 Web 入口 `dsh-app://app/`；Electron 把应用 HTTP 请求转发到带鉴权的 Web Host，并丢弃连接级响应头、对插件 bundle 响应标 `no-store`；WebSocket 只在自有窗口附带凭证；Node IPC 承载 boot injections、就绪与关闭。**桌面端默认端口 19387，Web 默认 3080**，可用 `webserver.config.port` 补丁覆盖。
→ 我方 T-003 里「路线 A 加载本地 dist / 路线 B 加载带 token 的 localhost URL」这个二选一已经由上游确定，不需要我方再选。

**4.2 状态所有权与隔离**
Electron 在**任何 profile 访问之前**取得进程级单实例锁，并**独占 `$DSH_HOME/profiles/desktop`**。CLI 与桌面端共享 `$DSH_HOME` 下的会话、设置、凭证、工作区与存储，但**不共享可执行包、插件激活、lockfile、node_modules**。
→ 我方原计划「私有 harness 目录 `<userData>/harness`」需要改为对齐上游的 `$DSH_HOME` 语义，否则会与官方客户端抢同一份数据。

**4.3 内置运行时**
桌面端自带相互独立的 Python / Node.js / pnpm 发行版（Python 含 numpy、pandas、python-docx、python-pptx、openpyxl、Pillow、lxml、XlsxWriter 等），首次使用时离线安装到 `$DSH_HOME/dsh-runtimes/dsh-primary-runtime`。dsh 在 Electron 下以 `ELECTRON_RUN_AS_NODE=1` 运行；`app.asar/dsh` 携带完整生产依赖树，**profile 只安装外部插件**；核心包「never copied into profile storage or installed by pnpm at first launch」。
→ 我方 T-011（DSH 内核承载 / 内置）与 T-012（进程生命周期）的目标已被上游完整覆盖。

**4.4 更新模型**
「The Electron shell, matching dsh runtime and pnpm form one signed update unit」、「A dsh upgrade is a Desktop release, even when the shell code is unchanged」、「Electron and `@deepseek-ai/dsh` always have the same exact version」。实现上有更新协调器、更新日志（journal）、更新排期、**强制更新策略**（mandatory update policy）、本地更新资格验证脚本；更新策略请求会额外上报架构、更新通道、内置运行时版本。签名走 Windows EV / macOS 公证，未签名构建只用于测试。
→ 我方 T-022（自动更新）与 T-023（升级恢复）应改为「复用上游更新机制 + 建设我方签名与更新托管」，而不是自研 updater。

**4.5 插件模型**
插件管理使用**共享的 Web Plugin Manager** 与内置 pnpm；桌面端**不暴露插件管理 IPC、也没有独立的插件管理文档**，插件管理走 Web 应用已鉴权的 HTTP API。profile 的 `dsh.profile.bundles` 是「内置 bundle 在前，已启用插件在后」。恢复动作可以「禁用第三方 bundle」并把 `cordis.patch.yml` 备份改名。
→ 直接冲击我方 P6B「复用 dshmarket」的假设：上游已有官方插件管理器，`dshmarket` 应降级为第三方生态参考而不是首选。更要紧的是：**如果我们的企业 bundle 被当作「第三方 bundle」，用户一次恢复动作就能把它禁用**——这与需求书「Host Core 不可拆卸」直接冲突，必须把企业 bundle 预置为内置 bundle。

**4.6 恢复与诊断**
致命错误（主窗口、主文档、preload、renderer、Web 初始化、后端启动失败）会弹出原生恢复对话框，提供退出 / 重启 /「禁用第三方插件 + 备份 profile patch + 重启」；崩溃报告写到平台日志目录，保留最近 10 份；Host stderr 只保留最后 64Ki 字符；`listen EADDRINUSE` 有专门的诊断替换文案。
→ 我方 T-021（本地诊断）与 T-023 的恢复部分，上游已实现，我方需要的是「企业侧上报与企业 bundle 的回滚」，不是重写。

**4.7 许可与品牌**
MIT（Copyright (c) 2026 DeepSeek），允许修改、再分发，条件是保留版权与许可声明。品牌指引：允许在描述中写「built on DeepSeek Harness / compatible with DeepSeek Harness」；**推荐用缩写 DSH 命名**；**禁止在项目名中直接使用 "DeepSeek Harness" 全称商标**，并禁止使用会造成官方背书误解的品牌素材。
→ 我方产品名 **WorkNexus-DSH 恰好符合品牌指引**（用了 DSH 缩写），这一点可以作为命名依据写进需求；同时必须在发行物中保留 MIT 声明与 `THIRD_PARTY_NOTICES`。

---

## 5. 对需求说明书的影响（逐节）

> 说明：本节与第 6 节的表格使用 **v1.0 计划的任务编号**（即改动提出时的编号），用于说明「哪一条为什么要改」；最终落地的编号与处置见第 12 节与总览 §3.1 编号迁移对照表。

| 规格章节 | 现状 | 建议改动 | 影响面 |
| --- | --- | --- | --- |
| §2.1 产品形态 | 「Desktop Shell 由我们负责」 | 改为「Desktop Shell 以上游 DSH Desktop 为基线，WorkNexus-DSH 负责企业发行版、企业插件层与控制面」 | 大 |
| §3.1 边界（WorkNexus-DSH 负责项） | 含「桌面客户端体验、自动更新与升级恢复」 | 这两项改由上游提供；我方负责**企业发行与分发、更新通道与签名、企业治理、控制面、业务插件** | 大 |
| §3.2 Host Core | 不可拆卸的八类契约 | 保留；但落地形态必须改为「随发行版预置的**内置 bundle** + profile 补丁」，因为签名版 `app.asar` 有完整性校验，不能靠改 `app.asar` 实现 | 中 |
| §4.1 P1 | 14 条需求、6 条验收，本质是「做出一个 DSH 桌面个人版」 | 改写为「基于官方桌面端构建 WorkNexus-DSH 企业发行版」：保留 F01 客户端安装、F11 更新、F12 恢复、F13 诊断、F14 密钥，但这几项的验收对象变成**我方发行版**而非自研壳 | 大 |
| §4.2 P2 | 企业管理插件 + 控制面 | 保留全部 12 条；新增「与上游凭据/账号/用量体系对齐，不另立第二套模型配置」的约束 | 小 |
| §4.6.2 P6B | 「优先复用 `dshmarket`」 | 改为「复用上游官方插件管理器（plugin-manager + Web Plugins 入口）」，`dshmarket` 降级为第三方生态参考；治理能力（白名单/审批/锁定/审计）作为其上层扩展 | 中 |
| §5.2 插件 Manifest | 自行定义最小字段集 | 不另立第二套插件系统；改为「上游 bundle/插件机制 + 企业治理扩展字段」 | 中 |
| §5.3 生命周期 | 自行实现安装/启用/禁用/升级/回滚/健康检查 | 改为复用上游 plugin-manager，并在其上加审计与治理；健康检查沿用上游失败上报 | 中 |
| §5.4 失败隔离 | 要求「插件失败不阻断 Host Core」 | 保留，并新增一条上游约束：企业 bundle 必须是内置 bundle，否则会被原生恢复动作禁用 | 中 |
| §6.4 AgentTransport | 自研内部适配层 | 保留接口语义，但实现优先复用上游 Web/API 能力与 `packages/acp`（P6A），不另造协议网关 | 小 |
| §8 复用策略 | 未列 DSH Desktop / plugin-manager / acp | 新增行：DSH Desktop（直接作为发行基线）、plugin-manager（插件治理挂接点）、`packages/acp`（P6A 实现）、`packages/api`（控制面边界参考） | 小 |
| §9 阶段计划 | P1 = 自建桌面客户端 | P1 工作量显著下降（自研壳部分消失），新增「企业发行版」定位；批次 0 增加 DG-9/DG-10/DG-11/DG-12 | 大 |
| §10 风险 | 未含上游同步风险 | 新增两条：上游迭代快导致 fork 分叉成本；上游尚处 rc/alpha，更新策略与签名依赖生产发布环境 | 中 |
| 新增需求（建议） | — | 「上游同步机制」（fork 策略、rebase 节奏、上游版本升级演练）、「品牌与许可合规」（MIT 声明、NOTICE、项目命名遵循 BRAND_GUIDELINES）、「企业 bundle 预置与 protected 验证」 | 新增 |

---

## 6. 对任务计划的处置建议（逐任务）

### 批次 0（P0 决策门）

| 任务 | 建议 | 理由 |
| --- | --- | --- |
| T-001 基线盘点 | **保留并扩展** | 增加「上游仓库与本机 第三方 版本差异」一项（本机 0.1.7-alpha.2 vs 上游 0.2.0-rc.1） |
| T-002 DG-1 版本锁定 | **改写** | 锁定口径从「DSH 版本」改为「上游桌面发行版版本」（当前 0.2.0-rc.1），并接受「壳与 dsh 版本恒等」规则 |
| T-003 DG-2 承载能力清单 | **缩减** | 承载方式已由上游确定（`dsh-app://app/`、端口 19387、HTTP 转发、WS 凭证）；改为核验上游机制 + 确认企业 bundle 注入点 |
| T-004 DG-3 用量字段 | **缩减** | 改为「上游 session 投影 + 账号用量能力 + telemetry」三条来源核对，去除自研推断部分 |
| T-005 DG-4 自动更新 | **改写** | 改为「我方更新通道与签名能力建设」：自有 EV 证书、自有更新源、通道策略；机制复用上游 electron-updater |
| T-006 / T-007 / T-008 | **保留** | 与桌面端无重叠 |
| **新增 DG-9** | **新增** | 客户端基线选择（见第 7 节） |
| **新增 DG-10/11/12** | **新增** | 版本口径、品牌与许可、更新通道与签名 |

### 批次 1（原 P1，重叠最严重）

| 任务 | 建议 | 理由（上游对应实现） |
| --- | --- | --- |
| T-011 DSH profile 初始化与版本校验 | **删除或降级为对齐任务** | 上游 shared profile initialization 已创建 manifest/空 patch/pnpm workspace，且校验 runtime descriptor |
| T-012 DSH 进程生命周期与健康检查 | **删除** | 上游 `host-process.ts`、`runtime-tree.ts` 已实现 Host 启停与就绪 |
| T-013 AgentTransport 适配层 | **缩减** | 会话能力由上游承载；我方仅在需要企业上下文的场景对接上游 API |
| T-014 Electron 主进程与窗口安全基线 | **删除** | 上游已有 `main.ts`、preload 隔离、`dsh-app://` 源、DevTools 策略、`<webview>` 租赁约束 |
| T-015 Web profile 承载与首屏 | **删除** | 上游已有 `dsh-app://app/` + 共享加载页 |
| T-016 / T-017 / T-018 会话新建/流式/取消/历史 | **删除** | 上游 Web 客户端即交互主链路 |
| T-019 工作区选择 | **删除** | 上游有原生目录选择 + project manager |
| T-020 模型配置与密钥安全存储 | **缩减** | 保留「企业侧模型策略与密钥托管」；基础凭据存储对齐上游 credential service |
| T-021 日志脱敏与诊断导出 | **缩减** | 上游有 crash report 与诊断；我方补「企业侧上报与脱敏策略」 |
| T-022 自动更新链路 | **改写** | 复用上游 electron-updater 与强制更新策略，改为建设我方签名与更新托管 |
| T-023 升级恢复与回滚 | **缩减** | 上游有 fatal-recovery 与 profile patch 备份；我方补企业 bundle 回滚 |
| T-024 P1 验收门禁 | **改写** | 验收对象改为「WorkNexus-DSH 企业发行版」 |

### 批次 2（Host Core）

| 任务 | 建议 | 理由 |
| --- | --- | --- |
| T-030 八类契约 | **保留**（注意命名避让） | 上游 `identity`/`credentials`/`api` 命名与语义不同，需避免混淆 |
| T-031 Plugin Manifest 规范 | **重大调整** | 不另立第二套插件系统；改为「上游 bundle 机制 + 企业治理扩展声明」 |
| T-032 PluginRegistry | **重大调整** | 改为挂接上游 plugin-manager 的治理与审计钩子，不重写生命周期 |
| T-033 EventBus | **调整** | 优先复用上游 cordis 事件机制，企业事件用命名空间前缀隔离 |
| T-034 契约冻结 | **保留** | 仍是必要的内部契约文档 |

### 批次 3（P2）

| 任务 | 建议 | 理由 |
| --- | --- | --- |
| T-040 控制面骨架 | **保留**（补边界说明） | 需明确与上游 `packages/api`（api-gateway）的边界 |
| T-041 ~ T-046 | **保留** | 上游无组织/空间/角色/审计体系 |
| T-047 用量采集 | **调整来源** | 优先上游 session 投影与账号用量能力；账号未接通时以 session 投影为主 |
| T-048 ~ T-053 | **保留** | 无重叠 |

### 批次 4~8

| 任务 | 建议 | 理由 |
| --- | --- | --- |
| T-060 ~ T-066（P3） | **保留**，插件形态改为上游插件规范 | 上游无知识库绑定体系 |
| T-070 ~ T-076（P4） | **保留** | 无重叠 |
| T-080 ~ T-083（P5） | **保留** | 无重叠 |
| T-090 ACP Transport | **改写为复用** | 上游有 `packages/acp`，不自研 JSON-RPC |
| T-091 ~ T-093 | **保留** | 治理与审计是新增能力 |
| T-100 `dshmarket` 复用 | **改写为上游 plugin-manager 接入** | 上游已有官方插件管理器 |
| T-101 ~ T-105 | **保留** | 私有源、白名单、审批、锁定、审计是新增治理能力 |

### 净效果

原计划 71 个任务中：**建议删除 8 个**（T-011、T-012、T-014、T-015、T-016、T-017、T-018、T-019），**改写 6 个**（T-002、T-005、T-022、T-024、T-031、T-032、T-090、T-100 中选其重）、**缩减 6 个**（T-003、T-004、T-013、T-020、T-021、T-023、T-047），**新增 4 个决策门**（DG-9~DG-12）与至少 2 个新任务（上游同步门禁、企业 bundle 预置与 protected 验证）。P1 从「15 个任务的客户端自研」变成「5~6 个任务的企业发行版」。

---

## 7. 客户端基线：三种方案对比与推荐

| 维度 | 方案 A：薄 fork 上游桌面端 + 企业插件层（推荐） | 方案 B：零 fork，纯插件注入 | 方案 C：自研 Electron 壳（原计划） |
| --- | --- | --- | --- |
| 做法 | 以 `deepseek-ai/deepseek-harness` 为上游，维护企业分支，只改品牌、更新源、预置 bundle、企业入口 | 不改上游代码，企业能力全部作为 profile bundle / 插件装载进官方客户端 | 从零写 Electron 壳、进程管理、更新器、诊断 |
| 与需求书「不重复建设」 | 符合 | 最符合 | 违背 |
| 企业 bundle 是否会被恢复动作禁用 | 可控（预置为内置 bundle） | 有风险（易被视为第三方 bundle） | 不存在该问题 |
| 更新与签名成本 | 中（要自建签名与更新源，但复用上游机制） | 低（依赖官方通道） | 高（全部自研） |
| 长期维护成本 | 中（需跟上游 rebase） | 低（但要忍受上游 UI/流程不可控） | 高（永久落后上游） |
| 品牌可控性 | 高 | 低（仍是官方外观） | 高 |
| 企业分发可控性（离线包、内网源） | 高 | 低 | 高 |
| 风险 | 上游 rc/alpha 快速演进导致分叉 | 无法满足「Host Core 不可拆卸」「企业入口品牌化」 | 重复投入 + 永远追不上上游 |

**推荐：A 为主、B 为辅。** 即：以官方桌面端为企业发行版基线（薄 fork，保持可 rebase），企业能力尽量实现为上游规范的插件/bundle；只有在 fork 无法承载时才改壳代码。同时把「企业能力也能跑在纯官方客户端上」作为附加目标，这样未来若官方支持企业插件机制，可以平滑切换回方案 B。

**不推荐 C。** 原 P1 计划中 10 个任务与上游重叠，继续自研壳意味着永久维护一套已经存在的东西，并且会在更新器、恢复策略、插件管理上持续落后。

**方案 A 的落地要点（供 DG-9 拍板后写进计划）**

1. 只改三类东西：产品品牌与文案、更新源与签名、随发行版预置的 bundle 清单。
2. 企业能力以第一方 bundle 形式预置（本机 第三方 的 `link:` 模式是已验证先例），并把它们放进 `dsh.profile.bundles` 的内置段，避免被 native recovery 当第三方禁用。
3. 保持向上游同步的能力：固定上游基线 tag（如 `dsh-v0.2.0-rc.1`），建立「上游合并演练」CI 门禁，每次上游发版跑一次合并 + 冒烟。
4. 发行合规：保留 MIT 声明与 `THIRD_PARTY_NOTICES`；项目命名继续用 DSH 缩写（WorkNexus-DSH 已符合品牌指引），描述中用「built on DeepSeek Harness」。

---

## 8. 建议新增/修订的决策门

| 门 | 问题 | 建议默认值 | 产出 |
| --- | --- | --- | --- |
| DG-9 | 客户端基线选 A / B / C | A（薄 fork）+ B（能力尽量插件化） | `docs/技术决策-客户端基线.md` |
| DG-10 | 版本锁定口径 | 锁定上游桌面发行版 tag，如 `dsh-v0.2.0-rc.1`；接受壳与 dsh 版本恒等；兼容范围随上游 minor 演进 | 更新 T-002 |
| DG-11 | 品牌与许可 | 保留 MIT 声明与 NOTICE；沿用 DSH 缩写命名；不使用官方品牌素材暗示背书 | `docs/技术决策-品牌与许可合规.md` |
| DG-12 | 更新通道与签名 | 复用上游 electron-updater 机制；自建 Windows 代码签名证书与自有更新源（内网/对象存储） | 更新 T-005、T-022 |

---

## 9. 未验证项与风险登记

| 项 | 状态 | 影响 | 建议动作 |
| --- | --- | --- | --- |
| 账号登录是否可用 | 文章说可用；README 说未接通、按钮禁用 | 影响 P2 用量/余额能力能否复用官方账号体系 | 安装官方 `0.2.0-rc.1` 实测：能否登录、是否出现「DeepSeek 账号」模型组、余额与用量页是否可用 |
| 「7 个官方插件」清单 | 未逐项清点 | 影响 P6B 治理基线 | 安装后清点 shipped bundles 与默认启用状态 |
| 第三方插件能否用 GitHub 仓库地址安装 | 未证实 | 影响 P6B「私有源」「白名单」设计 | 实测插件安装入口接受的输入形态 |
| 上游更新清单文件路径 | `dsh-desk/bin/win-x64/latest.yml` 与 `latest.json` 均 404 | 影响我方能否镜像更新源 | 抓取客户端实际 updater 请求（可用本地 updater 资格脚本 `test:updates:local` 的思路） |
| 企业预置 bundle 会不会被 native recovery 视为第三方 | 未验证 | **高风险**：与「Host Core 不可拆卸」直接冲突 | 实测：故意让 Host 启动失败，观察恢复对话框是否会列出并禁用我方 bundle |
| `0.2.0-rc.1` 是否有破坏性变更 | 未读 CHANGELOG | 影响基线选择 | 若采用方案 A，先拉 `dsh-v0.2.0-rc.1` 与 `dsh-v0.1.7-rc.2` 的差异清单 |
| win-x64 payload 在 arm64 主机上的架构校验限制 | README 已列为 known limitation | 影响少数设备 | 记录为已知限制，不阻塞 |

---

## 10. 复现命令

```powershell
# 1) 文章正文
curl.exe -sS -L -A "Mozilla/5.0" -o wx.html "https://mp.weixin.qq.com/s/CwiNLFV9txARS6jWUYHX0A"

# 2) 仓库基本信息
curl.exe -sS -H "Accept: application/vnd.github+json" "https://api.github.com/repos/deepseek-ai/deepseek-harness"

# 3) 发布列表（确认 0.2.0-rc.1 已发布且为 prerelease）
curl.exe -sS -H "Accept: application/vnd.github+json" "https://api.github.com/repos/deepseek-ai/deepseek-harness/releases?per_page=8"

# 4) 桌面端包信息与设计说明
curl.exe -sS "https://api.github.com/repos/deepseek-ai/deepseek-harness/contents/apps/desktop/package.json"
curl.exe -sS "https://api.github.com/repos/deepseek-ai/deepseek-harness/contents/apps/desktop/README.md"

# 5) 插件管理器与身份包（确认上游无企业体系）
curl.exe -sS "https://api.github.com/repos/deepseek-ai/deepseek-harness/contents/packages/boot/plugin-manager/README.md"
curl.exe -sS "https://api.github.com/repos/deepseek-ai/deepseek-harness/contents/packages/identity/README.md"

# 6) 安装包真伪
curl.exe -sS -I -L "https://download.deepseek.com/dsh-desk/bin/win-x64/deepseek-harness-0.2.0-rc.1-win-x64.exe"
```

---

## 11. 下一步

1. **需要你拍板 DG-9**：客户端基线选 A（薄 fork + 插件层）、B（零 fork 纯插件）还是 C（继续自研壳）。
2. 拍板后我按第 5、6 节的清单一次性同步：需求说明书升版（v1.1，保留 v1.0 原件）、总览的批次与任务索引、三份执行计划，并补 DG-9~DG-12 决策文档与「上游同步门禁」任务。
3. 无论选哪个方案，建议先做两件实测：装官方 `0.2.0-rc.1` 确认账号登录与插件入口的真实能力；验证企业预置 bundle 会不会被 native recovery 禁用（这是「Host Core 不可拆卸」的硬前提）。

---

## 12. 决策记录

### DG-9 客户端基线（2026-09-28 决策人拍板）

**决策：方案 A（薄 fork 上游桌面端）+ 上游优先原则。** 原话要求：「尽量 follow 官方开源的 `dsh-desktop`，需求说明书里跟官方开源冲突的地方，优先保留官方开源的设计。这是最稳妥且后续可以跟随官方同步升级的办法，我们的个性化需求只体现在业务侧，所有基础功能侧，严格遵循 DeepSeek Harness 官方。」

据此落地的规则（已成为需求书 §3.4 与任务计划 G0）：

1. 基础功能侧严格遵循官方：客户端壳、进程与运行时管理、profile 初始化、插件装载与生命周期、更新与恢复、诊断、凭据存储、会话交互。
2. 需求书与官方设计冲突时以官方为准，并在需求书 §13.3 登记让位原因。
3. 个性化只落业务侧：企业管理、知识库、DocGraph Adapter、IPD Demo、企业插件治理，以及发行版四类差异（品牌、更新源与签名、预置 bundle 清单、企业侧入口）。
4. 差异集白名单化、可枚举、可审计；每个上游正式版本至少一次 rebase 演练。

### 同步结果（本次已完成）

| 文档 | 变更 |
| --- | --- |
| `内部历史归档` | 新增：§3.4 上游基线与跟随策略、P1-F15~F18、§13 变更对照表与让位登记；改写：§1 总原则、§2.1 责任方、§3.1 边界、§4.1 目标与验收、§4.6.2（`dshmarket` → 官方插件管理器）、§5.2/§5.3、§6.4、§8、§9、§11 新增 5 条。v1.0 的 57 条需求条目**一条未删** |
| `docs/WorkNexus-DSH-需求说明书-v1.2.md` | 对 v1.1 的证据化红队评审发现 RT-01~RT-10 **全部回填**。**修订 1（RT-01~RT-04）**：改写 §4.1.4 P1 范围（业务功能 vs Host Core 骨架）、§3.2 / §4.2.6 契约职责（`PluginRegistry` → `PluginGovernanceView`）、§6.4 / §4.6.1 接口归属（`AgentTransport` 仅为 ACP 目标契约），新增 §3.5 运行模式。**修订 2（RT-05~RT-10）**：§5.4 第 6 条补降级批准路径、§4.1.5 补签名产物演练与验收 9/10、新增 §7.1 诊断上报与隐私边界、§7 可用性改为可测口径、§1 决策 2 与 §3.4 绑定锁定 tag、§4.2.4 补审计留存与只追加。新增 §13.4 修订映射。按决策人要求**就地覆盖 v1.2，不新增 v1.3**；v1.1 保留为历史基线 |
| `内部任务拆分总览` | 升 v2.0：新增 G0 上游优先原则与 DG-9~DG-12；批次 0 扩为 12 个任务；批次 1 整体替换为企业发行版（9 个任务）；新增 §3.1 编号迁移对照表；总任务数 71 → 68（新增 9、作废 8） |
| `内部步骤明细附录` | 新建，取代原 P0/P1 计划 |
| `内部步骤明细附录` | 定点修订：T-030 插件契约改为只读治理视图；T-031 改为企业插件声明；T-032 改为治理挂接；T-033 改为企业事件通道；T-040/T-041/T-046/T-047/T-050/T-051/T-052/T-053 补充官方对齐约束 |
| `内部步骤明细附录` | 定点修订：T-090 改为复用官方 ACP；T-100 改为挂接官方插件管理器；全部插件测试改用 `parseEnterpriseDeclaration` |
| `内部历史归档`、`内部历史归档` | 旧版计划归档留痕，带废弃横幅 |

### 仍然待办的实测项

1. 装官方 `0.2.0-rc.1` 确认账号登录与插件入口的真实能力（研究第 9 节的风险项，已转为 T-006）。
2. 验证企业预置 bundle 会不会被 native recovery 禁用（已转为 T-005，是「Host Core 不可拆卸」的硬前提）。
3. 定位官方更新清单的实际路径（基线核查时 `latest.yml` / `latest.json` 均 404，已转为 T-022 Step 1）。
