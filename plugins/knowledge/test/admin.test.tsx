/**
 * T-065：知识库管理页面（P3-F09）——三动作齐备、模式门控、仅授权管理员可见。
 */

import { describe, expect, it } from 'vitest'
import { parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import manifest from '../plugin.manifest.json'
import {
  KNOWLEDGE_ADMIN_ACTIONS,
  KnowledgeAdminPage,
  adminActionsFor,
} from '../src/pages/KnowledgeAdmin.js'
import { visiblePages } from '../src/permissions.js'

describe('knowledge admin page', () => {
  it('declares an admin page and kb permissions in the official manifest', () => {
    const result = parseEnterpriseDeclaration(manifest)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.declaration.uiSlots).toHaveLength(2)
      expect(result.declaration.permissions).toEqual(
        expect.arrayContaining(['kb.retrieve', 'kb.bind']),
      )
    }
    expect(KnowledgeAdminPage.uiSlot).toBe('worknexus.knowledge.admin')
  })

  it('covers the three P3-F09 capabilities', () => {
    expect(KNOWLEDGE_ADMIN_ACTIONS.map((action) => action.id)).toEqual([
      'configure-provider',
      'bind-space',
      'toggle-knowledge',
    ])
    expect(KNOWLEDGE_ADMIN_ACTIONS.every((action) => action.requiresAdmin)).toBe(true)
  })

  it('shows actions only to authorized admins and hides the page in personal mode', () => {
    expect(adminActionsFor({ organizationId: 'o', role: 'viewer' })).toEqual([])
    expect(adminActionsFor({ organizationId: 'o', role: 'member' })).toEqual([])
    expect(adminActionsFor({ organizationId: 'o', role: 'admin' })).toHaveLength(3)
    expect(adminActionsFor({ organizationId: 'o', role: 'owner' })).toHaveLength(3)

    expect(visiblePages('personal')).toEqual([])
    expect(visiblePages('enterprise')).toEqual(expect.arrayContaining(['connections', 'admin']))
  })

  it('does not carry a second plugin-manager surface', () => {
    const source = JSON.stringify(KnowledgeAdminPage) + JSON.stringify(KNOWLEDGE_ADMIN_ACTIONS)
    expect(source).not.toContain('ipcRenderer')
    expect(source).not.toContain('installBundle')
  })
})
