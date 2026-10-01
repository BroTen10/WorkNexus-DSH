/**
 * T-091：ACP 插件声明与后台任务页面。
 */

import { describe, expect, it } from 'vitest'
import { parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import manifest from '../plugin.manifest.json'
import { ACP_PAGES } from '../src/index.js'
import { JOB_ACTIONS, JOB_STATUS_LABELS } from '../src/pages/JobList.js'

describe('acp plugin', () => {
  it('declares the background automation manifest with session.create', () => {
    const result = parseEnterpriseDeclaration(manifest)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.declaration.permissions).toEqual(
        expect.arrayContaining(['space.read', 'session.create', 'audit.read', 'usage.read']),
      )
      expect(result.declaration.uiSlots).toEqual(['worknexus.acp.jobs'])
    }
  })

  it('exposes the six job states and three lifecycle actions', () => {
    expect(Object.keys(JOB_STATUS_LABELS)).toEqual([
      'queued', 'running', 'succeeded', 'failed', 'cancelled', 'closed',
    ])
    expect(JOB_ACTIONS).toEqual(['cancel', 'resume', 'close'])
    expect(ACP_PAGES.map((page) => page.id)).toEqual(['jobs'])
    expect(ACP_PAGES[0]?.backgroundOnly).toBe(true)
  })
})
