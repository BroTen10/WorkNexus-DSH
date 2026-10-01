/**
 * ACP 企业适配层（T-090，需求书 §4.6.1 功能 1、§6.4 策略 2/4）。
 *
 * 上游事实（`repos/deepseek-harness` @ dsh-v0.2.0-rc.1，本次实测取证）：
 *  - 官方 ACP 服务器由 `pnpm dsh --profile acp` 启动（`@deepseek-ai/dsh-acp`，stdio JSON-RPC）；
 *  - 官方仓库客户端为 `@deepseek-ai/dsh-subagent-acp`，**协议层由官方提供**；
 *  - 协议面：`session/new`、`session/list`、`session/resume`、`session/close`、
 *    `session/set_config_option`、`session/prompt`、`session/cancel`、`session/update`、
 *    `session/request_permission`；
 *  - **不支持**：`session/load`、删除、fork、transcript 回放、附加目录、SSE、终端的客户端文件系统操作。
 *
 * 本模块**只做企业侧适配**：任务与用户/空间/插件关联、权限策略前置、审计与用量上报、异常映射。
 * **不自研 JSON-RPC、不复刻 ACP 协议**（§8、§11）；**不接管交互主链路**（§4.6.1 第 6 条）。
 * 官方不支持的能力在这里显式返回 `unsupported`，不在接口层伪装（§6.4 第 4 条）。
 */

export const ACP_SERVER_COMMAND = 'pnpm dsh --profile acp'
export const ACP_OFFICIAL_CLIENT = '@deepseek-ai/dsh-subagent-acp'

export type AcpSessionHandle = { sessionId: string; cwd: string }

export type AcpSessionSummary = { sessionId: string; cwd: string; updatedAt?: string }

export type AcpUpdate = {
  sessionId: string
  kind: 'message' | 'thought' | 'tool' | 'config' | 'usage'
  text?: string
  tool?: string
  usage?: AcpUsage
  raw?: unknown
}

export type AcpUsage = {
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
  model?: string
  provider?: string
}

export type AcpNewSessionInput = {
  cwd: string
  model?: string
  reasoningEffort?: string
  mcpServers?: readonly unknown[]
}

/** 官方 ACP 客户端能力面（由官方 `dsh-subagent-acp` / 其 SDK 提供）。 */
export interface AcpClientPort {
  newSession(input: AcpNewSessionInput): Promise<AcpSessionHandle>
  resumeSession(sessionId: string): Promise<AcpSessionHandle>
  listSessions(query?: { cwd?: string }): Promise<AcpSessionSummary[]>
  closeSession(sessionId: string): Promise<void>
  cancel(sessionId: string): Promise<void>
  setConfigOption(
    sessionId: string,
    option: { model?: string; reasoningEffort?: string },
  ): Promise<void>
  prompt(input: { sessionId: string; text: string }): AsyncIterable<AcpUpdate>
}

/** §6.4 的 `AgentTransport` 最小接口（v1.2 中只作为 ACP 目标契约）。 */
export type AgentSessionHandle = AcpSessionHandle & {
  /** 企业侧关联（功能 3：任务与用户、空间、插件关联）。 */
  enterprise: AcpEnterpriseContext
}

export type AcpEnterpriseContext = {
  userId: string
  organizationId: string
  spaceId: string | null
  pluginId: string
}

export type AgentEvent =
  | { type: 'message' | 'thought'; text: string }
  | { type: 'tool'; tool: string }
  | { type: 'usage'; usage: AcpUsage }
  | { type: 'error'; code: string; detail: string }

export type AgentTransport = {
  createSession(input: { cwd: string; model?: string; reasoningEffort?: string }): Promise<AgentSessionHandle>
  resumeSession(sessionId: string): Promise<AgentSessionHandle>
  sendMessage(input: { sessionId: string; text: string }): AsyncIterable<AgentEvent>
  cancel(sessionId: string): Promise<void>
  closeSession(sessionId: string): Promise<void>
  listSessions(query?: { cwd?: string }): Promise<AcpSessionSummary[]>
}

export type AcpAuditEntry = {
  action: 'acp.job.start' | 'acp.job.finish' | 'acp.job.failed' | 'acp.job.cancelled' | 'acp.job.closed'
  sessionId: string
  context: AcpEnterpriseContext
  detail?: string
}

export type AcpUsageEntry = AcpEnterpriseContext & {
  sessionId: string
  usage: AcpUsage
}

export type AcpPolicy = {
  /** 权限策略前置：返回 false 时拒绝运行该工具（功能 4）。 */
  canRunTool(input: { tool: string; context: AcpEnterpriseContext }): boolean
}

export type AcpTransportDeps = {
  client: AcpClientPort
  context: AcpEnterpriseContext
  policy?: AcpPolicy
  audit?: (entry: AcpAuditEntry) => Promise<void> | void
  usage?: (entry: AcpUsageEntry) => Promise<void> | void
}

export type UnsupportedAcpCapability =
  | 'session.delete'
  | 'session.fork'
  | 'transcript.replay'
  | 'session.additionalDirectory'

