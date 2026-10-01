/**
 * 任务列表页面声明（T-072）。
 *
 * 五态展示 + 退避轮询；未知状态显式显示「未知」，不猜测。
 */

export const JOB_STATE_LABELS = Object.freeze({
  queued: '排队中',
  running: '运行中',
  succeeded: '成功',
  failed: '失败',
  cancelled: '已取消',
  unknown: '未知',
} as const)

export const DocGraphJobListPage = {
  id: 'jobs',
  uiSlot: 'worknexus.docgraph.jobs',
  title: 'DocGraph 任务',
  permission: 'docgraph.read',
  states: ['queued', 'running', 'succeeded', 'failed', 'cancelled', 'unknown'],
  polling: { intervalMs: 2000, maxPolls: 30, backoffFactor: 1.5, maxIntervalMs: 15000 },
} as const
