/**
 * @worknexus/ent-core/skeleton —— Host Core 契约骨架的挂载点（T-029）。
 *
 * 职责：把 `@worknexus/contracts`（八类契约 + 契约版本 v1）作为**预置 bundle**的一部分
 * 暴露给企业插件层，证明「Host Core 契约随发行版预置且可被解析」。
 *
 * 禁止事项（T-029 派发卡）：
 *  - 不在骨架里实现业务逻辑；
 *  - 不连接企业控制面；
 *  - 不实现 `AgentTransport`（需求书 §6.4 策略 1）。
 */

import {
  ENTERPRISE_EVENT_TOPICS,
  HOST_CORE_CONTRACT_VERSION,
  ROLES,
} from '@worknexus/contracts'

export const name = 'ent-core-skeleton'

export { HOST_CORE_CONTRACT_VERSION }

export function describe() {
  return {
    ok: true,
    detail: 'host core contract skeleton mounted from @worknexus/contracts',
    contractVersion: HOST_CORE_CONTRACT_VERSION,
    roles: ROLES,
    enterpriseEventTopics: ENTERPRISE_EVENT_TOPICS,
    // 显式声明骨架不承载的三件事，便于自检与审计
    carriesBusinessData: false,
    connectsControlPlane: false,
    implementsAgentTransport: false,
  }
}

export function apply() {
  // 骨架不得有副作用：不注册服务、不订阅事件、不改动官方行为。
}
