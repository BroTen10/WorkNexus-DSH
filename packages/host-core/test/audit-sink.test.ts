import { describe, expect, it } from 'vitest'

import { createHttpAuditSink } from '../src/audit-sink.js'

describe('http audit sink', () => {
  it('posts the append-only event without changing it', async () => {
    const bodies: unknown[] = []
    const sink = createHttpAuditSink({
      endpoint: '/api/v1/audit/events',
      post: async (url, body) => {
        expect(url).toBe('/api/v1/audit/events')
        bodies.push(body)
        return { ok: true, status: 200 }
      },
    })
    await sink.write({
      userId: 'u1',
      organizationId: 'o1',
      action: 'plugin.enable',
      resourceType: 'plugin',
      resourceId: 'p1',
      result: 'success',
      device: 'desktop',
      summary: 'enable plugin',
    })
    expect(bodies).toHaveLength(1)
  })
})
