/**
 * Agent 会话联动（T-075，需求书 P4-F09）。
 *
 * 边界：
 *  - **只调用官方支持的能力**：本模块只产出「可被会话引用的文本/摘要」，不接管交互主链路，
 *    也不新增 `AgentTransport` 实现（总览 §2.1 第 16 条、§11 第 1/2 条）；
 *  - 官方未提供的能力（删除会话、Fork、转录回放）**显式返回不支持**，不伪装（§2.1 第 14 条）；
 *  - 引用必须带空间上下文：越权结果不得进入会话（P4-F06 的延伸约束）。
 */

import type { SpaceContext } from '@worknexus/contracts'

export type DocGraphResultReference = {
  type: 'docgraph.result'
  jobId: string
  spaceId: string
  summary: string
  sourceUrl?: string
  text: string
}

export type BuildReferenceInput = {
  jobId: string
  spaceId: string
  summary: string
  sourceUrl?: string
  findingCount?: number
}

export type ReferenceDecision = { ok: true; reference: DocGraphResultReference } | { ok: false; reason: 'denied' }

export type UnsupportedCapability =
  | 'session.delete'
  | 'session.fork'
  | 'transcript.replay'
  | 'transcript.export'

export const UNSUPPORTED_AGENT_CAPABILITIES: readonly UnsupportedCapability[] = Object.freeze([
  'session.delete',
  'session.fork',
  'transcript.replay',
  'transcript.export',
])

const MAX_SUMMARY = 2000

/** 构造可被 Agent 会话引用的结果引用（带空间归属，缺省不携带正文）。 */
export function buildResultReference(input: BuildReferenceInput): DocGraphResultReference {
  const summary = input.summary.slice(0, MAX_SUMMARY)
  const findings = typeof input.findingCount === 'number' ? `共 ${input.findingCount} 项发现` : ''
  const text = [
    `DocGraph 任务 ${input.jobId} 的审查结果：${summary}`,
    findings,
    input.sourceUrl ? `原文：${input.sourceUrl}` : '',
  ].filter((part) => part.length > 0).join('；')
  return input.sourceUrl === undefined
    ? { type: 'docgraph.result', jobId: input.jobId, spaceId: input.spaceId, summary, text }
    : { type: 'docgraph.result', jobId: input.jobId, spaceId: input.spaceId, summary, sourceUrl: input.sourceUrl, text }
}

/** 空间校验：只有当前会话空间（或其部门/组织范围）的引用才可进入会话。 */
export function referenceIsVisible(reference: DocGraphResultReference, spaceContext: SpaceContext): boolean {
  const scope = [spaceContext.projectSpaceId, spaceContext.departmentId, spaceContext.organizationId]
    .filter((value): value is string => typeof value === 'string' && value.length > 0)
  return scope.includes(reference.spaceId)
}

export function decideReference(
  reference: DocGraphResultReference,
  spaceContext: SpaceContext,
): ReferenceDecision {
  return referenceIsVisible(reference, spaceContext) ? { ok: true, reference } : { ok: false, reason: 'denied' }
}

/** 预置 prompt：说明这是 DocGraph 结果引用，由官方会话能力承载，不承诺自动化。 */
export function buildReferencePrompt(reference: DocGraphResultReference, question?: string): string {
  const ask = question ?? '请总结这份 DocGraph 审查结果，并指出需要人工确认的项。'
  return `${ask}\n\n【DocGraph 结果引用】\n${reference.text}\n（来源：DocGraph 任务 ${reference.jobId}；请勿编造引用之外的内容。）`
}

/**
 * 官方未支持的能力统一在这里显式拒绝——**不调用任何官方接口，也不伪装成功**。
 * 降级路径：把结果摘要复制到会话（由调用方使用 `buildReferencePrompt` 完成）。
 */
export function requestUnsupportedCapability(
  capability: UnsupportedCapability,
): { ok: false; unsupported: true; detail: string } {
  return {
    ok: false,
    unsupported: true,
    detail: `agent-unsupported: 官方会话未提供 ${capability}（总览 §2.1 第 14 条），降级为复制结果摘要到会话`,
  }
}
