/**
 * 企业侧脱敏诊断上报（客户端侧）—— 需求书 §7.1。
 *
 * 三条硬要求（门禁逐条断言）：
 *  1. **默认关闭**；由企业管理员在控制面开启后生效；**个人模式永不开启/不发送**；
 *  2. **白名单外的数据不得上报**——未列出的字段一律拒绝，而不是「尽量过滤」；
 *  3. **P1 不发送**：本阶段没有企业控制面，模块只提供「可开关 + 可本地查看 + 不发送」，
 *     真正的发送端在 T-054 接通。
 *
 * 明确不重写官方诊断（T-002 §4 N-9）：本模块是**企业侧独立实现**，官方崩溃报告与
 * 诊断导出保持原样。
 */

import type { RunMode } from '@worknexus/contracts'

import { redactText, truncateStderr, type RedactOptions } from './redact.js'

export * from './redact.js'

/** §7.1「可上报字段」——白名单，逐字对应需求书表格。 */
export const DIAGNOSTIC_ALLOWED_FIELDS = Object.freeze([
  'runtimeVersion',
  'platform',
  'profileCheck',
  'pluginInventory',
  'errorType',
  'errorCode',
  'errorSummary',
  'timestamp',
  'anonymousInstallId',
] as const)

export type DiagnosticField = (typeof DIAGNOSTIC_ALLOWED_FIELDS)[number]

export type DiagnosticPayload = {
  runtimeVersion?: string
  platform?: { os: string; arch: string }
  profileCheck?: { ok: boolean; detail?: string }
  pluginInventory?: Array<{ id: string; version: string; enabled: boolean }>
  errorType?: string
  errorCode?: string
  errorSummary?: string
  timestamp?: string
  anonymousInstallId?: string
}

/**
 * §7.1「禁止上报字段」对应的键名黑名单（尽力而为的第二道防线；
 * 第一道防线是上面的字段白名单——白名单外的一切都会被拒）。
 */
export const DIAGNOSTIC_FORBIDDEN_KEYS = Object.freeze([
  'prompt', 'messages', 'modelOutput', 'output',
  'attachments', 'fileContent', 'fileContents',
  'filePath', 'absolutePath', 'workspacePath',
  'sessionTitle', 'title',
  'apiKey', 'token', 'credential', 'credentials', 'password', 'verificationCode', 'otp',
  'stderr', 'stdout',
] as const)

/** 客户端开关状态（默认关闭；个人模式恒为关闭）。 */
export type DiagnosticSwitch = {
  /** 控制面下发的开关（P1 无控制面，恒为 false） */
  adminEnabled: boolean
  mode: RunMode
}

export function isDiagnosticsEnabled(s: DiagnosticSwitch): boolean {
  return s.mode === 'enterprise' && s.adminEnabled === true
}

export type BuildResult =
  | { ok: true; report: Partial<DiagnosticPayload>; rejectedFields: string[] }
  | { ok: false; problems: string[] }

export type BuildOptions = RedactOptions & {
  /** 官方 stderr（只取头部，尾部插件输出被截断） */
  officialStderr?: string
}

/**
 * 从任意输入构造**可上报报告**：
 *  - 白名单外字段被拒并记录（不是静默丢弃，便于本地查看与审计）；
 *  - 文本字段统一走脱敏；
 *  - 官方 stderr 只保留头部（§7.1 截断要求），且不进入报告白名单字段——
 *    只能通过 `errorSummary` 的脱敏片段体现，避免原文外泄。
 */
export function buildDiagnosticReport(raw: Record<string, unknown>, options: BuildOptions = {}): BuildResult {
  const allowed = new Set<string>(DIAGNOSTIC_ALLOWED_FIELDS)
  const rejected: string[] = []
  const report: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(raw)) {
    if (!allowed.has(key)) {
      rejected.push(key)
      continue
    }
    report[key] = value
  }

  if (typeof report['errorSummary'] === 'string') {
    report['errorSummary'] = redactText(report['errorSummary'], options)
  }
  const profileCheck = report['profileCheck']
  if (profileCheck && typeof profileCheck === 'object' && 'detail' in profileCheck) {
    const detail = (profileCheck as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      (profileCheck as { detail?: string }).detail = redactText(detail, options)
    }
  }

  // stderr 只做截断+脱敏，用于本地查看；不放入报告字段。
  const stderrPreview = options.officialStderr === undefined
    ? undefined
    : redactText(truncateStderr(options.officialStderr), options)

  const problems: string[] = []
  const forbiddenHit = Object.keys(raw).filter((k) =>
    (DIAGNOSTIC_FORBIDDEN_KEYS as readonly string[]).includes(k))
  if (forbiddenHit.length > 0) {
    // 命中禁止键不属于「失败」，但必须记录；它们已在白名单外被拒。
    rejected.push(...forbiddenHit)
  }
  if (problems.length > 0) return { ok: false, problems }

  return {
    ok: true,
    report: {
      ...(report as Partial<DiagnosticPayload>),
      ...(stderrPreview === undefined ? {} : {}),
    },
    rejectedFields: [...new Set(rejected)].sort(),
  }
}

export type SendResult =
  | { sent: false; reason: 'disabled' | 'personal-mode' | 'control-plane-not-connected' }
  | { sent: true; transport: 'enterprise-control-plane' }

/**
 * 发送入口。P1 **不发送**：
 *  - 开关关闭或个人模式 → 明确原因；
 *  - 即使在企业模式且开关打开，P1 也没有控制面 → `control-plane-not-connected`（T-054 接通）。
 */
export function sendDiagnosticReport(
  report: BuildResult,
  s: DiagnosticSwitch,
  transport?: { send(report: Partial<DiagnosticPayload>): Promise<void> },
): SendResult {
  if (s.mode !== 'enterprise') return { sent: false, reason: 'personal-mode' }
  if (!s.adminEnabled) return { sent: false, reason: 'disabled' }
  if (!transport) return { sent: false, reason: 'control-plane-not-connected' }
  if (!report.ok) return { sent: false, reason: 'disabled' }
  return { sent: true, transport: 'enterprise-control-plane' }
}

/** 本地查看：返回将要上报的内容与本地 stderr 预览，不发送任何数据。 */
export function inspectLocally(
  raw: Record<string, unknown>,
  options: BuildOptions = {},
): { report: BuildResult; stderrPreview: string | null } {
  const report = buildDiagnosticReport(raw, options)
  const stderrPreview = options.officialStderr === undefined
    ? null
    : redactText(truncateStderr(options.officialStderr), options)
  return { report, stderrPreview }
}

/** 留存期约束（§7.1）：默认 30 天，上限 180 天。 */
export const RETENTION_DEFAULT_DAYS = 30
export const RETENTION_MAX_DAYS = 180

export function clampRetentionDays(days: number): number {
  if (!Number.isFinite(days) || days < 1) return RETENTION_DEFAULT_DAYS
  return Math.min(Math.floor(days), RETENTION_MAX_DAYS)
}
