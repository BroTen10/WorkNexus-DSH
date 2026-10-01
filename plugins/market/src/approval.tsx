/**
 * 安装审批提示（T-102，需求书 P6B-F03、§3.5）。
 *
 * 官方未提供审批弹窗，因此审批提示在企业 UI 内展示、审批动作由企业控制面完成；
 * 个人模式不强制白名单，只提示「已记录安装请求」。
 */

export type ApprovalAction = 'install' | 'update' | 'enable' | 'disable'

export type ApprovalPromptInput = {
  pluginId: string
  version: string
  action: ApprovalAction
  mode: 'personal' | 'enterprise'
  whitelisted: boolean
}

export type ApprovalPrompt = {
  visible: boolean
  surface: 'enterprise-ui'
  status: 'pending-approval' | 'not-whitelisted' | 'recorded-only' | 'allowed'
  title: string
  detail: string
}

export const APPROVAL_ACTION_LABELS: Record<ApprovalAction, string> = {
  install: '安装',
  update: '更新',
  enable: '启用',
  disable: '禁用',
}

export function buildApprovalPrompt(input: ApprovalPromptInput): ApprovalPrompt {
  const label = APPROVAL_ACTION_LABELS[input.action]
  if (input.mode === 'personal') {
    return {
      visible: true,
      surface: 'enterprise-ui',
      status: 'recorded-only',
      title: `${label} ${input.pluginId}`,
      detail: '个人模式不强制企业白名单：本次安装请求仅被记录，不阻塞安装',
    }
  }
  if (!input.whitelisted) {
    return {
      visible: true,
      surface: 'enterprise-ui',
      status: 'not-whitelisted',
      title: `${label} ${input.pluginId}@${input.version}`,
      detail: '企业模式下未通过白名单不能安装；请提交审批，由管理员在控制面批准',
    }
  }
  return {
    visible: true,
    surface: 'enterprise-ui',
    status: 'allowed',
    title: `${label} ${input.pluginId}@${input.version}`,
    detail: '已通过白名单，安装动作交由官方插件管理器执行',
  }
}

export function isEnterpriseWhitelistEnforced(mode: 'personal' | 'enterprise'): boolean {
  return mode === 'enterprise'
}
