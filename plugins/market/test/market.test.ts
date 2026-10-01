/**
 * T-100：挂接官方插件管理器（只做治理接入，不替换实现）。
 */

import { describe, expect, it } from 'vitest'
import { createGovernanceHooks, parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import manifest from '../plugin.manifest.json'
import { MARKET_PAGES, MARKET_ACTIONS, OFFICIAL_MANAGER_FACTS, describeMarket } from '../src/index.js'
import type { OfficialPluginManagerPort } from '../src/official-manager.js'

describe('market plugin', () => {
  it('declares a market-capable manifest', () => {
    const result = parseEnterpriseDeclaration(manifest)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(['ui', 'governance', 'composite']).toContain(result.declaration.type)
      expect(result.declaration.permissions).toEqual(
        expect.arrayContaining(['plugin.enable', 'plugin.disable', 'audit.read']),
      )
    }
  })

  it('documents the official install input forms and registry rules', () => {
    expect(OFFICIAL_MANAGER_FACTS.package).toBe('@deepseek-ai/dsh-plugin-manager')
    expect(OFFICIAL_MANAGER_FACTS.installInputs).toEqual([
      'registry-package', 'absolute-path', 'git-url', 'tarball',
    ])
    expect(OFFICIAL_MANAGER_FACTS.registryOptions).toContain('fallbackRegistries')
    expect(OFFICIAL_MANAGER_FACTS.privateRegistryIsolated).toBe(true)
    expect(OFFICIAL_MANAGER_FACTS.officialApprovalDialog).toBe(false)
    expect(describeMarket()).toMatchObject({
      officialUi: 'ui-plugin-manager',
      approvalSurface: 'control-plane',
    })
  })

  it('keeps the enterprise surface to governance only', () => {
    expect(MARKET_PAGES.map((page) => page.id)).toEqual(['browse'])
    expect(MARKET_ACTIONS).toEqual(['browse', 'request-install', 'request-enable', 'request-disable'])
    expect(MARKET_PAGES[0]?.officialSurface).toBe('ui-plugin-manager')
    expect(MARKET_PAGES[0]?.enterpriseApproval).toBe('control-plane')
  })

  it('denies non-whitelisted installs through the reused governance hooks', async () => {
    const audits: string[] = []
    const hooks = createGovernanceHooks({
      whitelist: ['worknexus.knowledge'],
      audit: (entry) => {
        audits.push(`${entry.action}:${entry.result}`)
      },
    })
    await expect(hooks.onInstall({ pluginId: 'unknown.plugin', version: '1.0.0' })).resolves.toMatchObject({
      decision: 'deny',
    })
    await expect(hooks.onInstall({ pluginId: 'worknexus.knowledge', version: '1.0.0' })).resolves.toMatchObject({
      decision: 'allow',
    })
    expect(audits).toEqual(['plugin.install:denied', 'plugin.install:success'])
  })

  it('wraps the official manager as an injected port without reimplementing it', async () => {
    const calls: string[] = []
    const port: OfficialPluginManagerPort = {
      async listBundles() {
        calls.push('listBundles')
        return [{ name: '@worknexus/plugin-knowledge', enabled: true }]
      },
      async inspect(spec) {
        calls.push('inspect')
        return { name: spec, version: '1.0.0', isBundle: true }
      },
      async installBundle(request) {
        calls.push('installBundle')
        return { requestId: 'r1', application: 'applied', bundle: request.spec }
      },
      async waitForInstall() {
        calls.push('waitForInstall')
        return null
      },
      async cancelInstall() {
        calls.push('cancelInstall')
        return 'not-running'
      },
    }
    await expect(port.installBundle({ spec: 'worknexus.knowledge' })).resolves.toMatchObject({ application: 'applied' })
    await expect(port.inspect('worknexus.knowledge')).resolves.toMatchObject({ isBundle: true })
    expect(calls).toEqual(['installBundle', 'inspect'])
  })
})
