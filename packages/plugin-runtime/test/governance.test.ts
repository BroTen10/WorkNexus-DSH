import { describe, expect, it } from 'vitest'

import { attachGovernanceHooks, createGovernanceHooks, type GovernanceAuditEntry } from '../src/governance.js'

describe('governance hooks', () => {
  it('denies an install that is not whitelisted', async () => {
    const hooks = createGovernanceHooks({ whitelist: ['worknexus.knowledge'], audit: async () => {} })
    const result = await hooks.onInstall({ pluginId: 'unknown.plugin', version: '1.0.0' })
    expect(result.decision).toBe('deny')
    expect(result.reason).toMatch(/whitelist/i)
  })

  it('allows a whitelisted install and writes an audit entry', async () => {
    const audited: string[] = []
    const hooks = createGovernanceHooks({
      whitelist: ['worknexus.knowledge'],
      audit: async (e) => { audited.push(e.action) },
    })
    const result = await hooks.onInstall({ pluginId: 'worknexus.knowledge', version: '1.0.0' })
    expect(result.decision).toBe('allow')
    expect(audited).toEqual(['plugin.install'])
  })

  it('never throws into the official plugin manager when a hook fails', async () => {
    const hooks = createGovernanceHooks({
      whitelist: [],
      audit: async () => { throw new Error('audit down') },
    })
    await expect(hooks.onEnable({ pluginId: 'p', version: '1.0.0' })).resolves.toBeUndefined()
  })

  it('audits enable, disable and uninstall even when details are unavailable', async () => {
    const audited: GovernanceAuditEntry[] = []
    const hooks = createGovernanceHooks({
      whitelist: [],
      audit: async (entry) => { audited.push(entry) },
    })
    await hooks.onEnable({ pluginId: '<unknown>', version: '<unknown>' })
    await hooks.onDisable({ pluginId: '<unknown>', version: '<unknown>' })
    await hooks.onUninstall({ pluginId: '<unknown>', version: '<unknown>' })
    expect(audited.map(entry => entry.action)).toEqual(['plugin.enable', 'plugin.disable', 'plugin.uninstall'])
  })

  it('does not propagate an audit failure out of enable, disable or uninstall', async () => {
    const hooks = createGovernanceHooks({
      whitelist: [],
      audit: async () => { throw new Error('audit down') },
    })
    await expect(hooks.onEnable({ pluginId: 'p', version: '1' })).resolves.toBeUndefined()
    await expect(hooks.onDisable({ pluginId: 'p', version: '1' })).resolves.toBeUndefined()
    await expect(hooks.onUninstall({ pluginId: 'p', version: '1' })).resolves.toBeUndefined()
  })
})

describe('official plugin-manager attachment', () => {
  it('maps install and remove without rewriting the lifecycle', async () => {
    const events: string[] = []
    const hooks = createGovernanceHooks({
      whitelist: ['worknexus.knowledge'],
      audit: async (entry) => { events.push(`${entry.action}:${entry.pluginId}:${entry.version}`) },
    })
    const listeners = new Map<string, Array<(event: unknown) => void>>()
    const official = {
      on(topic: string, handler: (event: unknown) => void) {
        const list = listeners.get(topic) ?? []
        list.push(handler)
        listeners.set(topic, list)
        return () => {}
      },
    }
    attachGovernanceHooks({ official, hooks })
    for (const handler of listeners.get('plugin-manager/changed') ?? []) {
      handler({ reason: 'install' })
      handler({ reason: 'remove' })
      handler({ reason: 'plugin' })
      handler({ reason: 'bundle' })
    }
    expect(events).toEqual([
      'plugin.install:<unknown>:<unknown>',
      'plugin.uninstall:<unknown>:<unknown>',
      'plugin.changed:<unknown>:<unknown>',
      'plugin.changed:<unknown>:<unknown>',
    ])
  })

  it('isolates an attachment error from the official event dispatch', async () => {
    const errors: string[] = []
    const seen: string[] = []
    const hooks = {
      onInstall: async () => { throw new Error('hook down') },
      onEnable: async () => {},
      onDisable: async () => {},
      onUninstall: async () => {},
      onPluginOrBundleChanged: async () => {},
    }
    let handler: ((event: unknown) => void) | undefined
    const official = {
      on(_topic: string, listener: (event: unknown) => void) {
        handler = listener
        return () => {}
      },
    }
    attachGovernanceHooks({ official, hooks, onError: (error) => { errors.push(String(error)) } })
    expect(() => handler?.({ reason: 'install' })).not.toThrow()
    await new Promise(resolve => setImmediate(resolve))
    expect(seen).toEqual([])
    expect(errors.join()).toMatch(/hook down/)
  })
})
