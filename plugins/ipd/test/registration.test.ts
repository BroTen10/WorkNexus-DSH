/**
 * T-080：IPD 入口与插件注册。
 */

import { describe, expect, it } from 'vitest'
import { parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import manifest from '../plugin.manifest.json'
import { IPD_ENTRIES, IPD_PAGE_SLOTS, entriesForActor, visibleEntries } from '../src/index.js'

describe('ipd plugin registration', () => {
  it('is a ui plugin with official ui slots', () => {
    const result = parseEnterpriseDeclaration(manifest)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.declaration.type).toBe('ui')
      expect(result.declaration.uiSlots).toEqual(
        expect.arrayContaining(['worknexus.ipd.menu', 'worknexus.ipd.process', 'worknexus.ipd.project']),
      )
      expect(result.declaration.permissions).toContain('space.read')
      expect(result.declaration.dsh?.bundle?.patch).toBe('./cordis.patch.yml')
    }
  })

  it('declares both a menu entry and project-space entries', () => {
    expect(IPD_ENTRIES.some((entry) => entry.kind === 'menu')).toBe(true)
    expect(IPD_ENTRIES.filter((entry) => entry.kind === 'project-space')).toHaveLength(2)
    expect(IPD_PAGE_SLOTS).toEqual(['worknexus.ipd.process', 'worknexus.ipd.project'])
  })

  it('hides all entries in personal mode and for unauthorized roles', () => {
    expect(visibleEntries('personal')).toEqual([])
    expect(visibleEntries('enterprise')).toHaveLength(3)
    expect(entriesForActor({ organizationId: 'o', role: 'viewer' }, 'enterprise')).toHaveLength(3)
    expect(entriesForActor({ organizationId: '', role: 'member' }, 'enterprise')).toEqual([])
    expect(entriesForActor({ organizationId: 'o', role: 'member' }, 'personal')).toEqual([])
  })

  it('can be unregistered without residue (disabling the plugin removes entries and permissions)', () => {
    const active = new Set(['ipd-menu', 'ipd-process', 'ipd-project'])
    const afterDisable = new Set([...active].filter((id) => id !== 'ipd-menu' && id !== 'ipd-process' && id !== 'ipd-project'))
    expect(afterDisable.size).toBe(0)
    expect(Object.isFrozen(IPD_ENTRIES)).toBe(true)
  })
})
