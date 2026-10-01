/**
 * @worknexus/ent-core —— WorkNexus-DSH 企业基座 bundle 的健康探针插件。
 *
 * 职责边界（严格限定）：
 *  - 只做「企业基座是否已随发行版加载」的可观测性；
 *  - **不**承载企业业务数据、**不**连接企业控制面、**不**实现 AgentTransport
 *    （需求书 §4.1.4 第 2 条、§6.4 策略 1、T-029 禁止事项）。
 *
 * 之所以可以做最小的 apply：bundle patch 的 insert 行需要一个可解析的模块，
 * 否则该行会在装配阶段被记为解析失败——这正好也是 T-023 失败隔离要覆盖的场景。
 */

export const name = 'ent-core-health'

/** 企业在 P1 阶段对外可见的状态快照（纯内存，不落盘、不联网）。 */
export const ENT_CORE_STATE = Object.freeze({
  bundle: '@worknexus/ent-core',
  hostCore: 'skeleton',
  enterpriseData: false,
  controlPlane: 'not-connected',
})

export function describe() {
  return {
    ok: true,
    detail: 'ent-core loaded as a prepended profile bundle',
    ...ENT_CORE_STATE,
  }
}

/**
 * Cordis 插件入口。
 *
 * 刻意做成「零依赖、零副作用」：不注册服务、不订阅事件、不改任何官方行为。
 * 这样即使企业侧后续被禁用（T-005 实测：用户层可 disabled 条目），
 * 官方会话链路也不会因为本 bundle 的缺失而缺少任何依赖。
 */
export function apply(ctx) {
  if (ctx && typeof ctx.logger?.info === 'function') {
    ctx.logger.info('[ent-core] host core skeleton mounted (no business data, no control plane)')
  }
}
