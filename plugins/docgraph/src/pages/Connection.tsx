/**
 * DocGraph 连接页面（T-070 声明）。
 *
 * 只声明页面身份与所需权限；Token 输入框必须允许留空并标注「取决于部署侧网关」（T-009 C-1）。
 */

export const DocGraphConnectionPage = {
  id: 'connection',
  uiSlot: 'worknexus.docgraph.connection',
  title: 'DocGraph 连接',
  permission: 'docgraph.submit',
  credentialOptional: true,
  authNote: 'gateway-dependent',
} as const
