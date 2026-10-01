/**
 * T-029：契约骨架的类型与版本可导入性 + 关键语义断言。
 *
 * 这些断言刻意只覆盖「契约层」的可判定性质（版本格式、只读语义、缺省拒绝、
 * 命名空间白名单、null 不猜），不涉及任何企业业务实现。
 */

import { describe, expect, it } from 'vitest'

import {
  AUDIT_SUMMARY_MAX_LENGTH,
  DENY_ALL_POLICY,
  ENTERPRISE_EVENT_TOPICS,
  ENTERPRISE_FIELD_PREFIX,
  HOST_CORE_CONTRACT_VERSION,
  PERSONAL_IDENTITY,
  READ_ONLY_FOR_VIEWER_POLICY,
  ROLES,
  assertEnterpriseTopic,
  deriveTotalTokens,
  hasAtLeastRole,
  isEnterpriseTopic,
  summarize,
  type AuditSink,
  type EventBus,
  type PermissionPolicy,
  type PluginGovernanceView,
  type SpaceContext,
  type UpdateManager,
  type UsageLedger,
} from '../src/index.js'

describe('契约版本', () => {
  it('声明语义化契约版本', () => {
    expect(HOST_CORE_CONTRACT_VERSION).toMatch(/^\d+\.\d+\.\d+$/)
  })

  it('企业字段使用 ent 前缀命名空间', () => {
    expect(ENTERPRISE_FIELD_PREFIX).toBe('ent')
  })
})

describe('契约① IdentityContext / ② SpaceContext', () => {
  it('个人模式常量即 P1 默认形态', () => {
    expect(PERSONAL_IDENTITY.mode).toBe('personal')
    expect(PERSONAL_IDENTITY.organizationIds).toEqual([])
  })

  it('只有四类角色，且角色序可用于最小角色判断', () => {
    expect(ROLES).toEqual(['owner', 'admin', 'member', 'viewer'])
    const viewer: SpaceContext = { organizationId: 'o', role: 'viewer' }
    const admin: SpaceContext = { organizationId: 'o', role: 'admin' }
    expect(hasAtLeastRole(viewer, 'member')).toBe(false)
    expect(hasAtLeastRole(admin, 'member')).toBe(true)
  })
})

describe('契约③ PermissionPolicy：默认最小权限', () => {
  it('DENY_ALL 对任何操作都拒绝', () => {
    const actor: SpaceContext = { organizationId: 'o', role: 'owner' }
    expect(DENY_ALL_POLICY.can(actor, 'budget.write', { type: 'org', id: 'o' })).toBe(false)
  })

  it('viewer 不能写空间，且可达 PermissionPolicy 类型', () => {
    const policy: PermissionPolicy = READ_ONLY_FOR_VIEWER_POLICY
    const viewer: SpaceContext = { organizationId: 'o', role: 'viewer' }
    expect(policy.can(viewer, 'space.write', { type: 'space', id: 's' })).toBe(false)
    expect(policy.can(viewer, 'space.read', { type: 'space', id: 's' })).toBe(true)
  })
})

describe('契约④ AuditSink：只写且最小采集', () => {
  it('write 只接收不含 id/timestamp 的事件，且摘要被截断', async () => {
    const seen: string[] = []
    const sink: AuditSink = {
      async write(event) {
        seen.push(event.summary)
      },
    }
    await sink.write({
      userId: 'u',
      organizationId: 'o',
      action: 'contracts.test',
      resourceType: 'test',
      result: 'success',
      device: 'unit-test',
      summary: summarize('x'.repeat(500)),
    })
    expect(seen).toHaveLength(1)
    expect(seen[0]!.length).toBeLessThanOrEqual(AUDIT_SUMMARY_MAX_LENGTH)
  })
})

describe('契约⑤ UsageLedger：缺字段留空不猜', () => {
  it('任一为 null 时 total 为 null', () => {
    expect(deriveTotalTokens(10, null)).toBeNull()
    expect(deriveTotalTokens(null, 5)).toBeNull()
    expect(deriveTotalTokens(10, 5)).toBe(15)
  })

  it('UsageLedger 契约可被实现且只追加', async () => {
    const rows: string[] = []
    const ledger: UsageLedger = {
      async record(entry) {
        rows.push(`${entry.source}:${entry.totalTokens ?? 'null'}`)
      },
      async query() {
        return []
      },
    }
    await ledger.record({
      organizationId: 'o',
      spaceId: null,
      userId: 'u',
      sessionId: 's',
      pluginId: null,
      provider: 'deepseek',
      model: 'deepseek-flash',
      promptTokens: 10,
      completionTokens: null,
      totalTokens: null,
      estimatedCost: null,
      source: 'dsh_event',
    })
    expect(rows).toEqual(['dsh_event:null'])
    expect('update' in ledger).toBe(false)
    expect('delete' in ledger).toBe(false)
  })
})

describe('契约⑥ EventBus：企业命名空间白名单', () => {
  it('白名单外的事件一律拒绝', () => {
    expect(isEnterpriseTopic('ent.identity.changed')).toBe(true)
    expect(isEnterpriseTopic('session.created')).toBe(false)
    expect(() => assertEnterpriseTopic('official.topic')).toThrow(/not in the enterprise whitelist/)
  })

  it('订阅返回取消函数', async () => {
    const bus: EventBus = {
      async publish() {},
      subscribe(_topic, _handler) {
        return () => {}
      },
      allowedTopics: () => ENTERPRISE_EVENT_TOPICS,
    }
    const off = bus.subscribe('ent.space.switched', () => {})
    expect(typeof off).toBe('function')
    expect(bus.allowedTopics().length).toBeGreaterThan(0)
  })
})

describe('契约⑦ PluginGovernanceView：只读镜像，无启停语义', () => {
  it('契约面不存在 enable / disable 方法', async () => {
    const view: PluginGovernanceView = {
      async list() {
        return []
      },
      async stateOf() {
        return 'installed'
      },
      isAllowed: () => false,
    }
    expect('enable' in view).toBe(false)
    expect('disable' in view).toBe(false)
    expect(await view.stateOf('x')).toBe('installed')
  })
})

describe('契约⑧ UpdateManager：四方法与「最近可用」回滚', () => {
  it('check / download / install / rollback 齐备，回滚返回 restoredVersion', async () => {
    const manager: UpdateManager = {
      async check(input) {
        return {
          available: false,
          currentVersion: input.currentVersion,
          targetVersion: null,
          mandatory: input.mandatory,
          channel: input.channel,
        }
      },
      async download() {
        return { ok: true }
      },
      async install() {
        return { ok: true }
      },
      async rollback() {
        return { ok: true, restoredVersion: '0.1.7-rc.2', detail: '最近可用版本' }
      },
      async upstreamPin() {
        return { tag: 'dsh-v0.2.0-rc.1', commit: '4878cdab', diffsetPatch: null, rebaseDrillRecord: null }
      },
    }
    const result = await manager.check({ currentVersion: '0.2.0-rc.1', channel: 'stable', mandatory: false })
    expect(result.channel).toBe('stable')
    const rolled = await manager.rollback({ organizationId: 'o' })
    expect(rolled.ok).toBe(true)
    expect(rolled.restoredVersion).toBe('0.1.7-rc.2')
  })
})
