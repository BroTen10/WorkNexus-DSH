/**
 * DocGraph HTTP 客户端（T-070，需求书 P4-F01 / P4-F02）。
 *
 * 端点与错误码**唯一来源**是 `docs/技术决策-DocGraph-API清单.md`（T-009）：
 *  - 健康检查：`GET {baseUrl}/api/health`；
 *  - 提交任务：`POST {baseUrl}/api/reviews/start`（body `contract_id` / `snapshot_id?`）；
 *  - 任务状态：`GET {baseUrl}/api/reviews/{task_id}`；
 *  - 任务结果：`GET {baseUrl}/api/reviews/{task_id}/by-rule`；
 *  - **远端没有取消端点**：`cancel()` 显式返回「不支持」，不伪装成功（总览 §2.1 第 14 条）；
 *  - **DocGraph 本体没有鉴权层**：`token` 允许留空，是否注入由部署侧网关决定（T-009 R-2）。
 *
 * 凭据边界：Token 只接受官方凭据服务已解析的事实或一次性 `resolveToken()` 端口，不落盘、不入日志。
 */

export const DOCGRAPH_DEFAULT_TIMEOUT_MS = 5000
export const DOCGRAPH_HEALTH_PATH = '/api/health'
export const DOCGRAPH_START_PATH = '/api/reviews/start'
export const DOCGRAPH_REVIEW_PATH = '/api/reviews'

export type DocGraphFetchInit = {
  method?: string
  headers?: Record<string, string>
  body?: string
  signal?: AbortSignal
}

export type DocGraphFetchLike = (url: string, init?: DocGraphFetchInit) => Promise<Response>

export type DocGraphConfig = {
  baseUrl: string
  /** 允许留空：DocGraph 本体无鉴权，Token 取决于部署侧网关（T-009 C-1）。 */
  token?: string
  resolveToken?: () => Promise<string | undefined>
  timeoutMs?: number
  /** 默认参数：如默认 `snapshot_id`（不传则由 DocGraph 使用最新快照）。 */
  defaultSnapshotId?: string
  fetchImpl?: DocGraphFetchLike
}

/** 远端状态直接透传后的类型化视图；未知状态映射为 `unknown`，不猜测（P4-F04）。 */
export type DocGraphJobState = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'unknown'

export type DocGraphJob = {
  jobId: string
  state: DocGraphJobState
  rawStatus: string | null
  progress: number | null
  stage: string | null
  error: string | null
  summary: string | null
}

export type DocGraphSubmitTask = {
  contractId: string
  documentId?: string
  snapshotId?: string
  mode?: 'analysis' | 'review'
}

export type DocGraphCancelResult = {
  ok: boolean
  supported: boolean
  detail: string
}

export type DocGraphClient = {
  id: string
  health(): Promise<{ ok: boolean; detail?: string }>
  submit(task: DocGraphSubmitTask): Promise<{ jobId: string }>
  status(jobId: string): Promise<DocGraphJob>
  result(jobId: string): Promise<unknown>
  cancel(jobId: string): Promise<DocGraphCancelResult>
  describe(): DocGraphConnectionDescriptor
}

export type DocGraphConnectionDescriptor = {
  baseUrl: string
  timeoutMs: number
  hasCredential: boolean
  defaultSnapshotId: string | null
  authNote: 'gateway-dependent'
}

export class DocGraphHttpError extends Error {
  readonly code: string
  readonly status: number

  constructor(status: number, detail = '') {
    const code = `docgraph-http-${status}`
    super(detail ? `${code}: ${detail}` : code)
    this.name = 'DocGraphHttpError'
    this.code = code
    this.status = status
  }
}

const REMOTE_STATUS_MAP: Record<string, DocGraphJobState> = {
  pending: 'queued',
  queued: 'queued',
  running: 'running',
  completed: 'succeeded',
  succeeded: 'succeeded',
  failed: 'failed',
  cancelled: 'cancelled',
  canceled: 'cancelled',
}

const MAX_DETAIL = 200

export function sanitizeDetail(message: string, secrets: readonly string[] = []): string {
  let text = message
  for (const secret of secrets) {
    if (secret && secret.length >= 4) text = text.split(secret).join('***')
  }
  text = text.replace(/(Bearer)\s+[A-Za-z0-9._~+/-]{4,}/gi, '$1 ***')
  text = text.replace(/(sk-[A-Za-z0-9._-]{4,})/g, '***')
  return text.slice(0, MAX_DETAIL)
}

