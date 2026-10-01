/**
 * ACP 权限请求的企业侧策略（T-092，需求书 §4.6.1 功能 4）。
 *
 * 与控制面 `services/api/app/routers/jobs.py` 的策略表**同形**：客户端只做 UI 预判，
 * 最终裁决仍在控制面（与 T-044 的客户端预判口径一致）。
 * 未知工具一律默认拒绝（fail closed）。
 */

export type AcpRole = 'owner' | 'admin' | 'member' | 'viewer'

export const POLICY_AUTO_ALLOWED_TOOLS: readonly string[] = Object.freeze(['fs.read', 'search', 'http.get'])
export const POLICY_ADMIN_REQUIRED_TOOLS: readonly string[] = Object.freeze([
  'fs.write',
  'shell.exec',
  'http.post',
  'mcp.call',
])

export type PermissionDecision = {
  decision: 'allowed' | 'denied'
  decidedBy: 'policy' | 'admin'
  reason: 'policy.auto_allowed' | 'admin.confirmed' | 'requires_admin_approval' | 'policy.default_deny'
  requiresAdminPrompt: boolean
}

const ROLE_RANK: Record<AcpRole, number> = { viewer: 1, member: 2, admin: 3, owner: 4 }

export function evaluateToolRequest(input: { tool: string; role: AcpRole }): PermissionDecision {
  if (POLICY_AUTO_ALLOWED_TOOLS.includes(input.tool)) {
    return { decision: 'allowed', decidedBy: 'policy', reason: 'policy.auto_allowed', requiresAdminPrompt: false }
  }
  const isAdmin = ROLE_RANK[input.role] >= ROLE_RANK.admin
  if (POLICY_ADMIN_REQUIRED_TOOLS.includes(input.tool)) {
    return isAdmin
      ? { decision: 'allowed', decidedBy: 'admin', reason: 'admin.confirmed', requiresAdminPrompt: false }
      : {
          decision: 'denied',
          decidedBy: 'policy',
          reason: 'requires_admin_approval',
          requiresAdminPrompt: true,
        }
  }
  return { decision: 'denied', decidedBy: 'policy', reason: 'policy.default_deny', requiresAdminPrompt: false }
}

/** 审批提示（企业 UI 内完成，不使用官方未提供的审批弹窗，§4.6.2 约束）。 */
export const AcpApprovalPrompt = {
  id: 'acp-approval',
  title: 'ACP 权限请求',
  surface: 'enterprise-ui',
  officialDialogAvailable: false,
  note: '官方未提供审批对话框，企业审批在企业 UI 或控制面完成',
} as const
