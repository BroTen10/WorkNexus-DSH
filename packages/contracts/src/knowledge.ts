/**
 * KnowledgeProvider —— 契约⑨（P3 扩展）：知识库检索、健康检查、配置校验、权限过滤。
 *
 * 对齐需求书 §4.3.2 P3-F01 的四项能力与 §4.3.3 第一版范围：
 *  - 只定义**可替换的能力面**，不写任何具体 Provider（RAGFlow / AnythingLLM / 自研）的实现细节；
 *  - 「权限过滤」由两层共同承担：调用方先做 `PermissionPolicy.can(actor, 'kb.retrieve', ...)` 判定，
 *    Provider 侧必须显式接收 `SpaceContext`，并丢弃不属于该空间的命中（需求书 §4.3.4 第 3 条）；
 *  - 命中不返回跨空间内容时用 `spaceId` 标注归属，缺失归属由调用方按绑定关系反查后过滤。
 *
 * 边界（总览 §2.1 第 16 条）：检索只落在企业插件内，不侵入官方会话主链路；检索失败只降级提示。
 */

import type { SpaceContext } from './space.js'

/**
 * 连接状态四态（需求书 P3-F07）：
 *  - `healthy`：可达且鉴权通过；
 *  - `unreachable`：网络不可达 / 超时 / 连接被拒；
 *  - `auth_failed`：可达但鉴权失败（401/403 或 Token 失效）；
 *  - `sync_failed`：服务可达且鉴权通过，但知识库同步或索引异常。
 */
export type KnowledgeHealth = 'healthy' | 'unreachable' | 'auth_failed' | 'sync_failed'

/** 四态的运行时枚举，供 Provider 与 UI 直接引用，避免各处重复清单。 */
export const KNOWLEDGE_HEALTH_STATES: readonly KnowledgeHealth[] = Object.freeze([
  'healthy',
  'unreachable',
  'auth_failed',
  'sync_failed',
])

/** 单条命中块：必须可追溯到文档、片段或链接（需求书 P3-F06）。 */
export type KnowledgeChunk = {
  documentId: string
  title: string
  snippet: string
  url?: string
  score: number
  /** 命中归属的企业侧空间；Provider 不返回时由调用方按绑定关系反查。 */
  spaceId?: string
}

/** 健康检查结果：`detail` 只放可公开的诊断摘要，不得含凭据。 */
export type KnowledgeHealthReport = {
  state: KnowledgeHealth
  detail?: string
}

/** 配置校验结果：失败必须给出字段级原因（`baseUrl: 必填` 这类）。 */
export type KnowledgeConfigValidation = {
  ok: boolean
  problems: string[]
}

/** 检索入参：空间上下文必填，不允许「无上下文检索」。 */
export type KnowledgeRetrieveInput = {
  query: string
  spaceContext: SpaceContext
  limit: number
}

/** 可替换的知识库 Provider 能力面（P3-F01）。 */
export interface KnowledgeProvider {
  readonly id: string
  healthCheck(): Promise<KnowledgeHealthReport>
  validateConfig(config: unknown): KnowledgeConfigValidation
  retrieve(input: KnowledgeRetrieveInput): Promise<KnowledgeChunk[]>
}
