import { describe, expect, it } from 'vitest'
import manifest from '../plugin.manifest.json'
import { parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import { canRender, visiblePages } from '../src/permissions.js'
import { ENTERPRISE_ADMIN_PAGES } from '../src/index.js'

describe('enterprise-admin plugin', () => {
  it('declares a valid manifest with six ui slots', () => {
    const result = parseEnterpriseDeclaration(manifest)
    expect(result.ok).toBe(true)
    if (result.ok) expect(result.declaration.uiSlots).toHaveLength(6)
  })

  it('hides write actions from viewers', () => {
    expect(canRender({ organizationId: 'o', role: 'viewer' }, 'budget.write')).toBe(false)
    expect(canRender({ organizationId: 'o', role: 'owner' }, 'budget.write')).toBe(true)
  })

  it('registers exactly six pages and hides all in personal mode', () => {
    expect(ENTERPRISE_ADMIN_PAGES).toHaveLength(6)
    expect(visiblePages('personal')).toEqual([])
    expect(visiblePages('enterprise')).toHaveLength(6)
  })
})
