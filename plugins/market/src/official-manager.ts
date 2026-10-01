/**
 * 官方插件管理器事实与接入端口（T-100 Step 0 / S2 取证）。
 *
 * 上游事实（`repos/deepseek-harness` @ dsh-v0.2.0-rc.1，`packages/boot/plugin-manager` README 原文）：
 *  - 官方包：`@deepseek-ai/dsh-plugin-manager`；Web 侧边栏「插件」页（`ui-plugin-manager`）；
 *  - **安装输入形态**：`installBundle(spec, options)`，spec 支持「注册表包名 / 绝对路径 / git 地址 / tarball」；
 *    注册表包名经 `pnpm view` 询问注册表（在 profile 目录内运行，沿用同一代理与认证配置）；
 *  - **私有源**：`options.registry` 优先，否则用配置的 `registry`，失败再依次问 `fallbackRegistries`；
 *    配置集合之外的注册表「只问它自己」，因此私有源不会落到公共源；
 *  - 事件：`plugin-manager/changed`（完成操作统一发）、`plugin-manager/install-log`（输出流）、
 *    `plugin-manager/install-state`（installing / cancelling / applying）；
 *  - 其他能力：`listBundles`、`inspect(spec)`、`waitForInstall(requestId)`、`cancelInstall(requestId)`；
 *  - 官方**未提供审批弹窗**：`plugin_manager` 工具要求 `danger-full-access` 或本次调用批准，
 *    企业审批必须在企业控制面/企业 UI 内完成（§4.6.2 约束）。
 *
 * 本模块**不实现**插件市场、**不替换**官方插件管理器：只把官方能力包装成可注入端口，
 * 供企业治理层（白名单、审批、锁定）在安装前后做判断与记录。
 */

export const OFFICIAL_MANAGER_PACKAGE = '@deepseek-ai/dsh-plugin-manager'
export const OFFICIAL_MANAGER_UI = 'ui-plugin-manager'

export const OFFICIAL_INSTALL_SPEC_KINDS = Object.freeze([
  'registry-package',
  'absolute-path',
  'git-url',
  'tarball',
] as const)

export type OfficialInstallSpecKind = (typeof OFFICIAL_INSTALL_SPEC_KINDS)[number]

export type OfficialBundleSummary = {
  name: string
  enabled: boolean
  description?: string
  error?: string
}

export type OfficialInspectResult = {
  name: string
  version: string
  isBundle: boolean
  registry?: string
  problem?: 'invalid-spec' | 'already-installed' | 'not-found' | 'not-a-package' | 'not-a-bundle' | 'network' | 'unknown'
}

export type OfficialInstallRequest = {
  spec: string
  registry?: string
  approvedBuilds?: readonly string[]
}

export type OfficialInstallResult = {
  requestId: string
  application: 'applied' | 'cancelled' | 'failed'
  bundle?: string
  failedAt?: 'spec-host' | 'registry' | null
}

/** 官方插件管理器能力面（由官方 `dsh-plugin-manager` 提供；本层只做包装与治理前置）。 */
export interface OfficialPluginManagerPort {
  listBundles(): Promise<OfficialBundleSummary[]>
  inspect(spec: string, options?: { registry?: string }): Promise<OfficialInspectResult>
  installBundle(request: OfficialInstallRequest): Promise<OfficialInstallResult>
  waitForInstall(requestId: string): Promise<OfficialInstallResult | null>
  cancelInstall(requestId: string): Promise<'cancelled' | 'too-late' | 'not-running'>
}

export const OFFICIAL_MANAGER_FACTS = Object.freeze({
  package: OFFICIAL_MANAGER_PACKAGE,
  ui: OFFICIAL_MANAGER_UI,
  installInputs: OFFICIAL_INSTALL_SPEC_KINDS,
  registryOptions: ['options.registry', 'configured registry', 'fallbackRegistries'],
  events: ['plugin-manager/changed', 'plugin-manager/install-log', 'plugin-manager/install-state'],
  privateRegistryIsolated: true,
  officialApprovalDialog: false,
})
