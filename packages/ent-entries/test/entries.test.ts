/**
 * T-024：企业入口按运行模式门控 + 插件启停联动。
 *
 * 核心断言（对应派发卡验证项）：
 *  - 个人模式下四个企业入口**必须隐藏**且**不报错**；
 *  - 缺少模式上下文时按 personal 处理；
 *  - 插件禁用后入口同步消失；
 *  - 本模块不提供插件启停能力（官方 plugin manager 是唯一权威）。
 */

import { describe, expect, it } from 'vitest'

import {
  ENTERPRISE_ENTRIES,
  applyPluginLifecycle,
  createMemoryEntryHost,
  resolveRunMode,
  syncEnterpriseEntries,
  visibleEntriesFor,
} from '../src/index.js'

describe('运行模式判定', () => {
  it('缺少上下文一律按 personal', () => {
    expect(resolveRunMode()).toBe('personal')
    expect(resolveRunMode({})).toBe('personal')
    expect(resolveRunMode({ signedIn: true })).toBe('personal')
    expect(resolveRunMode({ signedIn: true, organizationId: null })).toBe('personal')
    expect(resolveRunMode({ signedIn: false, organizationId: 'org-1' })).toBe('personal')
  })

  it('已登录且已选定组织才是 enterprise', () => {
    expect(resolveRunMode({ signedIn: true, organizationId: 'org-1' })).toBe('enterprise')
  })
})

describe('入口可见性', () => {
  it('个人模式无可见入口', () => {
    expect(visibleEntriesFor('personal')).toEqual([])
  })

  it('企业模式四个入口', () => {
    expect(visibleEntriesFor('enterprise')).toHaveLength(4)
    expect(ENTERPRISE_ENTRIES.map((e) => e.id)).toEqual([
      'ent-admin',
      'ent-knowledge',
      'ent-docgraph',
      'ent-ipd',
    ])
  })
})

describe('入口同步（个人模式是 P1 唯一分支）', () => {
  it('个人模式下不注册任何入口，且不抛错', () => {
    const host = createMemoryEntryHost()
    const result = syncEnterpriseEntries(host, 'personal')
    expect(result).toEqual({ added: [], removed: [] })
    expect(host.list()).toEqual([])
  })

  it('个人 → 企业 → 个人 的切换是幂等且可逆的', () => {
    const host = createMemoryEntryHost()
    expect(syncEnterpriseEntries(host, 'personal').added).toEqual([])

    const up = syncEnterpriseEntries(host, 'enterprise')
    expect(up.added).toHaveLength(4)
    expect(up.removed).toEqual([])
    // 幂等：再调用不重复注册
    expect(syncEnterpriseEntries(host, 'enterprise')).toEqual({ added: [], removed: [] })

    const down = syncEnterpriseEntries(host, 'personal')
    expect(down.removed).toHaveLength(4)
    expect(host.list()).toEqual([])
  })
})

describe('插件启停联动', () => {
  it('禁用插件后其入口消失；重新启用后按当前模式恢复', () => {
    const host = createMemoryEntryHost()
    syncEnterpriseEntries(host, 'enterprise')
    expect(host.list()).toHaveLength(4)

    const off = applyPluginLifecycle(host, 'enterprise', { pluginId: '@worknexus/ent-docgraph', state: 'disabled' })
    expect(off.removed).toEqual(['ent-docgraph'])
    expect(host.list()).not.toContain('ent-docgraph')
    expect(host.list()).toHaveLength(3)

    const on = applyPluginLifecycle(host, 'enterprise', { pluginId: '@worknexus/ent-docgraph', state: 'enabled' })
    expect(on.added).toEqual(['ent-docgraph'])
    expect(host.list()).toHaveLength(4)
  })

  it('卸载与禁用等效；个人模式下启用也不注册入口', () => {
    const host = createMemoryEntryHost()
    syncEnterpriseEntries(host, 'enterprise')
    applyPluginLifecycle(host, 'enterprise', { pluginId: '@worknexus/ent-ipd', state: 'uninstalled' })
    expect(host.list()).not.toContain('ent-ipd')

    const personalHost = createMemoryEntryHost()
    const r = applyPluginLifecycle(personalHost, 'personal', { pluginId: '@worknexus/ent-admin', state: 'enabled' })
    expect(r).toEqual({ added: [], removed: [] })
    expect(personalHost.list()).toEqual([])
  })
})

describe('边界：不提供插件启停能力', () => {
  it('导出的 API 中没有 enable/disable 插件状态的方法', async () => {
    const mod = await import('../src/index.js')
    const names = Object.keys(mod)
    expect(names).not.toContain('enablePlugin')
    expect(names).not.toContain('disablePlugin')
  })
})
