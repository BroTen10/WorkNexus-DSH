import { describe, expect, it } from 'vitest'

import { can, hasAllActions } from '../src/permission-client.js'

describe('permission client', () => {
  it('uses the same core role decisions for UI prechecks', () => {
    const actor = { organizationId: 'o', role: 'admin' } as const
    expect(can(actor, 'plugin.enable', { type: 'plugin', id: 'p' })).toBe(true)
    expect(can(actor, 'organization.delete', { type: 'organization', id: 'o' })).toBe(false)
    expect(can({ organizationId: 'o', role: 'viewer' }, 'session.create', { type: 'session', id: 's' })).toBe(false)
  })

  it('requires every requested action before rendering write controls', () => {
    expect(hasAllActions({ organizationId: 'o', role: 'owner' }, ['audit.read', 'usage.read'])).toBe(true)
    expect(hasAllActions({ organizationId: 'o', role: 'member' }, ['audit.read'])).toBe(false)
  })
})
