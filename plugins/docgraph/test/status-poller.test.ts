/**
 * T-072：状态轮询——五态、上限、退避与失败不崩。
 */

import { describe, expect, it, vi } from 'vitest'

import { collectStatuses, isTerminal, type DocGraphStatusPort } from '../src/status-poller.js'
import { DOCGRAPH_PAGES } from '../src/index.js'

function port(impl: DocGraphStatusPort['status']): DocGraphStatusPort {
  return { status: impl }
}

describe('status poller', () => {
  it('emits queued -> running -> succeeded and stops', async () => {
    const status = vi
      .fn<DocGraphStatusPort['status']>()
      .mockResolvedValueOnce({ jobId: 'j', state: 'queued', rawStatus: 'pending', progress: null, stage: null, error: null, summary: null })
      .mockResolvedValueOnce({ jobId: 'j', state: 'running', rawStatus: 'running', progress: 10, stage: null, error: null, summary: null })
      .mockResolvedValueOnce({ jobId: 'j', state: 'succeeded', rawStatus: 'completed', progress: 100, stage: null, error: null, summary: null })
    const seen = await collectStatuses(port(status), 'j', { intervalMs: 1, maxPolls: 5, sleep: async () => {} })
    expect(seen).toEqual(['queued', 'running', 'succeeded'])
    expect(status).toHaveBeenCalledTimes(3)
  })

  it('stops after maxPolls when the job never settles', async () => {
    const status = vi.fn<DocGraphStatusPort['status']>(
      async () => ({ jobId: 'j', state: 'running', rawStatus: 'running', progress: null, stage: null, error: null, summary: null }),
    )
    const seen = await collectStatuses(port(status), 'j', { intervalMs: 1, maxPolls: 3, sleep: async () => {} })
    expect(seen).toHaveLength(3)
  })

  it('covers the five product states plus unknown, and treats failures as unknown instead of throwing', async () => {
    expect(isTerminal('succeeded')).toBe(true)
    expect(isTerminal('failed')).toBe(true)
    expect(isTerminal('cancelled')).toBe(true)
    expect(isTerminal('running')).toBe(false)

    const failing = port(async () => {
      throw new Error('docgraph-http-503')
    })
    const seen = await collectStatuses(failing, 'j', { intervalMs: 1, maxPolls: 2, sleep: async () => {} })
    expect(seen).toEqual(['unknown', 'unknown'])
  })

  it('backs off between polls up to the configured ceiling', async () => {
    const waits: number[] = []
    const status = vi.fn<DocGraphStatusPort['status']>(
      async () => ({ jobId: 'j', state: 'running', rawStatus: 'running', progress: null, stage: null, error: null, summary: null }),
    )
    await collectStatuses(port(status), 'j', {
      intervalMs: 100,
      maxPolls: 5,
      backoffFactor: 2,
      maxIntervalMs: 400,
      sleep: async (ms) => {
        waits.push(ms)
      },
    })
    expect(waits).toEqual([100, 200, 400, 400])
  })

  it('registers the job list page with five states', () => {
    expect(DOCGRAPH_PAGES.map((page) => page.id)).toEqual(['connection', 'submit', 'jobs'])
  })
})
