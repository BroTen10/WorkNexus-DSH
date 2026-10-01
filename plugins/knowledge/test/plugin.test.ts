/**
 * T-061：知识库插件以官方插件形态交付（声明 + 模式门控 + 权限预判）。
 */

import { describe, expect, it } from 'vitest'
import { parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import manifest from '../plugin.manifest.json'
import { KNOWLEDGE_PAGES } from '../src/index.js'
import { canManageKnowledge, visiblePages } from '../src/permissions.js'

describe('knowledge plugin', () => {
  it('declares a valid official bundle manifest with knowledge permissions', () => {
    const result = parseEnterpriseDeclaration(manifest)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.declaration.permissions).toEqual(
        expect.arrayContaining(['space.read', 'kb.retrieve', 'kb.bind']),
      )
      expect(result.declaration.uiSlots.length).toBeGreaterThan(0)
      expect(result.declaration.dsh?.bundle?.patch).toBe('./cordis.patch.yml')
    }
  })

  it('registers the connection page and hides all pages in personal mode', () => {
    expect(KNOWLEDGE_PAGES.map((page) => page.id)).toEqual(['connections', 'admin'])
    expect(KNOWLEDGE_PAGES[0]?.uiSlot).toBe('worknexus.knowledge.connections')
    expect(visiblePages('personal')).toEqual([])
    expect(visiblePages('enterprise')).toEqual(expect.arrayContaining(['connections', 'admin']))
  })

  it('reserves write actions for admins and owners', () => {
    expect(canManageKnowledge({ organizationId: 'o', role: 'member' })).toBe(false)
    expect(canManageKnowledge({ organizationId: 'o', role: 'viewer' })).toBe(false)
    expect(canManageKnowledge({ organizationId: 'o', role: 'admin' })).toBe(true)
    expect(canManageKnowledge({ organizationId: 'o', role: 'owner' })).toBe(true)
  })
})
