/**
 * T-090：ACP 企业适配层。
 */

import { describe, expect, it, vi } from 'vitest'

import {
  UNSUPPORTED_ACP_CAPABILITIES,
  createAcpTransport,
  type AcpAuditEntry,
  type AcpUsageEntry,
} from '../src/acp-transport.js'
import { createFakeAcpClient } from './fake-acp-client.js'
import { runTransportContract } from './transport.contract.js'

const context = {
  userId: 'u1',
  organizationId: 'o1',
  spaceId: 's1',
  pluginId: 'acp',
}

describe('AcpTransport', () => {
  runTransportContract(() => {
    const client = createFakeAcpClient({
      script: [
        { sessionId: 'x', kind: 'message', text: 'hello' },
        { sessionId: 'x', kind: 'tool', tool: 'fs.read' },
        { sessionId: 'x', kind: 'usage', usage: { totalTokens: 12, model: 'deepseek-v4-pro' } },
      ],
    })
    const transport = createAcpTransport({ client, context, policy: { canRunTool: () => true } })
    return { transport }
  })
})

describe('acp enterprise adaptation', () => {
  it('reports start / finish and per-session usage through enterprise hooks', async () => {
    const audit: AcpAuditEntry[] = []
    const usage: AcpUsageEntry[] = []
    const transport = createAcpTransport({
      client: createFakeAcpClient({
        script: [
          { sessionId: 'x', kind: 'message', text: 'hello' },
          { sessionId: 'x', kind: 'usage', usage: { totalTokens: 7, promptTokens: 3, completionTokens: 4 } },
        ],
      }),
      context,
      policy: { canRunTool: () => true },
      audit: (entry) => {
        audit.push(entry)
      },
      usage: (entry) => {
        usage.push(entry)
      },
    })

    const session = await transport.createSession({ cwd: '/w', model: 'deepseek-v4-pro' })
    const events = []
    for await (const event of transport.sendMessage({ sessionId: session.sessionId, text: 'ping' })) {
      events.push(event)
    }
    expect(events.map((event) => event.type)).toEqual(['message', 'usage'])
    expect(audit.map((entry) => entry.action)).toEqual(['acp.job.start', 'acp.job.finish'])
    expect(usage).toHaveLength(1)
    expect(usage[0]).toMatchObject({ pluginId: 'acp', spaceId: 's1', sessionId: session.sessionId })
  })

  it('maps a process/protocol failure to a task failure instead of losing it', async () => {
    const audit: AcpAuditEntry[] = []
    const transport = createAcpTransport({
      client: createFakeAcpClient({ failWith: new Error('acp process exited with code 1') }),
      context,
      audit: (entry) => {
        audit.push(entry)
      },
    })
    const session = await transport.createSession({ cwd: '/w' })
    const events = []
    for await (const event of transport.sendMessage({ sessionId: session.sessionId, text: 'boom' })) {
      events.push(event)
    }
    expect(events).toEqual([
      { type: 'error', code: 'acp-runtime-error', detail: 'acp process exited with code 1' },
    ])
    expect(audit.map((entry) => entry.action)).toEqual(['acp.job.start', 'acp.job.failed'])
  })

  it('denies tools that the enterprise policy rejects', async () => {
    const audit: AcpAuditEntry[] = []
    const transport = createAcpTransport({
      client: createFakeAcpClient({ script: [{ sessionId: 'x', kind: 'tool', tool: 'fs.write' }] }),
      context,
      policy: { canRunTool: ({ tool }) => tool !== 'fs.write' },
      audit: (entry) => {
        audit.push(entry)
      },
    })
    const session = await transport.createSession({ cwd: '/w' })
    const events = []
    for await (const event of transport.sendMessage({ sessionId: session.sessionId, text: 'write' })) {
      events.push(event)
    }
    expect(events).toEqual([{ type: 'error', code: 'acp-policy-denied', detail: 'policy denied tool fs.write' }])
    expect(audit.at(-1)?.action).toBe('acp.job.failed')
  })

  it('explicitly refuses the capabilities ACP does not offer', () => {
    const transport = createAcpTransport({ client: createFakeAcpClient(), context })
    for (const capability of UNSUPPORTED_ACP_CAPABILITIES) {
      const result = transport.requestUnsupportedCapability(capability)
      expect(result).toMatchObject({ ok: false, unsupported: true })
      expect(result.detail).toContain('acp-unsupported')
    }
    expect(transport.describe()).toMatchObject({
      serverCommand: 'pnpm dsh --profile acp',
      officialClient: '@deepseek-ai/dsh-subagent-acp',
    })
  })

  it('never blocks the task chain when enterprise audit throws', async () => {
    const transport = createAcpTransport({
      client: createFakeAcpClient({ script: [{ sessionId: 'x', kind: 'message', text: 'ok' }] }),
      context,
      audit: vi.fn(() => {
        throw new Error('audit sink down')
      }),
    })
    const session = await transport.createSession({ cwd: '/w' })
    const events = []
    for await (const event of transport.sendMessage({ sessionId: session.sessionId, text: 'ping' })) {
      events.push(event)
    }
    expect(events).toEqual([{ type: 'message', text: 'ok' }])
  })
})
