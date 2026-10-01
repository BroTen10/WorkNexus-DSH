import type { SpaceContext } from '@worknexus/contracts'
import { canPermission, type ServerAction } from '@worknexus/host-core'

export type PluginPermission = ServerAction | 'identity.read'

export type PluginActor = SpaceContext

export function canRender(actor: PluginActor, action: PluginPermission): boolean {
  if (action === 'identity.read') return true
  return canPermission(actor, action as ServerAction, { type: 'enterprise-admin', id: actor.organizationId })
}

export function visiblePages(mode: 'personal' | 'enterprise'): string[] {
  return mode === 'enterprise' ? ENTERPRISE_ADMIN_PAGE_IDS : []
}

const ENTERPRISE_ADMIN_PAGE_IDS = [
  'organizations',
  'members',
  'roles',
  'spaces',
  'audit',
  'usage',
]
