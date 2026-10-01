/**
 * 空间内检索与权限过滤（T-062，需求书 P3-F05）。
 *
 * 双重防护：
 *  1. **调用前**：先做 `PermissionPolicy.can(actor, 'kb.retrieve', ...)` 判定；无权限时
 *     **不调用 Provider**（避免「先查后判」导致的外部数据暴露与无谓调用）；
 *  2. **调用后**：按空间归属过滤命中——跨空间结果一律丢弃。
 *
 * 裁决：Provider 不返回空间标识时（第三方 RAG 常见），保留该命中并由 T-063 的绑定关系反查归属；
 * **错判代价**：若第三方系统返回的命中实际属于其他空间且不带标识，则该条会按「绑定反查」口径放行，
 * 需要靠绑定粒度与远端 ACL 兜住（已登记到 T-062/T-063 交付说明）。
 *
 * 检索失败只降级：返回空数组，不抛出未捕获异常（总览 §2.1 第 16 条）。
 */

import type {
  KnowledgeChunk,
  KnowledgeProvider,
  PermissionPolicy,
  SpaceContext,
} from '@worknexus/contracts'

export type RetrieveForSpaceInput = {
  query: string
  limit: number
  provider: KnowledgeProvider
  policy: PermissionPolicy
  spaceContext: SpaceContext
  /** T-063 绑定解析得到的允许空间集合；缺省时按会话空间上下文推导。 */
  allowedSpaceIds?: readonly string[]
}

/** 会话可读的空间范围：项目空间 → 部门 → 组织（存在的都算）。 */
export function sessionSpaceScope(spaceContext: SpaceContext): string[] {
  return [spaceContext.projectSpaceId, spaceContext.departmentId, spaceContext.organizationId].filter(
    (value): value is string => typeof value === 'string' && value.length > 0,
  )
}

export function isChunkVisible(chunk: KnowledgeChunk, allowedSpaceIds: readonly string[]): boolean {
  if (chunk.spaceId === undefined || chunk.spaceId === '') return true
  return allowedSpaceIds.includes(chunk.spaceId)
}

export async function retrieveForSpace(input: RetrieveForSpaceInput): Promise<KnowledgeChunk[]> {
  const { query, limit, provider, policy, spaceContext, allowedSpaceIds } = input

  const resource = { type: 'knowledge-base', id: provider.id }
  if (!policy.can(spaceContext, 'kb.retrieve', resource)) {
    return []
  }

  const requestedLimit = Number.isInteger(limit) && limit > 0 ? limit : 0
  if (requestedLimit === 0) return []

  let chunks: KnowledgeChunk[]
  try {
    chunks = await provider.retrieve({ query, spaceContext, limit: requestedLimit })
  } catch {
    return []
  }
  if (!Array.isArray(chunks)) return []

  const allow = allowedSpaceIds && allowedSpaceIds.length > 0
    ? [...allowedSpaceIds]
    : sessionSpaceScope(spaceContext)
  return chunks.filter((chunk) => chunk !== null && isChunkVisible(chunk, allow)).slice(0, requestedLimit)
}
