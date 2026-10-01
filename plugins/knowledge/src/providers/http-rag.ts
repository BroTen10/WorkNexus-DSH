/**
 * 通用 `http-rag` KnowledgeProvider（T-061，需求书 P3-F02 / P3-F07）。
 *
 * 设计边界：
 *  - **不硬编码外部服务地址与密钥**：地址、Token、超时与默认参数全部来自配置；
 *  - **不引第二套凭据存储**：Token 只接受「已由官方凭据服务解析出来的事实」或一次性的
 *    `resolveToken()` 端口，本模块不落盘、不缓存、不写日志（T-025 的凭据边界同源）；
 *  - 四态健康检查可区分：`healthy` / `unreachable` / `auth_failed` / `sync_failed`；
 *  - 任何失败都**降级**：`healthCheck` 返回状态而不抛错，`retrieve` 返回空数组（总览 §2.1 第 16 条）。
 */

import type {
  KnowledgeChunk,
  KnowledgeConfigValidation,
  KnowledgeHealth,
  KnowledgeHealthReport,
  KnowledgeProvider,
} from '@worknexus/contracts'

export const HTTP_RAG_DEFAULT_SEARCH_PATH = '/api/v1/retrieval'
export const HTTP_RAG_DEFAULT_HEALTH_PATH = '/api/v1/health'
export const HTTP_RAG_DEFAULT_TIMEOUT_MS = 5000
export const HTTP_RAG_DEFAULT_LIMIT = 10

export type HttpRagFetchInit = {
  method?: string
  headers?: Record<string, string>
  body?: string
  signal?: AbortSignal
}

export type HttpRagFetchLike = (url: string, init?: HttpRagFetchInit) => Promise<Response>

/**
 * 连接配置。
 *
 * `token` 与 `resolveToken` 二选一：前者是官方凭据服务已解析出的事实（会话内使用，不落盘），
 * 后者是每请求读取一次的端口，便于 UI 触发重新解析。
 */
export type HttpRagConfig = {
  baseUrl: string
  token?: string
  resolveToken?: () => Promise<string | undefined>
  searchPath?: string
  healthPath?: string
  timeoutMs?: number
  defaultLimit?: number
  fetchImpl?: HttpRagFetchLike
}

export type HttpRagConnectionDescriptor = {
  baseUrl: string
  searchPath: string
  healthPath: string
  timeoutMs: number
  defaultLimit: number
  hasCredential: boolean
}

const MAX_DETAIL_LENGTH = 200

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

function withDefaults(config: HttpRagConfig): Required<Omit<HttpRagConfig, 'token' | 'resolveToken' | 'fetchImpl'>> {
  return {
    baseUrl: config.baseUrl ?? '',
    searchPath: config.searchPath ?? HTTP_RAG_DEFAULT_SEARCH_PATH,
    healthPath: config.healthPath ?? HTTP_RAG_DEFAULT_HEALTH_PATH,
    timeoutMs: config.timeoutMs ?? HTTP_RAG_DEFAULT_TIMEOUT_MS,
    defaultLimit: config.defaultLimit ?? HTTP_RAG_DEFAULT_LIMIT,
  }
}

/** 配置校验（P3-F01 第 3 项）：失败必须给出字段级原因，且不得回显凭据值。 */
export function validateHttpRagConfig(config: unknown): KnowledgeConfigValidation {
  const problems: string[] = []
  if (typeof config !== 'object' || config === null) {
    return { ok: false, problems: ['config: 必须是对象'] }
  }
  const raw = config as Record<string, unknown>
  const baseUrl = typeof raw.baseUrl === 'string' ? raw.baseUrl.trim() : ''
  if (!baseUrl) problems.push('baseUrl: 必填')
  else if (!isHttpUrl(baseUrl)) problems.push('baseUrl: 必须是 http/https 绝对地址')

  const hasCredential =
    (typeof raw.token === 'string' && raw.token.trim().length > 0) || typeof raw.resolveToken === 'function'
  if (!hasCredential) problems.push('token: 必填（由官方凭据服务解析，不接受明文落盘）')

  if (raw.timeoutMs !== undefined) {
    const timeoutMs = raw.timeoutMs
    if (typeof timeoutMs !== 'number' || !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      problems.push('timeoutMs: 必须是正数（毫秒）')
    }
  }
  if (raw.defaultLimit !== undefined) {
    const limit = raw.defaultLimit
    if (typeof limit !== 'number' || !Number.isInteger(limit) || limit <= 0 || limit > 50) {
      problems.push('defaultLimit: 必须是 1~50 的整数')
    }
  }
  return { ok: problems.length === 0, problems }
}

