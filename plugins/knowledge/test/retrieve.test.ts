/**
 * T-062：检索前权限判定、检索后空间过滤（P3-F05）。
 */

import { describe, expect, it, vi } from 'vitest'
import type { Action, KnowledgeChunk, KnowledgeProvider, PermissionPolicy, ResourceRef, SpaceContext } from '@worknexus/contracts'

import { retrieveForSpace } from '../src/retrieve.js'

function policy(allowed: boolean): PermissionPolicy {
  return {
    can: (_actor: SpaceContext, _action: Action, _resource: ResourceRef) => allowed,
  }
}

type RetrieveFn = KnowledgeProvider['retrieve']

function retrieveMock(impl?: RetrieveFn): RetrieveFn & { mock: { calls: unknown[][] } } {
  return vi.fn<RetrieveFn>(impl ?? (async () => [])) as RetrieveFn & { mock: { calls: unknown[][] } }
}

function providerWith(chunks: KnowledgeChunk[], retrieve?: RetrieveFn): KnowledgeProvider {
  return {
    id: 'http-rag',
    healthCheck: async () => ({ state: 'healthy' }),
    validateConfig: () => ({ ok: true, problems: [] }),
    retrieve: retrieve ?? retrieveMock(async () => chunks),
  }
}

describe('space-scoped retrieval', () => {
  it('does not call the provider when the actor lacks kb.retrieve', async () => {
    const retrieve = retrieveMock(async () => [])
    const provider = providerWith([], retrieve)
    const out = await retrieveForSpace({
      query: 'q',
      limit: 5,
      provider,
      policy: policy(false),
      spaceContext: { organizationId: 'o', role: 'viewer' },
    })
    expect(out).toEqual([])
    expect(retrieve).not.toHaveBeenCalled()
  })

  it('passes the space context through and slices to the requested limit', async () => {
    const chunk: KnowledgeChunk = { documentId: 'd1', title: 't', snippet: 's', score: 1, spaceId: 'mine' }
    const retrieve = retrieveMock(async () => [chunk, chunk, chunk])
    const out = await retrieveForSpace({
      query: 'q',
      limit: 2,
      provider: providerWith([], retrieve),
      policy: policy(true),
      spaceContext: { organizationId: 'o', projectSpaceId: 'mine', role: 'member' },
    })
    expect(retrieve).toHaveBeenCalledTimes(1)
    expect(retrieve.mock.calls[0]?.[0]).toMatchObject({ query: 'q', limit: 2 })
    expect(out).toHaveLength(2)
  })

  it('drops chunks bound to another project space', async () => {
    const provider = providerWith([
      { documentId: 'd1', title: 't', snippet: 's', score: 1, spaceId: 'other' },
    ])
    const out = await retrieveForSpace({
      query: 'q',
      limit: 5,
      provider,
      policy: policy(true),
      spaceContext: { organizationId: 'o', projectSpaceId: 'mine', role: 'member' },
    })
    expect(out).toEqual([])
  })

  it('accepts chunks from the department or organization scope of the session', async () => {
    const provider = providerWith([
      { documentId: 'd-dep', title: 't', snippet: 's', score: 1, spaceId: 'dept' },
      { documentId: 'd-org', title: 't', snippet: 's', score: 1, spaceId: 'o' },
      { documentId: 'd-other', title: 't', snippet: 's', score: 1, spaceId: 'other' },
    ])
    const out = await retrieveForSpace({
      query: 'q',
      limit: 5,
      provider,
      policy: policy(true),
      spaceContext: { organizationId: 'o', departmentId: 'dept', projectSpaceId: 'mine', role: 'member' },
    })
    expect(out.map((chunk) => chunk.documentId)).toEqual(['d-dep', 'd-org'])
  })

  it('uses the explicit binding-derived allow list when supplied', async () => {
    const provider = providerWith([
      { documentId: 'd1', title: 't', snippet: 's', score: 1, spaceId: 'bound' },
      { documentId: 'd2', title: 't', snippet: 's', score: 1, spaceId: 'mine' },
    ])
    const out = await retrieveForSpace({
      query: 'q',
      limit: 5,
      provider,
      policy: policy(true),
      spaceContext: { organizationId: 'o', projectSpaceId: 'mine', role: 'member' },
      allowedSpaceIds: ['bound'],
    })
    expect(out.map((chunk) => chunk.documentId)).toEqual(['d1'])
  })

  it('keeps chunks without a space marker (binding lookup assumption) and degrades on provider errors', async () => {
    const annotated = providerWith([
      { documentId: 'd1', title: 't', snippet: 's', score: 1 },
    ])
    const kept = await retrieveForSpace({
      query: 'q',
      limit: 5,
      provider: annotated,
      policy: policy(true),
      spaceContext: { organizationId: 'o', role: 'member' },
    })
    expect(kept.map((chunk) => chunk.documentId)).toEqual(['d1'])

    const failing = providerWith([], retrieveMock(async () => {
      throw new Error('provider exploded')
    }))
    await expect(
      retrieveForSpace({
        query: 'q',
        limit: 5,
        provider: failing,
        policy: policy(true),
        spaceContext: { organizationId: 'o', role: 'member' },
      }),
    ).resolves.toEqual([])
  })
})
