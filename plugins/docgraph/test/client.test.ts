/**
 * T-070：DocGraph 客户端——连接配置、健康检查、类型化错误与凭据边界。
 */

import { describe, expect, it, vi } from 'vitest'
import { parseEnterpriseDeclaration } from '@worknexus/plugin-runtime'
import manifest from '../plugin.manifest.json'
import {
  DocGraphHttpError,
  createDocGraphClient,
  mapRemoteStatus,
  type DocGraphFetchLike,
} from '../src/client.js'
import { DOCGRAPH_PAGES } from '../src/index.js'

const TOKEN = 'sk-docgraph-secret'

describe('docgraph client', () => {
  it('reports unreachable instead of throwing on connect failure', async () => {
    const client = createDocGraphClient({
      baseUrl: 'http://x',
      token: TOKEN,
      timeoutMs: 10,
      fetchImpl: vi.fn<DocGraphFetchLike>(async () => {
        throw new Error('ECONNREFUSED')
      }),
    })
    await expect(client.health()).resolves.toMatchObject({ ok: false })
  })

  it('reports healthy only when the remote health payload says ok', async () => {
    const client = createDocGraphClient({
      baseUrl: 'http://x',
      timeoutMs: 10,
      fetchImpl: vi.fn<DocGraphFetchLike>(
        async () => new Response(JSON.stringify({ status: 'ok', version: '1.0.0' }), { status: 200 }),
      ),
    })
    const report = await client.health()
    expect(report.ok).toBe(true)
    expect(report.detail).toContain('1.0.0')

    const degraded = createDocGraphClient({
      baseUrl: 'http://x',
      timeoutMs: 10,
      fetchImpl: vi.fn<DocGraphFetchLike>(
        async () => new Response(JSON.stringify({ status: 'down' }), { status: 200 }),
      ),
    })
    await expect(degraded.health()).resolves.toMatchObject({ ok: false })
  })

  it('normalizes an unexpected status into a typed error', async () => {
    const client = createDocGraphClient({
      baseUrl: 'http://x',
      token: TOKEN,
      timeoutMs: 10,
      fetchImpl: vi.fn<DocGraphFetchLike>(async () => new Response('nope', { status: 418 })),
    })
    await expect(client.status('j1')).rejects.toThrow(/docgraph-http-418/)
    await expect(client.status('j1')).rejects.toBeInstanceOf(DocGraphHttpError)
  })

  it('never leaks the credential into errors or the connection descriptor', async () => {
    const client = createDocGraphClient({
      baseUrl: 'http://x',
      token: TOKEN,
      timeoutMs: 10,
      fetchImpl: vi.fn<DocGraphFetchLike>(
        async () => new Response(`Authorization: Bearer ${TOKEN}`, { status: 500 }),
      ),
    })
    const error = await client.status('j1').catch((reason: unknown) => reason as Error)
    expect(String(error)).not.toContain(TOKEN)
    expect(JSON.stringify(client.describe())).not.toContain(TOKEN)
    expect(client.describe()).toMatchObject({ authNote: 'gateway-dependent', hasCredential: true })
  })

  it('submits review tasks through /api/reviews/start and allows an empty token', async () => {
    const fetchImpl = vi.fn<DocGraphFetchLike>(async () =>
      new Response(JSON.stringify({ id: 'task-1', status: 'pending' }), { status: 200 }),
    )
    const client = createDocGraphClient({ baseUrl: 'http://x', timeoutMs: 10, defaultSnapshotId: 'snap-9', fetchImpl })
    await expect(client.submit({ contractId: 'c1' })).resolves.toEqual({ jobId: 'task-1' })

    const call = fetchImpl.mock.calls[0]
    expect(call?.[0]).toBe('http://x/api/reviews/start')
    expect(call?.[1]?.headers?.Authorization).toBeUndefined()
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ contract_id: 'c1', snapshot_id: 'snap-9' })
  })

  it('maps remote status honestly and marks unsupported cancel as unsupported', async () => {
    expect(mapRemoteStatus('pending')).toBe('queued')
    expect(mapRemoteStatus('completed')).toBe('succeeded')
    expect(mapRemoteStatus('weird-state')).toBe('unknown')
    expect(mapRemoteStatus(null)).toBe('unknown')

    const fetchImpl = vi.fn<DocGraphFetchLike>(async () =>
      new Response(JSON.stringify({ id: 'j1', status: 'running', progress: 40, stage: 'llm' }), { status: 200 }),
    )
    const client = createDocGraphClient({ baseUrl: 'http://x', timeoutMs: 10, fetchImpl })
    await expect(client.status('j1')).resolves.toMatchObject({
      jobId: 'j1',
      state: 'running',
      rawStatus: 'running',
      progress: 40,
      stage: 'llm',
    })
    const cancelled = await client.cancel('j1')
    expect(cancelled).toMatchObject({ ok: false, supported: false })
    expect(cancelled.detail).toContain('docgraph-unsupported')
    expect(fetchImpl).toHaveBeenCalledTimes(1)
  })

  it('fetches results from the by-rule endpoint', async () => {
    const fetchImpl = vi.fn<DocGraphFetchLike>(async () =>
      new Response(JSON.stringify({ task_id: 'j1', results: [], summary: {} }), { status: 200 }),
    )
    const client = createDocGraphClient({ baseUrl: 'http://x', timeoutMs: 10, fetchImpl })
    await expect(client.result('j1')).resolves.toMatchObject({ task_id: 'j1' })
    expect(String(fetchImpl.mock.calls[0]?.[0])).toBe('http://x/api/reviews/j1/by-rule')
  })

  it('declares the official plugin manifest and the connection page', () => {
    const parsed = parseEnterpriseDeclaration(manifest)
    expect(parsed.ok).toBe(true)
    if (parsed.ok) {
      expect(parsed.declaration.permissions).toEqual(
        expect.arrayContaining(['space.read', 'docgraph.submit', 'docgraph.read']),
      )
    }
    expect(DOCGRAPH_PAGES.map((page) => page.id)).toEqual(['connection', 'submit', 'jobs'])
  })
})
