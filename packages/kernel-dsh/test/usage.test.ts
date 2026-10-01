import { describe, expect, it } from 'vitest'

import { toUsageRecord } from '../src/usage.js'

describe('toUsageRecord', () => {
  it('marks unavailable fields as null instead of zero', () => {
    const record = toUsageRecord({
      sessionId: 's1',
      userId: 'u1',
      organizationId: 'o1',
      provider: 'deepseek',
      model: 'm',
      totalTokens: undefined,
    })
    expect(record.totalTokens).toBeNull()
    expect(record.promptTokens).toBeNull()
    expect(record.completionTokens).toBeNull()
    expect(record.estimatedCost).toBeNull()
  })

  it('labels projected values as dsh_event and imprecise values as adapter_estimate', () => {
    const precise = toUsageRecord({
      sessionId: 's1', userId: 'u1', organizationId: 'o1',
      provider: 'deepseek', model: 'm', totalTokens: 10, promptTokens: 4, completionTokens: 6,
    })
    expect(precise.source).toBe('dsh_event')
    const estimated = toUsageRecord({
      sessionId: 's1', userId: 'u1', organizationId: 'o1',
      provider: 'deepseek', model: 'm', totalTokens: 1234, precise: false,
    })
    expect(estimated.source).toBe('adapter_estimate')
    expect(estimated.totalTokens).toBe(1234)
  })

  it('does not derive total when either component is missing', () => {
    const record = toUsageRecord({
      sessionId: 's1', userId: 'u1', organizationId: 'o1',
      provider: 'deepseek', model: 'm', promptTokens: 10,
    })
    expect(record.totalTokens).toBeNull()
  })
})