export const UNSUPPORTED_ACP_CAPABILITIES: readonly UnsupportedAcpCapability[] = Object.freeze([
  'session.delete',
  'session.fork',
  'transcript.replay',
  'session.additionalDirectory',
])

export type UnsupportedAcpResult = { ok: false; unsupported: true; detail: string }

export type AcpTransport = AgentTransport & {
  /** 官方未支持的能力统一在此显式拒绝（不发请求、不伪装成功）。 */
  requestUnsupportedCapability(capability: UnsupportedAcpCapability): UnsupportedAcpResult
  describe(): {
    serverCommand: string
    officialClient: string
    supported: readonly string[]
    unsupported: readonly UnsupportedAcpCapability[]
  }
}

const SUPPORTED_SURFACE = Object.freeze([
  'session/new',
  'session/list',
  'session/resume',
  'session/close',
  'session/set_config_option',
  'session/prompt',
  'session/cancel',
  'session/update',
  'session/request_permission',
])

function mapUpdate(update: AcpUpdate): AgentEvent[] {
  switch (update.kind) {
    case 'message':
    case 'thought':
      return [{ type: update.kind, text: update.text ?? '' }]
    case 'tool':
      return [{ type: 'tool', tool: update.tool ?? '<unknown>' }]
    case 'usage':
      return [{ type: 'usage', usage: update.usage ?? {} }]
    case 'config':
    default:
      return []
  }
}

export function createAcpTransport(deps: AcpTransportDeps): AcpTransport {
  const notify = async (entry: AcpAuditEntry): Promise<void> => {
    try {
      await deps.audit?.(entry)
    } catch {
      // 企业审计失败不得阻塞后台任务链路（与 T-032 同口径）
    }
  }

  const handle = (session: AcpSessionHandle): AgentSessionHandle => ({
    sessionId: session.sessionId,
    cwd: session.cwd,
    enterprise: { ...deps.context },
  })

  return {
    describe() {
      return {
        serverCommand: ACP_SERVER_COMMAND,
        officialClient: ACP_OFFICIAL_CLIENT,
        supported: SUPPORTED_SURFACE,
        unsupported: UNSUPPORTED_ACP_CAPABILITIES,
      }
    },
    requestUnsupportedCapability(capability) {
      return {
        ok: false,
        unsupported: true,
        detail: `acp-unsupported: 官方 ACP 未提供 ${capability}（§6.4 第 4 条、§11），不在接口层伪装支持`,
      }
    },
    async createSession(input) {
      const session = await deps.client.newSession({
        cwd: input.cwd,
        ...(input.model === undefined ? {} : { model: input.model }),
        ...(input.reasoningEffort === undefined ? {} : { reasoningEffort: input.reasoningEffort }),
      })
      await notify({ action: 'acp.job.start', sessionId: session.sessionId, context: deps.context })
      return handle(session)
    },
    async resumeSession(sessionId) {
      const session = await deps.client.resumeSession(sessionId)
      await notify({
        action: 'acp.job.start',
        sessionId: session.sessionId,
        context: deps.context,
        detail: 'resume',
      })
      return handle(session)
    },
    sendMessage(input) {
      const context = deps.context
      const client = deps.client
      const policy = deps.policy
      async function* iterate(): AsyncIterable<AgentEvent> {
        let failed: string | null = null
        try {
          for await (const update of client.prompt({ sessionId: input.sessionId, text: input.text })) {
            if (policy !== undefined && update.kind === 'tool') {
              const tool = update.tool ?? '<unknown>'
              if (!policy.canRunTool({ tool, context })) {
                const detail = `policy denied tool ${tool}`
                await notify({ action: 'acp.job.failed', sessionId: input.sessionId, context, detail })
                failed = detail
                yield { type: 'error', code: 'acp-policy-denied', detail }
                break
              }
            }
            if (update.kind === 'usage' && update.usage !== undefined) {
              try {
                await deps.usage?.({ ...context, sessionId: input.sessionId, usage: update.usage })
              } catch {
                // 用量上报失败不阻塞任务链路
              }
            }
            for (const event of mapUpdate(update)) yield event
          }
        } catch (error) {
          // 进程异常退出/协议错误必须上报为任务失败，不得静默丢失
          const detail = error instanceof Error ? error.message : String(error)
          failed = detail
          await notify({ action: 'acp.job.failed', sessionId: input.sessionId, context, detail })
          yield { type: 'error', code: 'acp-runtime-error', detail }
        }
        if (failed === null) {
          await notify({ action: 'acp.job.finish', sessionId: input.sessionId, context })
        }
      }
      return iterate()
    },
    async cancel(sessionId) {
      await deps.client.cancel(sessionId)
      await notify({ action: 'acp.job.cancelled', sessionId, context: deps.context })
    },
    async closeSession(sessionId) {
      await deps.client.closeSession(sessionId)
      await notify({ action: 'acp.job.closed', sessionId, context: deps.context })
    },
    async listSessions(query) {
      return deps.client.listSessions(query ?? {})
    },
  }
}
