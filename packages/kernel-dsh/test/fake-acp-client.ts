/**
 * 测试用官方 ACP 客户端桩：只实现 ACP v1 已被官方公布的能力面，
 * 不含任何 JSON-RPC 编解码（协议层由官方提供）。
 */

import type {
  AcpClientPort,
  AcpNewSessionInput,
  AcpSessionHandle,
  AcpSessionSummary,
  AcpUpdate,
} from '../src/acp-transport.js'

export type FakeAcpClientOptions = {
  script?: readonly AcpUpdate[]
  failWith?: Error
}

export type FakeAcpClient = AcpClientPort & {
  calls: string[]
  sessions: AcpSessionSummary[]
  cancelled: string[]
  closed: string[]
}

export function createFakeAcpClient(options: FakeAcpClientOptions = {}): FakeAcpClient {
  const calls: string[] = []
  const sessions: AcpSessionSummary[] = []
  const cancelled: string[] = []
  const closed: string[] = []

  return {
    calls,
    sessions,
    cancelled,
    closed,
    async newSession(input: AcpNewSessionInput): Promise<AcpSessionHandle> {
      calls.push('session/new')
      const session = { sessionId: `sess-${sessions.length + 1}`, cwd: input.cwd }
      sessions.push(session)
      return session
    },
    async resumeSession(sessionId: string): Promise<AcpSessionHandle> {
      calls.push('session/resume')
      const existing = sessions.find((item) => item.sessionId === sessionId)
      return existing ?? { sessionId, cwd: '/workspace' }
    },
    async listSessions(): Promise<AcpSessionSummary[]> {
      calls.push('session/list')
      return [...sessions]
    },
    async closeSession(sessionId: string): Promise<void> {
      calls.push('session/close')
      closed.push(sessionId)
    },
    async cancel(sessionId: string): Promise<void> {
      calls.push('session/cancel')
      cancelled.push(sessionId)
    },
    async setConfigOption(): Promise<void> {
      calls.push('session/set_config_option')
    },
    prompt(input: { sessionId: string; text: string }): AsyncIterable<AcpUpdate> {
      calls.push('session/prompt')
      const script = options.script ?? []
      const failWith = options.failWith
      async function* run(): AsyncIterable<AcpUpdate> {
        if (failWith !== undefined) throw failWith
        for (const update of script) {
          yield { ...update, sessionId: input.sessionId }
        }
      }
      return run()
    },
  }
}
