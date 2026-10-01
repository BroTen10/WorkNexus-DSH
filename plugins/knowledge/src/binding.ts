/**
 * 空间绑定与会话继承（T-063，需求书 P3-F03 / P3-F04）。
 *
 * 规则：
 *  - 绑定只到**部门空间或项目空间**，不存在会话级绑定，也不把组织本身当作绑定范围（P3-F03）；
 *  - 会话可用知识库由**会话所在空间**决定：项目空间绑定 + 所属部门绑定（部门级知识库在该部门
 *    的所有项目空间生效）；
 *  - 一个空间多个知识库 → 全部生效，按 `weight` 降序、`bindingId` 升序排序（裁决，见交付说明）；
 *  - 控制面不可达时降级为空列表，不阻断会话（需求书 §5.4 第 3 条）。
 */

import type { SpaceContext } from '@worknexus/contracts'

/** 控制面返回的绑定记录；`spaceId` 为通用字段（等价于项目空间范围）。 */
export type KnowledgeBindingRecord = {
  id: string
  providerId: string
  enabled: boolean
  weight?: number
  spaceId?: string
  departmentId?: string
  projectSpaceId?: string
  organizationId?: string
}

export type KnowledgeBindingsApi = {
  listBindings(input: { organizationId: string }): Promise<KnowledgeBindingRecord[]>
}

export type ResolvedKnowledgeBinding = {
  bindingId: string
  providerId: string
  scopeKind: 'project' | 'department'
  scopeId: string
  weight: number
}

function scopeOf(record: KnowledgeBindingRecord): { kind: 'project' | 'department'; id: string } | null {
  if (typeof record.projectSpaceId === 'string' && record.projectSpaceId.length > 0) {
    return { kind: 'project', id: record.projectSpaceId }
  }
  if (typeof record.spaceId === 'string' && record.spaceId.length > 0) {
    return { kind: 'project', id: record.spaceId }
  }
  if (typeof record.departmentId === 'string' && record.departmentId.length > 0) {
    return { kind: 'department', id: record.departmentId }
  }
  return null
}

/**
 * 解析会话可用的知识库绑定。
 *
 * 返回值按「weight 降序 → bindingId 升序」稳定排序；`scopeId` 可直接作为
 * `retrieveForSpace({ allowedSpaceIds })` 的允许集（T-062）。
 */
export async function resolveKnowledgeForSpace(
  spaceContext: SpaceContext,
  api: KnowledgeBindingsApi,
): Promise<ResolvedKnowledgeBinding[]> {
  const sessionScopes = new Set(
    [spaceContext.projectSpaceId, spaceContext.departmentId].filter(
      (value): value is string => typeof value === 'string' && value.length > 0,
    ),
  )
  if (sessionScopes.size === 0) return []

  let records: KnowledgeBindingRecord[]
  try {
    records = await api.listBindings({ organizationId: spaceContext.organizationId })
  } catch {
    return []
  }
  if (!Array.isArray(records)) return []

  return records
    .filter((record) => record.enabled)
    .map((record) => {
      const scope = scopeOf(record)
      if (scope === null || !sessionScopes.has(scope.id)) return null
      return {
        bindingId: record.id,
        providerId: record.providerId,
        scopeKind: scope.kind,
        scopeId: scope.id,
        weight: typeof record.weight === 'number' && Number.isFinite(record.weight) ? record.weight : 0,
      } satisfies ResolvedKnowledgeBinding
    })
    .filter((item): item is ResolvedKnowledgeBinding => item !== null)
    .sort((left, right) => right.weight - left.weight || left.bindingId.localeCompare(right.bindingId))
}
