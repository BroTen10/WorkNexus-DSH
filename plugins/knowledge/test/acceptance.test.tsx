/**
 * T-066：P3 验收集成场景（§4.3.4 六条的可执行证据）。
 *
 * 这些用例把「Provider + 绑定 + 检索过滤 + 引用」串成一条链路，
 * 对应验收：管理员配置并绑定 → 空间成员可用 → 非成员取不到 → 引用可追溯 →
 * Provider 不可用与会话不阻断。
 */

import { describe, expect, it, vi } from 'vitest'
import { renderToString } from 'react-dom/server'
import type { Action, PermissionPolicy, ResourceRef, SpaceContext } from '@worknexus/contracts'

import { Citations } from '../src/citations.js'
import { resolveKnowledgeForSpace } from '../src/binding.js'
import { retrieveForSpace } from '../src/retrieve.js'
import { createHttpRagProvider, type HttpRagFetchLike } from '../src/providers/http-rag.js'

const MATRIX: Record<string, string[]> = {
  owner: ['kb.retrieve', 'kb.bind'],
  admin: ['kb.retrieve', 'kb.bind'],
  member: ['kb.retrieve', 'kb.bind'],
  viewer: ['kb.retrieve'],
}

function matrixPolicy(): PermissionPolicy {
  return {
    can: (actor: SpaceContext, action: Action, _resource: ResourceRef) =>
      (MATRIX[actor.role] ?? []).includes(action),
  }
}

const member: SpaceContext = { organizationId: 'o', departmentId: 'd1', projectSpaceId: 's1', role: 'member' }
const outsider: SpaceContext = { organizationId: 'o', role: 'viewer' }

const payload = {
  chunks: [
    { document_id: 'doc-1', document_name: '合同模板', content: '条款 A', link: 'https://rag/doc-1', similarity: 0.93, space_id: 's1' },
  ],
}

function provider(fetchImpl: HttpRagFetchLike) {
  return createHttpRagProvider({ baseUrl: 'http://rag.local', token: 'sk-acceptance', fetchImpl })
}

const bindings = {
  listBindings: async () => [
    { id: 'b1', providerId: 'http-rag', enabled: true, projectSpaceId: 's1', weight: 2 },
    { id: 'b2', providerId: 'http-rag', enabled: true, departmentId: 'd1', weight: 1 },
    { id: 'b3', providerId: 'http-rag', enabled: true, projectSpaceId: 's-other', weight: 9 },
  ],
}

const okFetch = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }))

describe('P3 acceptance chain', () => {
  it('管理员绑定后：成员按空间继承拿到绑定，检索命中并可展示引用', async () => {
    const resolved = await resolveKnowledgeForSpace(member, bindings)
    expect(resolved.map((item) => item.bindingId)).toEqual(['b1', 'b2'])

    const chunks = await retrieveForSpace({
      query: '合同模板',
      limit: 5,
      provider: provider(okFetch),
      policy: matrixPolicy(),
      spaceContext: member,
      allowedSpaceIds: resolved.map((item) => item.scopeId),
    })
    expect(chunks.map((chunk) => chunk.documentId)).toEqual(['doc-1'])

    const html = renderToString(<Citations chunks={chunks} />)
    expect(html).toContain('合同模板')
    expect(html).toContain('条款 A')
    expect(html).toContain('https://rag/doc-1')
  })

  it('非空间成员检索不到内容，且不会调用 Provider', async () => {
    const outsiderFetch = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }))
    const chunks = await retrieveForSpace({
      query: '合同模板',
      limit: 5,
      provider: provider(outsiderFetch),
      policy: matrixPolicy(),
      spaceContext: outsider,
      allowedSpaceIds: [],
    })
    expect(chunks).toEqual([])

    const blockedFetch = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }))
    const noPermission: PermissionPolicy = { can: () => false }
    const blocked = await retrieveForSpace({
      query: '合同模板',
      limit: 5,
      provider: provider(blockedFetch),
      policy: noPermission,
      spaceContext: member,
    })
    expect(blocked).toEqual([])
    expect(blockedFetch).not.toHaveBeenCalled()
  })

  it('Provider 不可用时降级：状态可区分、检索为空、会话链路不被打断', async () => {
    const down = provider(async () => {
      throw new Error('ECONNREFUSED')
    })
    await expect(down.healthCheck()).resolves.toMatchObject({ state: 'unreachable' })

    const chunks = await retrieveForSpace({
      query: '合同模板',
      limit: 5,
      provider: down,
      policy: matrixPolicy(),
      spaceContext: member,
      allowedSpaceIds: ['s1'],
    })
    expect(chunks).toEqual([])
  })
})
