/**
 * T-061：通用 `http-rag` Provider 的四态健康检查、配置校验与凭据边界。
 */

import { describe, expect, it, vi } from 'vitest'

import {
  createHttpRagProvider,
  describeConnection,
  type HttpRagFetchLike,
} from '../src/providers/http-rag.js'

const TOKEN = 'sk-rag-secret-token'

function fetchReturning(response: Response | Error) {
  return vi.fn(async () => {
    if (response instanceof Error) throw response
    return response
  })
}

describe('http-rag provider', () => {
  it('maps 401 to auth_failed instead of throwing', async () => {
    const provider = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      fetchImpl: fetchReturning(new Response('', { status: 401 })),
    })
    await expect(provider.healthCheck()).resolves.toMatchObject({ state: 'auth_failed' })
  })

  it('maps 403 to auth_failed', async () => {
    const provider = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      fetchImpl: fetchReturning(new Response('', { status: 403 })),
    })
    await expect(provider.healthCheck()).resolves.toMatchObject({ state: 'auth_failed' })
  })

  it('maps a timeout or connection error to unreachable', async () => {
    const provider = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      timeoutMs: 10,
      fetchImpl: fetchReturning(new Error('aborted')),
    })
    await expect(provider.healthCheck()).resolves.toMatchObject({ state: 'unreachable' })
  })

  it('maps a healthy payload to healthy and a server/index fault to sync_failed', async () => {
    const healthy = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      fetchImpl: fetchReturning(
        new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
      ),
    })
    await expect(healthy.healthCheck()).resolves.toMatchObject({ state: 'healthy' })

    const faulted = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      fetchImpl: fetchReturning(new Response('boom', { status: 503 })),
    })
    await expect(faulted.healthCheck()).resolves.toMatchObject({ state: 'sync_failed' })

    const indexFault = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      fetchImpl: fetchReturning(
        new Response(JSON.stringify({ status: 'sync_failed', detail: 'index rebuild pending' }), { status: 200 }),
      ),
    })
    await expect(indexFault.healthCheck()).resolves.toMatchObject({ state: 'sync_failed' })
  })

  it('reports field-level config problems without leaking the token', () => {
    const provider = createHttpRagProvider({ baseUrl: '', token: '', timeoutMs: 0 })
    const result = provider.validateConfig({ baseUrl: '', token: '', timeoutMs: 0 })
    expect(result.ok).toBe(false)
    expect(result.problems.join(' | ')).toContain('baseUrl')
    expect(result.problems.join(' | ')).toContain('timeoutMs')
    expect(result.problems.join(' | ')).not.toContain(TOKEN)
    expect(provider.validateConfig({ baseUrl: 'ftp://rag', token: 'x' }).ok).toBe(false)
    expect(provider.validateConfig({ baseUrl: 'http://rag', token: 'x' }).ok).toBe(true)
  })

  it('never leaks the credential into health detail or the UI descriptor', async () => {
    const failing = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      fetchImpl: fetchReturning(new Error(`connect failed with Authorization: Bearer ${TOKEN}`)),
    })
    const report = await failing.healthCheck()
    expect(report.detail ?? '').not.toContain(TOKEN)
    expect(JSON.stringify(report)).not.toContain(TOKEN)

    const descriptor = describeConnection({ baseUrl: 'http://rag.local', token: TOKEN })
    expect(descriptor).toEqual({
      baseUrl: 'http://rag.local',
      searchPath: '/api/v1/retrieval',
      healthPath: '/api/v1/health',
      timeoutMs: 5000,
      defaultLimit: 10,
      hasCredential: true,
    })
    expect(JSON.stringify(descriptor)).not.toContain(TOKEN)
  })

  it('degrades to an empty result when the provider is unreachable', async () => {
    const provider = createHttpRagProvider({
      baseUrl: 'http://rag.local',
      token: TOKEN,
      fetchImpl: fetchReturning(new Error('ECONNREFUSED')),
    })
    await expect(
      provider.retrieve({ query: '合同模板', spaceContext: { organizationId: 'o', role: 'member' }, limit: 5 }),
    ).resolves.toEqual([])
  })

  it('maps provider payload into contract chunks, dropping malformed entries', async () => {
    const fetchImpl = vi.fn<HttpRagFetchLike>(async () =>
      new Response(
        JSON.stringify({
          chunks: [
            { document_id: 'd1', document_name: '合同模板', content: '条款 A', link: 'https://x/1', similarity: 0.9, space_id: 's1' },
            { document_id: 'd2' },
          ],
        }),
        { status: 200 },
      ),
    )
    const provider = createHttpRagProvider({ baseUrl: 'http://rag.local', token: TOKEN, fetchImpl })
    const chunks = await provider.retrieve({
      query: '合同',
      spaceContext: { organizationId: 'o', projectSpaceId: 's1', role: 'member' },
      limit: 5,
    })
    expect(chunks).toEqual([
      { documentId: 'd1', title: '合同模板', snippet: '条款 A', url: 'https://x/1', score: 0.9, spaceId: 's1' },
    ])
    const sent = JSON.parse(String(fetchImpl.mock.calls[0]?.[1]?.body))
    expect(sent.topK).toBe(5)
    expect(sent.spaceIds).toEqual(['s1'])
  })
})
