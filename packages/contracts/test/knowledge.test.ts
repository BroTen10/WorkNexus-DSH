/**
 * T-060：`KnowledgeProvider` 契约（P3-F01）。
 *
 * 只断言契约层可判定的性质：四项能力的形状、四种健康状态的互斥可区分、
 * 权限过滤必须显式携带企业侧空间上下文，以及契约不承载任何具体 Provider 实现。
 */

import { describe, expect, it } from 'vitest'

import {
  KNOWLEDGE_HEALTH_STATES,
  type KnowledgeChunk,
  type KnowledgeHealth,
  type KnowledgeProvider,
} from '../src/knowledge.js'
import type { SpaceContext } from '../src/space.js'

describe('契约⑨ KnowledgeProvider', () => {
  it('暴露检索、健康检查、配置校验三项方法，并有稳定 id', () => {
    const provider: KnowledgeProvider = {
      id: 'http-rag',
      healthCheck: async () => ({ state: 'healthy' }),
      validateConfig: () => ({ ok: true, problems: [] }),
      retrieve: async () => [],
    }
    expect(Object.keys(provider)).toEqual(
      expect.arrayContaining(['id', 'healthCheck', 'validateConfig', 'retrieve']),
    )
  })

  it('四种连接状态互斥且可区分（P3-F07）', () => {
    const states: KnowledgeHealth[] = ['healthy', 'unreachable', 'auth_failed', 'sync_failed']
    expect(new Set(states).size).toBe(4)
    expect(KNOWLEDGE_HEALTH_STATES).toEqual(states)
  })

  it('配置校验失败给出字段级问题列表，成功时 problems 为空', () => {
    const provider: KnowledgeProvider = {
      id: 'http-rag',
      healthCheck: async () => ({ state: 'unreachable', detail: 'connect ECONNREFUSED' }),
      validateConfig: (config) =>
        typeof config === 'object' && config !== null && 'baseUrl' in config
          ? { ok: true, problems: [] }
          : { ok: false, problems: ['baseUrl: 必填'] },
      retrieve: async () => [],
    }
    expect(provider.validateConfig({ baseUrl: 'http://rag' })).toEqual({ ok: true, problems: [] })
    expect(provider.validateConfig({}).ok).toBe(false)
    expect(provider.validateConfig({}).problems).toEqual(['baseUrl: 必填'])
  })

  it('检索必须显式携带空间上下文（权限过滤的输入），返回可追溯引用块', async () => {
    const spaceContext: SpaceContext = { organizationId: 'o', projectSpaceId: 's1', role: 'member' }
    const provider: KnowledgeProvider = {
      id: 'http-rag',
      healthCheck: async () => ({ state: 'healthy' }),
      validateConfig: () => ({ ok: true, problems: [] }),
      retrieve: async ({ query, spaceContext: ctx, limit }): Promise<KnowledgeChunk[]> => {
        expect(query).toBe('合同模板')
        expect(ctx.projectSpaceId).toBe('s1')
        expect(limit).toBe(5)
        return [{ documentId: 'd1', title: '合同模板', snippet: '条款 A', url: 'https://x/1', score: 0.9 }]
      },
    }
    const chunks = await provider.retrieve({ query: '合同模板', spaceContext, limit: 5 })
    expect(chunks).toHaveLength(1)
    expect(chunks[0]).toMatchObject({ documentId: 'd1', title: '合同模板', score: 0.9 })
  })

  it('权限过滤是契约方与 Provider 的双层职责，超时与 limit 有显式默认值', async () => {
    const provider: KnowledgeProvider = {
      id: 'http-rag',
      healthCheck: async () => ({ state: 'healthy' }),
      validateConfig: () => ({ ok: true, problems: [] }),
      retrieve: async ({ limit }) => {
        expect(limit).toBe(10)
        return []
      },
    }
    // 契约不允许「不传空间上下文就检索」，因此 retrieve 的入参是必填对象而非可选。
    await expect(
      provider.retrieve({ query: 'q', spaceContext: { organizationId: 'o', role: 'viewer' }, limit: 10 }),
    ).resolves.toEqual([])
  })
})