export function mapRemoteStatus(rawStatus: unknown): DocGraphJobState {
  if (typeof rawStatus !== 'string' || rawStatus.length === 0) return 'unknown'
  return REMOTE_STATUS_MAP[rawStatus.toLowerCase()] ?? 'unknown'
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, '')}${path.startsWith('/') ? path : `/${path}`}`
}

/**
 * 创建 DocGraph 客户端。返回对象只暴露能力面，调用方拿不到 Token 或内部配置。
 */
export function createDocGraphClient(config: DocGraphConfig, id = 'docgraph'): DocGraphClient {
  const baseUrl = config.baseUrl ?? ''
  const timeoutMs = config.timeoutMs ?? DOCGRAPH_DEFAULT_TIMEOUT_MS
  const fetchImpl: DocGraphFetchLike = config.fetchImpl ?? ((url, init) => fetch(url, init as RequestInit))

  function resolvedToken(): string | null {
    return typeof config.token === 'string' && config.token.length > 0 ? config.token : null
  }

  async function request(path: string, init: DocGraphFetchInit = {}): Promise<Response> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    const token = resolvedToken()
    const headers: Record<string, string> = { ...(init.headers ?? {}) }
    if (token) headers.Authorization = `Bearer ${token}`
    try {
      return await fetchImpl(joinUrl(baseUrl, path), { ...init, headers, signal: controller.signal })
    } finally {
      clearTimeout(timer)
    }
  }

  async function jsonOrThrow(response: Response, what: string): Promise<Record<string, unknown>> {
    if (!response.ok) {
      let detail = ''
      try {
        detail = sanitizeDetail(await response.text(), [resolvedToken() ?? ''])
      } catch {
        detail = ''
      }
      throw new DocGraphHttpError(response.status, detail || what)
    }
    try {
      const payload = await response.json()
      return typeof payload === 'object' && payload !== null ? (payload as Record<string, unknown>) : {}
    } catch {
      throw new DocGraphHttpError(response.status, `${what}: 响应不是合法 JSON`)
    }
  }

  return {
    id,
    describe(): DocGraphConnectionDescriptor {
      return {
        baseUrl,
        timeoutMs,
        hasCredential: resolvedToken() !== null || typeof config.resolveToken === 'function',
        defaultSnapshotId: typeof config.defaultSnapshotId === 'string' ? config.defaultSnapshotId : null,
        authNote: 'gateway-dependent',
      }
    },
    async health() {
      try {
        const response = await request(DOCGRAPH_HEALTH_PATH)
        if (!response.ok) return { ok: false, detail: sanitizeDetail(`HTTP ${response.status}`) }
        const payload = (await response.json()) as { status?: unknown; version?: unknown }
        const ok = typeof payload.status === 'string' && payload.status.toLowerCase() === 'ok'
        return ok
          ? { ok: true, ...(typeof payload.version === 'string' ? { detail: `version ${payload.version}` } : {}) }
          : { ok: false, detail: sanitizeDetail(`health status=${String(payload.status)}`) }
      } catch (error) {
        return {
          ok: false,
          detail: sanitizeDetail(error instanceof Error ? error.message : String(error), [resolvedToken() ?? '']),
        }
      }
    },
    async submit(task) {
      const snapshotId = task.snapshotId ?? config.defaultSnapshotId
      const body: Record<string, unknown> = { contract_id: task.contractId }
      if (typeof snapshotId === 'string' && snapshotId.length > 0) body.snapshot_id = snapshotId
      const response = await request(DOCGRAPH_START_PATH, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const payload = await jsonOrThrow(response, 'start review task')
      const jobId = payload.id ?? payload.task_id
      if (typeof jobId !== 'string' || jobId.length === 0) {
        throw new DocGraphHttpError(response.status, 'start review task: 响应缺少任务 id')
      }
      return { jobId }
    },
    async status(jobId) {
      const response = await request(`${DOCGRAPH_REVIEW_PATH}/${encodeURIComponent(jobId)}`, { method: 'GET' })
      const payload = await jsonOrThrow(response, 'review status')
      return {
        jobId,
        state: mapRemoteStatus(payload.status),
        rawStatus: typeof payload.status === 'string' ? payload.status : null,
        progress: typeof payload.progress === 'number' ? payload.progress : null,
        stage: typeof payload.stage === 'string' ? payload.stage : null,
        error: typeof payload.error === 'string' ? sanitizeDetail(payload.error) : null,
        summary: typeof payload.summary === 'string' ? payload.summary : null,
      }
    },
    async result(jobId) {
      const response = await request(`${DOCGRAPH_REVIEW_PATH}/${encodeURIComponent(jobId)}/by-rule`, { method: 'GET' })
      return jsonOrThrow(response, 'review result')
    },
    async cancel(jobId) {
      return {
        ok: false,
        supported: false,
        detail: `docgraph-unsupported: 远端无取消端点（T-009 清单），任务 ${jobId} 只能在平台侧标记取消`,
      }
    },
  }
}
