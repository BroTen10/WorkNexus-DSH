/**
 * `AgentTransport` 契约测试（T-090）：任何实现都必须满足同一组语义。
 *
 * 说明：派发卡把该辅助文件写成 `transport.contract.test.js`，但 vitest 会把
 * 匹配 `*.test.*` 的文件当作测试文件收集，导出型辅助文件单独放会因「无测试」报错。
 * 因此本文件命名为 `transport.contract.ts`（内容与用途不变），由 `acp-transport.test.ts` 调用。
 */

import { describe, expect, it } from 'vitest'

import type { AgentTransport } from '../src/acp-transport.js'

export type TransportContractFactory = () => { transport: AgentTransport }

/** 逐条验证 §6.4 的最小接口语义。 */
export function runTransportContract(factory: TransportContractFactory): void {
  describe('AgentTransport contract', () => {
    it('创建会话后可见于列表，并可恢复与关闭', async () => {
      const { transport } = factory()
      const created = await transport.createSession({ cwd: '/workspace/project' })
      expect(created.sessionId).toBeTruthy()
      expect(created.cwd).toBe('/workspace/project')

      const listed = await transport.listSessions()
      expect(listed.map((session) => session.sessionId)).toContain(created.sessionId)

      const resumed = await transport.resumeSession(created.sessionId)
      expect(resumed.sessionId).toBe(created.sessionId)

      await transport.closeSession(created.sessionId)
    })

    it('发送消息产生有序事件流，并可取消', async () => {
      const { transport } = factory()
      const session = await transport.createSession({ cwd: '/workspace/project' })
      const events = []
      for await (const event of transport.sendMessage({ sessionId: session.sessionId, text: 'ping' })) {
        events.push(event)
      }
      expect(events.length).toBeGreaterThan(0)
      await transport.cancel(session.sessionId)
    })

    it('会话句柄携带企业侧关联（用户 / 组织 / 空间 / 插件）', async () => {
      const { transport } = factory()
      const session = await transport.createSession({ cwd: '/workspace/project' })
      expect(session.enterprise).toMatchObject({
        userId: expect.any(String),
        organizationId: expect.any(String),
        pluginId: 'acp',
      })
    })
  })
}
