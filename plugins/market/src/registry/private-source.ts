/**
 * 企业私有插件源（T-101，需求书 P6B-F01）。
 *
 * 行为约定：
 *  - 配置：地址 / 凭据 / 超时 / 回退源；凭据只接受官方凭据服务已解析的事实或一次性 `resolveToken()`；
 *  - **不可达时降级**为 `installed-only`（仅展示已安装插件），并且**不阻塞客户端启动**
 *    （模块零副作用：不在顶层发起请求，失败只在 `list()` 内收敛为降级结果）；
 *  - 与官方管理器注册表语义对齐：私有源只问自己，不回退到公共源（T-100 取证结论）。
 */

export const PRIVATE_SOURCE_DEFAULT_TIMEOUT_MS = 4000

export type PrivateSourceFetchLike = (url: string, init?: { headers?: Record<string, string>; signal?: AbortSignal }) => Promise<Response>

export type PrivateSourceConfig = {
  baseUrl: string
  token?: string
  resolveToken?: () => Promise<string | undefined>
  timeoutMs?: number
  fetchImpl?: PrivateSourceFetchLike
}

export type PrivateSourcePlugin = {
  id: string
  version: string
  description?: string
  source: 'private-registry'
}

export type PrivateSourceListing = {
  mode: 'registry' | 'installed-only'
  plugins: PrivateSourcePlugin[]
  detail?: string
}

export type PrivateSource = {
  list(installed?: readonly PrivateSourcePlugin[]): Promise<PrivateSourceListing>
  describe(): {
    baseUrl: string
    timeoutMs: number
    hasCredential: boolean
    fallbackToPublic: false
  }
}

const MAX_DETAIL = 200

export function sanitizeDetail(message: string, secrets: readonly string[] = []): string {
  let text = message
  for (const secret of secrets) {
    if (secret && secret.length >= 4) text = text.split(secret).join('***')
  }
  text = text.replace(/(Bearer)\s+[A-Za-z0-9._~+/-]{4,}/gi, '$1 ***')
  return text.slice(0, MAX_DETAIL)
}

function normalizePlugin(raw: unknown): PrivateSourcePlugin | null {
  if (typeof raw !== 'object' || raw === null) return null
  const item = raw as Record<string, unknown>
  const id = item.id ?? item.name ?? item.pluginId
  const version = item.version
  if (typeof id !== 'string' || typeof version !== 'string') return null
  return typeof item.description === 'string'
    ? { id, version, description: item.description, source: 'private-registry' }
    : { id, version, source: 'private-registry' }
}

/**
 * 创建私有源客户端。**创建本身不发请求**（启动路径安全）；所有网络行为只在 `list()` 内发生。
 */
export function createPrivateSource(config: PrivateSourceConfig): PrivateSource {
  const baseUrl = (config.baseUrl ?? '').replace(/\/+$/, '')
  const timeoutMs = config.timeoutMs ?? PRIVATE_SOURCE_DEFAULT_TIMEOUT_MS
  const fetchImpl: PrivateSourceFetchLike =
    config.fetchImpl ?? ((url, init) => fetch(url, init as RequestInit))

  function currentToken(): string | null {
    return typeof config.token === 'string' && config.token.length > 0 ? config.token : null
  }

  return {
    describe() {
      return {
        baseUrl,
        timeoutMs,
        hasCredential: currentToken() !== null || typeof config.resolveToken === 'function',
        fallbackToPublic: false,
      }
    },
    async list(installed = []): Promise<PrivateSourceListing> {
      const installedOnly: PrivateSourceListing = { mode: 'installed-only', plugins: [...installed] }
      if (baseUrl.length === 0) {
        return { ...installedOnly, detail: 'private-registry: 未配置私有源地址' }
      }
      let token = currentToken()
      if (token === null && typeof config.resolveToken === 'function') {
        try {
          token = (await config.resolveToken()) ?? null
        } catch (error) {
          return {
            ...installedOnly,
            detail: sanitizeDetail(`private-registry: 凭据解析失败（${error instanceof Error ? error.message : String(error)}）`),
          }
        }
      }
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), timeoutMs)
      try {
        const headers: Record<string, string> = { Accept: 'application/json' }
        if (token !== null) headers.Authorization = `Bearer ${token}`
        const response = await fetchImpl(`${baseUrl}/-/v1/search?text=worknexus`, {
          headers,
          signal: controller.signal,
        })
        if (!response.ok) {
          return { ...installedOnly, detail: `private-registry: HTTP ${response.status}` }
        }
        const payload = (await response.json()) as { plugins?: unknown[]; objects?: unknown[] }
        const raw = payload.plugins ?? payload.objects ?? []
        const plugins = raw.map(normalizePlugin).filter((item): item is PrivateSourcePlugin => item !== null)
        return { mode: 'registry', plugins }
      } catch (error) {
        return {
          ...installedOnly,
          detail: sanitizeDetail(
            error instanceof Error ? error.message : String(error),
            [token ?? ''],
          ),
        }
      } finally {
        clearTimeout(timer)
      }
    },
  }
}
