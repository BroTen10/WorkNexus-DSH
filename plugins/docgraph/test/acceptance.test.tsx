/**
 * T-076：P4 验收集成场景（§4.4.4 的可执行证据）。
 *
 * 链路：健康检查 → 提交任务 → 状态流转 → 结果渲染 → 会话引用；
 * 以及「DocGraph 中断」时的降级行为（不阻塞、不抛未捕获异常）。
 */

import { describe, expect, it, vi } from 'vitest'
import { renderToString } from 'react-dom/server'

import { createDocGraphClient, DocGraphHttpError, type DocGraphFetchLike } from '../src/client.js'
import { collectStatuses } from '../src/status-poller.js'
import { JobResult } from '../src/pages/JobResult.js'
import { buildResultReference, decideReference } from '../src/agent-bridge.js'
import { DOCGRAPH_PAGES } from '../src/index.js'

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status })
}

describe('P4 acceptance chain', () => {
  it('健康 → 提交 → 状态 → 结果 → 引用 全链路可用', async () => {
    const fetchImpl = vi.fn<DocGraphFetchLike>(async (url) => {
      if (url.endsWith('/api/health')) return response({ status: 'ok', version: '1.0.0' })
      if (url.endsWith('/api/reviews/start')) return response({ id: 'task-1', status: 'pending' })
      if (url.endsWith('/api/reviews/task-1')) return response({ id: 'task-1', status: 'completed', progress: 100 })
      if (url.endsWith('/api/reviews/task-1/by-rule')) {
        return response({
          task_id: 'task-1',
          results: [{ rule: 'R1', message: '缺少签章', result: 'fail', severity: 'high', source: 'graph' }],
          sourceUrl: 'https://docgraph/docs/1',
        })
      }
      return new Response('not found', { status: 404 })
    })

    const client = createDocGraphClient({ baseUrl: 'https://docgraph', token: 'sk-acceptance', fetchImpl })
    await expect(client.health()).resolves.toMatchObject({ ok: true })
    const { jobId } = await client.submit({ contractId: 'c1' })
    expect(jobId).toBe('task-1')

    const states = await collectStatuses(client, jobId, { intervalMs: 1, maxPolls: 3, sleep: async () => {} })
    expect(states).toEqual(['succeeded'])

    const result = await client.result(jobId)
    const html = renderToString(<JobResult result={result} />)
    expect(html).toContain('缺少签章')
    expect(html).toContain('https://docgraph/docs/1')

    const reference = buildResultReference({
      jobId,
      spaceId: 's1',
      summary: '1 项高风险',
      sourceUrl: 'https://docgraph/docs/1',
      findingCount: 1,
    })
    expect(decideReference(reference, { organizationId: 'o', projectSpaceId: 's1', role: 'member' })).toMatchObject({ ok: true })
    expect(decideReference(reference, { organizationId: 'o', projectSpaceId: 's9', role: 'member' })).toEqual({
      ok: false,
      reason: 'denied',
    })
  })

  it('DocGraph 中断时降级：健康不可用、类型化错误、轮询不崩', async () => {
    const down = createDocGraphClient({
      baseUrl: 'https://docgraph',
      fetchImpl: vi.fn<DocGraphFetchLike>(async () => {
        throw new Error('ECONNREFUSED')
      }),
    })
    await expect(down.health()).resolves.toMatchObject({ ok: false })

    const offline = createDocGraphClient({
      baseUrl: 'https://docgraph',
      fetchImpl: vi.fn<DocGraphFetchLike>(async () => new Response('boom', { status: 503 })),
    })
    await expect(offline.status('task-1')).rejects.toBeInstanceOf(DocGraphHttpError)

    const states = await collectStatuses(offline, 'task-1', { intervalMs: 1, maxPolls: 2, sleep: async () => {} })
    expect(states).toEqual(['unknown', 'unknown'])
  })

  it('插件被禁用不影响其他能力：页面声明纯数据、模块无副作用', () => {
    expect(Object.isFrozen(DOCGRAPH_PAGES)).toBe(true)
    expect(DOCGRAPH_PAGES.map((page) => page.uiSlot)).toEqual([
      'worknexus.docgraph.connection',
      'worknexus.docgraph.submit',
      'worknexus.docgraph.jobs',
    ])
    // 引用与结果渲染都是纯函数：禁用插件后其他插件不依赖这里的任何全局状态
    const reference = buildResultReference({ jobId: 'j1', spaceId: 's1', summary: 'x' })
    expect(reference.type).toBe('docgraph.result')
  })
})