/** 供连接页面使用的只读描述：不含任何凭据值。 */
export function describeConnection(config: HttpRagConfig): HttpRagConnectionDescriptor {
  const resolved = withDefaults(config)
  return {
    baseUrl: resolved.baseUrl,
    searchPath: resolved.searchPath,
    healthPath: resolved.healthPath,
    timeoutMs: resolved.timeoutMs,
    defaultLimit: resolved.defaultLimit,
    hasCredential:
      (typeof config.token === 'string' && config.token.trim().length > 0)
      || typeof config.resolveToken === 'function',
  }
}

function joinUrl(baseUrl: string, path: string): string {
  const trimmedBase = baseUrl.replace(/\/+$/, '')
  const trimmedPath = path.startsWith('/') ? path : `/${path}`
  return `${trimmedBase}${trimmedPath}`
}

/** 脱敏：任何进入 detail / 异常的字符串都必须先过这里，凭据一律替换为 `***`。 */
export function sanitizeDetail(message: string, secrets: readonly string[] = []): string {
  let text = message
  for (const secret of secrets) {
    if (secret && secret.length >= 4) {
      text = text.split(secret).join('***')
    }
  }
  text = text.replace(/(Bearer)\s+[A-Za-z0-9._~+/-]{4,}/gi, '$1 ***')
  text = text.replace(/(sk-[A-Za-z0-9._-]{4,})/g, '***')
  return text.slice(0, MAX_DETAIL_LENGTH)
}

function classifyStatus(status: number): KnowledgeHealth {
  if (status === 401 || status === 403) return 'auth_failed'
  return 'sync_failed'
}

function mapChunk(raw: unknown): KnowledgeChunk | null {
  if (typeof raw !== 'object' || raw === null) return null
  const item = raw as Record<string, unknown>
  const documentId = item.documentId ?? item.document_id ?? item.id
  const title = item.title ?? item.document_name ?? item.name
  const snippet = item.snippet ?? item.content ?? item.text
  if (typeof documentId !== 'string' || typeof title !== 'string' || typeof snippet !== 'string') {
    return null
  }
  const score = typeof item.score === 'number' ? item.score : typeof item.similarity === 'number' ? item.similarity : 0
  const url = typeof item.url === 'string' ? item.url : typeof item.link === 'string' ? item.link : undefined
  const spaceId = typeof item.spaceId === 'string' ? item.spaceId : typeof item.space_id === 'string' ? item.space_id : undefined
  return url === undefined
    ? spaceId === undefined
      ? { documentId, title, snippet, score }
      : { documentId, title, snippet, score, spaceId }
    : spaceId === undefined
      ? { documentId, title, snippet, url, score }
      : { documentId, title, snippet, url, score, spaceId }
}

function extractChunks(payload: unknown): KnowledgeChunk[] {
  const container = Array.isArray(payload)
    ? payload
    : typeof payload === 'object' && payload !== null
      ? (payload as Record<string, unknown>).chunks
        ?? (payload as Record<string, unknown>).hits
        ?? (payload as Record<string, unknown>).data
      : undefined
  if (!Array.isArray(container)) return []
  return container.map(mapChunk).filter((chunk): chunk is KnowledgeChunk => chunk !== null)
}

/**
 * 创建通用 `http-rag` Provider。返回对象只暴露契约⑨的四个成员，
 * 保证调用方无法绕过契约拿到 Token 或内部配置。
 */
