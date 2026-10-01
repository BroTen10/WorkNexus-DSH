/**
 * PluginGovernanceView —— 契约⑦：企业侧对官方插件状态的**只读镜像**与治理标注。
 *
 * 硬约束（需求书 §5.3、§6.1 补充、§11.12）：
 *  - **官方 plugin manager 是插件启停的唯一权威**；
 *  - 本契约**不提供 enable / disable 语义**，企业侧只做白名单/审批判定与审计。
 */

export type PluginHealth = { ok: boolean; detail?: string }

export type PluginState = 'installed' | 'enabled' | 'disabled' | 'failed'

export type PluginView = {
  id: string
  version: string
  enabled: boolean
  protected: boolean
  health: PluginHealth
}

export interface PluginGovernanceView {
  list(): Promise<PluginView[]>
  stateOf(pluginId: string): Promise<PluginState>
  isAllowed(pluginId: string, version: string): boolean
}

/**
 * 个人模式下的宽松视图：只记录可疑安装，不强制白名单（需求书 §3.5）。
 */
export const PERSONAL_MODE_GOVERNANCE: PluginGovernanceView = Object.freeze({
  list: async () => [],
  stateOf: async () => 'installed' as PluginState,
  isAllowed: () => true,
})
