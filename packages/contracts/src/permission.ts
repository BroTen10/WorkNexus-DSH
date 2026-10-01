/**
 * PermissionPolicy —— 契约③：判断用户是否可执行某资源上的某操作。
 *
 * 默认最小权限（需求书 §3.5 / §4.2.3）：未显式授权的操作一律拒绝。
 * 权限的**最终裁决权在服务端**（附录 B 架构说明）；客户端实现只是本地预判缓存。
 */

import type { SpaceContext } from './space.js'

export type Action =
  | 'space.read'
  | 'space.write'
  | 'member.invite'
  | 'member.remove'
  | 'role.assign'
  | 'plugin.enable'
  | 'plugin.disable'
  | 'audit.read'
  | 'usage.read'
  | 'budget.write'
  | 'kb.retrieve'
  | 'kb.bind'
  | 'docgraph.submit'
  | 'docgraph.read'
  | 'session.create'

/** `Action` 的运行时枚举，供企业插件声明校验器直接引用，避免重复清单。 */
export const ACTIONS = Object.freeze([
  'space.read',
  'space.write',
  'member.invite',
  'member.remove',
  'role.assign',
  'plugin.enable',
  'plugin.disable',
  'audit.read',
  'usage.read',
  'budget.write',
  'kb.retrieve',
  'kb.bind',
  'docgraph.submit',
  'docgraph.read',
  'session.create',
] as const)

export type ResourceRef = { type: string; id: string }

export interface PermissionPolicy {
  can(actor: SpaceContext, action: Action, resource: ResourceRef): boolean
}

/** 默认拒绝实现：任何未显式允许的操作返回 false。 */
export const DENY_ALL_POLICY: PermissionPolicy = Object.freeze({
  can: () => false,
})

/**
 * 只读角色的基线策略：viewer 只能读，不能写/邀请/改角色/管预算。
 * 仅用于 P1 的个人模式与 P2 的最小可用集；服务端策略以服务端为准。
 */
export const READ_ONLY_FOR_VIEWER_POLICY: PermissionPolicy = Object.freeze({
  can(actor: SpaceContext, action: Action) {
    if (actor.role !== 'viewer') return true
    return action === 'space.read' || action === 'usage.read' || action === 'kb.retrieve'
      || action === 'docgraph.read' || action === 'session.create'
  },
})
