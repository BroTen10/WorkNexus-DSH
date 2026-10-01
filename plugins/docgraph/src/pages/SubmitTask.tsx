/**
 * 任务提交页面声明（T-071，需求书 P4-F03）。
 *
 * 从项目空间提交文档分析/审查任务；提交动作要求 `docgraph.submit` 且必须是空间成员。
 */

export const DocGraphSubmitPage = {
  id: 'submit',
  uiSlot: 'worknexus.docgraph.submit',
  title: '提交 DocGraph 任务',
  permission: 'docgraph.submit',
  modes: ['analysis', 'review'],
  requiresSpaceMembership: true,
} as const
