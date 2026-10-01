/**
 * T-104：安全提示——权限 / 来源 / 风险 / 最近更新。
 */

import { describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'

import { RiskDisplay, assessRisk } from '../src/risk-display.js'
import { MarketPage } from '../src/pages/Market.js'

describe('risk display', () => {
  it('shows permissions, source and last update', () => {
    const html = renderToString(
      <RiskDisplay
        info={{ permissions: ['kb.retrieve', 'audit.write'], source: 'private-registry', lastUpdated: '2026-09-01' }}
      />,
    )
    expect(html).toContain('kb.retrieve')
    expect(html).toContain('private-registry')
    expect(html).toContain('2026-09-01')
  })

  it('keeps the source and permission list visible regardless of risk level', () => {
    const html = renderToString(
      <RiskDisplay
        info={{ permissions: ['space.read'], source: 'local', lastUpdated: '2026-09-20' }}
      />,
    )
    expect(html).toContain('来源：')
    expect(html).toContain('local')
    expect(html).toContain('space.read')
    expect(html).toContain('data-risk="low"')
  })

  it('raises the risk level with sensitive permissions, untrusted source and stale updates', () => {
    const low = assessRisk({ permissions: ['space.read'], source: 'local', lastUpdated: '2026-09-20' })
    expect(low.level).toBe('low')

    const medium = assessRisk({
      permissions: ['space.read', 'kb.bind'],
      source: 'local',
      lastUpdated: '2026-09-20',
    })
    expect(medium.level).toBe('medium')
    expect(medium.sensitivePermissions).toEqual(['kb.bind'])

    const high = assessRisk({
      permissions: ['audit.write', 'budget.write', 'plugin.enable'],
      source: 'private-registry',
      lastUpdated: '2025-01-01',
    })
    expect(high.level).toBe('high')
    expect(high.reasons.join(' | ')).toContain('敏感权限 3 项')
    expect(high.reasons.join(' | ')).toContain('私有源')
    expect(high.reasons.join(' | ')).toContain('超过 180 天')
  })

  it('flags missing update information and requires the display on the market page', () => {
    const unknown = assessRisk({ permissions: [], source: 'official', lastUpdated: 'not-a-date' })
    expect(unknown.level).toBe('medium')
    expect(unknown.reasons.join(' | ')).toContain('缺少可解析的最近更新时间')
    expect(MarketPage.requiresRiskDisplay).toBe(true)
  })
})
