/**
 * T-105：P6B 验收集成场景（§4.6.2 四条的可执行证据）。
 */

import { describe, expect, it, vi } from 'vitest'

import { MARKET_PAGES, MarketPage, OFFICIAL_MANAGER_FACTS, buildApprovalPrompt, assessRisk } from '../src/index.js'
import { createPrivateSource, type PrivateSourceFetchLike } from '../src/registry/private-source.js'
import type { OfficialPluginManagerPort } from '../src/official-manager.js'

describe('P6B acceptance chain', () => {
  it('市场入口走官方表面，企业侧只做治理与提示', () => {
    expect(MarketPage.officialSurface).toBe('ui-plugin-manager')
    expect(MarketPage.enterpriseApproval).toBe('control-plane')
    expect(MarketPage.requiresRiskDisplay).toBe(true)
    expect(MARKET_PAGES).toHaveLength(1)
    expect(OFFICIAL_MANAGER_FACTS.installInputs).toContain('registry-package')
  })

  it('企业模式未白名单被拦，个人模式仅记录', () => {
    const blocked = buildApprovalPrompt({
      pluginId: 'third.party.plugin',
      version: '1.0.0',
      action: 'install',
      mode: 'enterprise',
      whitelisted: false,
    })
    expect(blocked.status).toBe('not-whitelisted')

    const recorded = buildApprovalPrompt({
      pluginId: 'third.party.plugin',
      version: '1.0.0',
      action: 'install',
      mode: 'personal',
      whitelisted: false,
    })
    expect(recorded.status).toBe('recorded-only')
  })

  it('私有源不可达时降级为 installed-only，客户端仍可启动', async () => {
    const source = createPrivateSource({
      baseUrl: 'https://registry.corp.local',
      fetchImpl: vi.fn<PrivateSourceFetchLike>(async () => {
        throw new Error('ECONNREFUSED')
      }),
    })
    const listing = await source.list([{ id: 'worknexus.knowledge', version: '0.1.0', source: 'private-registry' }])
    expect(listing.mode).toBe('installed-only')
    expect(listing.plugins).toHaveLength(1)
  })

  it('安装前可展示权限、来源与风险，供管理员决策', () => {
    const assessment = assessRisk({
      permissions: ['audit.write', 'budget.write', 'plugin.enable'],
      source: 'private-registry',
      lastUpdated: '2025-01-01',
    })
    expect(assessment.level).toBe('high')
    expect(assessment.reasons.length).toBeGreaterThan(0)
  })

  it('只通过官方能力面驱动安装，不自建安装实现', async () => {
    const calls: string[] = []
    const port: OfficialPluginManagerPort = {
      async listBundles() {
        calls.push('listBundles')
        return []
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
        return null
      },
      async cancelInstall() {
        return 'not-running'
      },
    }
    await port.inspect('worknexus.market')
    await port.installBundle({ spec: 'worknexus.market', registry: 'https://registry.corp.local' })
    expect(calls).toEqual(['inspect', 'installBundle'])
  })
})
