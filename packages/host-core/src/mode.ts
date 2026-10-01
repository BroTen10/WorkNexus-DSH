/**
 * 运行模式上下文与门控（T-035）。
 *
 * 规则（需求书 §3.5）：
 *  - 未登录或未选定组织 → personal；
 *  - 已登录且已选定有效组织 → enterprise；
 *  - 不提供手工强制开关；
 *  - 切换是状态投影，不回滚、不删除官方会话与工作区数据；
 *  - 控制面不可达或组织上下文失效时降级，官方客户端与 DSH 会话仍可用。
 */

import type { RunMode } from '@worknexus/contracts'

/** 运行模式输入的唯一来源；T-051 登录态投影将实现该抽象。 */
export interface ModeProvider {
  current(): ModeProviderState | Promise<ModeProviderState>
}

export type ModeProviderState = {
  signedIn: boolean
  organizationId: string | null
  organizationContextValid?: boolean
  controlPlaneReachable?: boolean
}

export type DegradationReason =
  | 'control-plane-unreachable'
  | 'organization-context-invalid'

export type PluginGovernanceStrength = 'record-only' | 'strict'

export type DataOwnership = 'local' | 'organization'

export type ModeContext = {
  mode: RunMode
  organizationId: string | null
  degraded: boolean
  degradationReason: DegradationReason | null
  notices: readonly string[]
  capabilities: {
    /** 官方客户端与 DSH 会话在任何模式下都不得被企业门控阻断。 */
    readonly officialSessionAvailable: true
    readonly enterpriseEntryVisible: boolean
    readonly controlPlaneConnectionAllowed: boolean
    readonly pluginGovernance: PluginGovernanceStrength
    readonly dataOwnership: DataOwnership
  }
}

function hasOrganization(value: string | null): value is string {
  return typeof value === 'string' && value.length > 0
}

function personalContext(input: ModeProviderState, degraded: boolean, reason: DegradationReason | null): ModeContext {
  const notices = reason === 'organization-context-invalid'
    ? ['组织上下文失效，已退回个人模式；官方会话与工作区数据未改动。']
    : []
  return {
    mode: 'personal',
    organizationId: degraded ? input.organizationId : null,
    degraded,
    degradationReason: reason,
    notices,
    capabilities: {
      officialSessionAvailable: true,
      enterpriseEntryVisible: false,
      controlPlaneConnectionAllowed: false,
      pluginGovernance: 'record-only',
      dataOwnership: 'local',
    },
  }
}

/**
 * 由登录态和组织上下文推导运行模式。该函数是纯投影；
 * “切换”指传入新的 provider 状态，而不是提供 mode 写入 API。
 */
export function createModeContext(input: ModeProviderState): ModeContext {
  if (!input.signedIn || !hasOrganization(input.organizationId)) {
    return personalContext(input, false, null)
  }

  if (input.organizationContextValid !== true) {
    return personalContext(input, true, 'organization-context-invalid')
  }

  if (input.controlPlaneReachable !== true) {
    return {
      mode: 'enterprise',
      organizationId: input.organizationId,
      degraded: true,
      degradationReason: 'control-plane-unreachable',
      notices: ['企业控制面不可达，企业功能已降级；DSH 会话仍可用。'],
      capabilities: {
        officialSessionAvailable: true,
        enterpriseEntryVisible: false,
        controlPlaneConnectionAllowed: false,
        pluginGovernance: 'record-only',
        dataOwnership: 'organization',
      },
    }
  }

  return {
    mode: 'enterprise',
    organizationId: input.organizationId,
    degraded: false,
    degradationReason: null,
    notices: [],
    capabilities: {
      officialSessionAvailable: true,
      enterpriseEntryVisible: true,
      controlPlaneConnectionAllowed: true,
      pluginGovernance: 'strict',
      dataOwnership: 'organization',
    },
  }
}

/** 企业入口可见性门控；个人模式和降级态都隐藏入口但不抛错。 */
export function enterpriseEntryVisible(context: ModeContext): boolean {
  return context.capabilities.enterpriseEntryVisible
}

/** 企业控制面连接门控；个人模式永不连接，降级企业态 fail closed。 */
export function controlPlaneConnectionAllowed(context: ModeContext): boolean {
  return context.capabilities.controlPlaneConnectionAllowed
}

/** 插件治理强度：企业健康态严格，个人态或降级态只记录可疑安装。 */
export function pluginGovernanceStrength(context: ModeContext): PluginGovernanceStrength {
  return context.capabilities.pluginGovernance
}

/** 数据归属：个人态为本地；企业态（含控制面降级）仍归属组织，不复制到本地。 */
export function dataOwnership(context: ModeContext): DataOwnership {
  return context.capabilities.dataOwnership
}
