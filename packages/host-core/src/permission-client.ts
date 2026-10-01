/**
 * 权限客户端预判：与服务端矩阵同形，但不是权威。
 * 最终以控制面 `app.services.permission.can()` 裁决为准。
 */

import type { Action, SpaceContext } from '@worknexus/contracts'

export type ServerAction = Action | 'organization.delete' | 'ownership.transfer'

export const SERVER_ACTIONS = Object.freeze([
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
  'organization.delete',
  'ownership.transfer',
] as const)

const PERMISSION_MATRIX: Record<string, ReadonlySet<string>> = Object.freeze({
  owner: new Set(SERVER_ACTIONS),
  admin: new Set(SERVER_ACTIONS.filter(action => action !== 'organization.delete' && action !== 'ownership.transfer')),
  member: new Set([
    'space.read', 'space.write', 'kb.retrieve', 'kb.bind',
    'docgraph.submit', 'docgraph.read', 'session.create',
  ]),
  viewer: new Set([
    'space.read', 'kb.retrieve', 'docgraph.read', 'usage.read',
  ]),
})

export function can(
  actor: SpaceContext,
  action: ServerAction,
  _resource: { type: string; id: string },
): boolean {
  return PERMISSION_MATRIX[actor.role]?.has(action) ?? false
}

export function hasAllActions(
  actor: SpaceContext,
  actions: readonly ServerAction[],
): boolean {
  return actions.every(action => can(actor, action, { type: 'precheck', id: actor.organizationId }))
}
