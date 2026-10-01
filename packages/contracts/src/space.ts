/**
 * SpaceContext —— 契约②：当前组织、部门、项目空间与角色。
 *
 * 第一版只做四类角色（需求书 §4.2.3、§11.6）：owner / admin / member / viewer，
 * **不做**自由组合的细粒度权限点编辑器。
 */

export type Role = 'owner' | 'admin' | 'member' | 'viewer'

export const ROLES: readonly Role[] = Object.freeze(['owner', 'admin', 'member', 'viewer'])

export type SpaceContext = {
  organizationId: string
  departmentId?: string
  projectSpaceId?: string
  role: Role
}

/** 角色能力序（越大越强），仅用于「至少需要某角色」这类判断，不替代 PermissionPolicy。 */
export const ROLE_RANK: Readonly<Record<Role, number>> = Object.freeze({
  viewer: 0,
  member: 1,
  admin: 2,
  owner: 3,
})

export function hasAtLeastRole(actor: SpaceContext, minimum: Role): boolean {
  return ROLE_RANK[actor.role] >= ROLE_RANK[minimum]
}