export function createHttpRagProvider(config: HttpRagConfig, id = 'http-rag'): KnowledgeProvider {
  const resolved = withDefaults(config)
  const fetchImpl: HttpRagFetchLike = config.fetchImpl ?? ((url, init) => fetch(url, init as RequestInit))

  async function resolveCredential(): Promise<{ token: string | null; problem?: string }> {
    if (typeof config.token === 'string' && config.token.trim().length > 0) {
      return { token: config.token }
    }
    if (typeof config.resolveToken === 'function') {
      try {
        const token = await config.resolveToken()
        if (typeof token === 'string' && token.length > 0) return { token }
        return { token: null, problem: 'token: 官方凭据服务未返回可用凭据' }
      } catch (error) {
        return {
          token: null,
          problem: sanitizeDetail(`token: 凭据解析失败（${error instanceof Error ? error.message : String(error)}）`),
        }
      }
    }
    return { token: null, problem: 'token: 必填（由官方凭据服务解析）' }
  }

  async function request(url: string, init: HttpRagFetchInit, token: string): Promise<Response> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), resolved.timeoutMs)
    try {
      return await fetchImpl(url, {
        ...init,
        headers: { ...(init.headers ?? {}), Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })
    } finally {
      clearTimeout(timer)
    }
  }

  return {
    id,
    async healthCheck(): Promise<KnowledgeHealthReport> {
      const validation = validateHttpRagConfig({ ...config, ...resolved })
      if (!validation.ok) {
        const state: KnowledgeHealth = validation.problems.some((p) => p.startsWith('baseUrl'))
          ? 'unreachable'
          : 'auth_failed'
        return { state, detail: sanitizeDetail(validation.problems.join('；')) }
      }
      const credential = await resolveCredential()
      if (!credential.token) {
        return { state: 'auth_failed', detail: sanitizeDetail(credential.problem ?? 'token: 不可用') }
      }
      let response: Response
      try {
        response = await request(joinUrl(resolved.baseUrl, resolved.healthPath), { method: 'GET' }, credential.token)
      } catch (error) {
        return {
          state: 'unreachable',
          detail: sanitizeDetail(error instanceof Error ? error.message : String(error), [credential.token]),
        }
      }
      if (response.status === 401 || response.status === 403) {
        return { state: 'auth_failed', detail: `HTTP ${response.status}` }
      }
      if (!response.ok) {
        return { state: classifyStatus(response.status), detail: `HTTP ${response.status}` }
      }
      let payload: unknown = null
      try {
        payload = await response.json()
      } catch {
        return { state: 'sync_failed', detail: '健康检查响应不是合法 JSON' }
      }
      const status = typeof payload === 'object' && payload !== null
        ? (payload as Record<string, unknown>).status
        : undefined
      if (typeof status === 'string' && status.toLowerCase().includes('sync')) {
        const detail = (payload as Record<string, unknown>).detail
        return { state: 'sync_failed', detail: typeof detail === 'string' ? sanitizeDetail(detail) : 'provider 自报同步异常' }
      }
      return { state: 'healthy' }
    },
    validateConfig: (candidate: unknown) => validateHttpRagConfig(candidate),
    async retrieve({ query, spaceContext, limit }): Promise<KnowledgeChunk[]> {
      const validation = validateHttpRagConfig({ ...config, ...resolved })
      if (!validation.ok) return []
      const credential = await resolveCredential()
      if (!credential.token) return []
      const requestedLimit = Number.isInteger(limit) && limit > 0 ? limit : resolved.defaultLimit
      // 只上报**最具体**的空间范围（项目空间 → 部门 → 组织），命中归属由绑定关系反查（T-062/T-063）。
      const scope = spaceContext.projectSpaceId ?? spaceContext.departmentId ?? spaceContext.organizationId
      const spaceIds = typeof scope === 'string' && scope.length > 0 ? [scope] : []
      try {
        const response = await request(
          joinUrl(resolved.baseUrl, resolved.searchPath),
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, topK: requestedLimit, spaceIds }),
          },
          credential.token,
        )
        if (!response.ok) return []
        return extractChunks(await response.json()).slice(0, requestedLimit)
      } catch {
        return []
      }
    },
  }
}
