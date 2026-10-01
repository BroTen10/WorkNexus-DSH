/**
 * T-101：私有插件源与降级。
 */

import { describe, expect, it, vi } from 'vitest'

import {
  createPrivateSource,
  type PrivateSourceFetchLike,
  type PrivateSourcePlugin,
} from '../src/registry/private-source.js'

const TOKEN = 'sk-registry-secret'

describe('private source', () => {
  it('degrades to installed-only when the registry is unreachable', async () => {
    const source = createPrivateSource({
      baseUrl: 'http://registry.local',
      token: TOKEN,
      fetchImpl: vi.fn<PrivateSourceFetchLike>(async () => {
        throw new Error('ECONNREFUSED')
      }),
    })
    const installed: PrivateSourcePlugin[] = [{ id: 'worknexus.knowledge', version: '0.1.0', source: 'private-registry' }]
    const listing = await source.list(installed)
    expect(listing.mode).toBe('installed-only')
    expect(listing.plugins).toEqual(installed)
    expect(listing.detail ?? '').not.toContain(TOKEN)
  })

  it('never blocks startup: creating the source performs no request', () => {
    const fetchImpl = vi.fn<PrivateSourceFetchLike>(async () => new Response('{}', { status: 200 }))
    const source = createPrivateSource({ baseUrl: 'http://registry.local', token: TOKEN, fetchImpl })
    expect(fetchImpl).not.toHaveBeenCalled()
    expect(source.describe()).toMatchObject({ fallbackToPublic: false, hasCredential: true })
    expect(JSON.stringify(source.describe())).not.toContain(TOKEN)
  })

  it('lists plugins from the private registry without falling back to public sources', async () => {
    const fetchImpl = vi.fn<PrivateSourceFetchLike>(
      async () => new Response(JSON.stringify({ plugins: [{ id: 'worknexus.ipd', version: '0.1.0' }, { name: 'x' }] }), { status: 200 }),
    )
    const source = createPrivateSource({ baseUrl: 'http://registry.local', token: TOKEN, fetchImpl })
    const listing = await source.list()
    expect(listing.mode).toBe('registry')
    expect(listing.plugins).toEqual([{ id: 'worknexus.ipd', version: '0.1.0', source: 'private-registry' }])
    const call = fetchImpl.mock.calls[0]
    expect(call?.[0]).toBe('http://registry.local/-/v1/search?text=worknexus')
    expect(call?.[1]?.headers?.Authorization).toBe(`Bearer ${TOKEN}`)
  })

  it('reports an explicit detail when the registry answers with an error status', async () => {
    const source = createPrivateSource({
      baseUrl: 'http://registry.local',
      fetchImpl: vi.fn<PrivateSourceFetchLike>(async () => new Response('nope', { status: 503 })),
    })
    const listing = await source.list()
    expect(listing).toMatchObject({ mode: 'installed-only', detail: 'private-registry: HTTP 503' })
  })
})
