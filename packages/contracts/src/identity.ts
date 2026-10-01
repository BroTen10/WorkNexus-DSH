/**
 * IdentityContext —— 契约①：当前用户、登录态、邮箱、组织归属。
 *
 * 边界（T-011 §3.2）：企业字段只在企业侧读取；官方客户端不理解本契约。
 * 凭据本身**不进入**本契约——凭据一律走官方 `dsh-credentials`（T-006 R-4）。
 */

import type { EnterpriseFieldPrefix } from './version.js'

/** 运行模式：由登录态与组织上下文决定（需求书 §3.5），不提供手工强制开关。 */
export type RunMode = 'personal' | 'enterprise'

export type IdentityContext = {
  userId: string
  email: string
  organizationIds: string[]
  sessionTokenExpiresAt: string
  mode: RunMode
}

/** 个人模式的最小身份（无组织上下文），用于 P1 交付。 */
export const PERSONAL_IDENTITY: Readonly<IdentityContext> = Object.freeze({
  userId: 'local',
  email: '',
  organizationIds: [],
  sessionTokenExpiresAt: '',
  mode: 'personal',
})

/** 企业字段在插件配置/事件载荷中的键名前缀（`entUserId` 等）。 */
export const IDENTITY_FIELD_PREFIX: EnterpriseFieldPrefix = 'ent'
