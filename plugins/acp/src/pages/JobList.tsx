/**
 * 后台任务列表页面声明（T-091，需求书 §4.6.1 验收 2/3）。
 *
 * 只声明页面与可用操作；任务本身由控制面 `/api/v1/jobs` 承载，插件不代理 ACP 运行时。
 */

export const JOB_STATUS_LABELS = Object.freeze({
  queued: '排队中',
  running: '运行中',
  succeeded: '成功',
  failed: '失败',
  cancelled: '已取消',
  closed: '已关闭',
} as const)

export const JOB_ACTIONS = Object.freeze(['cancel', 'resume', 'close'] as const)

export const AcpJobListPage = {
  id: 'jobs',
  uiSlot: 'worknexus.acp.jobs',
  title: '后台自动化任务',
  permission: 'session.create',
  actions: JOB_ACTIONS,
  statuses: Object.keys(JOB_STATUS_LABELS),
  backgroundOnly: true,
} as const
