/**
 * T-075：Agent 会话联动——空间约束的引用、预置 prompt 与「不支持」的显式返回。
 */

import { describe, expect, it } from 'vitest'

import {
  UNSUPPORTED_AGENT_CAPABILITIES,
  buildReferencePrompt,
  buildResultReference,
  decideReference,
  referenceIsVisible,
  requestUnsupportedCapability,
} from '../src/agent-bridge.js'

const member = { organizationId: 'o', departmentId: 'd1', projectSpaceId: 's1', role: 'member' as const }

describe('agent bridge', () => {
  it('builds a space-scoped reference the agent can cite', () => {
    const ref = buildResultReference({ jobId: 'j1', spaceId: 's1', summary: '3 项风险' })
    expect(ref).toMatchObject({ type: 'docgraph.result', jobId: 'j1', spaceId: 's1' })
    expect(ref.text).toContain('3 项风险')
  })

  it('includes the source link and finding count when provided', () => {
    const ref = buildResultReference({
      jobId: 'j1',
      spaceId: 's1',
      summary: '2 项风险',
      sourceUrl: 'https://d/1',
      findingCount: 2,
    })
    expect(ref.text).toContain('https://d/1')
    expect(ref.text).toContain('共 2 项发现')
    expect(buildReferencePrompt(ref)).toContain('【DocGraph 结果引用】')
  })

  it('keeps out-of-space results out of the session', () => {
    const foreign = buildResultReference({ jobId: 'j2', spaceId: 'other', summary: '别的空间' })
    expect(referenceIsVisible(foreign, member)).toBe(false)
    expect(decideReference(foreign, member)).toEqual({ ok: false, reason: 'denied' })

    const own = buildResultReference({ jobId: 'j3', spaceId: 's1', summary: '本空间' })
    expect(decideReference(own, member)).toMatchObject({ ok: true })
    // 部门与组织范围内的结果同样可见（与 T-062 的空间过滤口径一致）
    expect(referenceIsVisible(buildResultReference({ jobId: 'j4', spaceId: 'd1', summary: '部门' }), member)).toBe(true)
  })

  it('returns an explicit unsupported result instead of pretending', () => {
    expect(UNSUPPORTED_AGENT_CAPABILITIES).toContain('session.fork')
    const denied = requestUnsupportedCapability('session.delete')
    expect(denied).toMatchObject({ ok: false, unsupported: true })
    expect(denied.detail).toContain('agent-unsupported')
    expect(denied.detail).toContain('降级为复制结果摘要到会话')
  })
})
