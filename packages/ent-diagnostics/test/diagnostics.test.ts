/**
 * T-026：客户端侧脱敏诊断上报（需求书 §7.1）。
 *
 * 断言重点：默认关闭、个人模式不发送、白名单外字段被拒、
 * 脱敏命中（Bearer / sk- / 验证码 / 已知密钥）、stderr 截断。
 */

import { describe, expect, it } from 'vitest'

import {
  DIAGNOSTIC_ALLOWED_FIELDS,
  RETENTION_DEFAULT_DAYS,
  RETENTION_MAX_DAYS,
  buildDiagnosticReport,
  clampRetentionDays,
  inspectLocally,
  isDiagnosticsEnabled,
  redactText,
  sendDiagnosticReport,
  truncateStderr,
} from '../src/index.js'

describe('§7.1 默认开关', () => {
  it('未开启时不启用；个人模式即使 adminEnabled 也不启用', () => {
    expect(isDiagnosticsEnabled({ adminEnabled: false, mode: 'enterprise' })).toBe(false)
    expect(isDiagnosticsEnabled({ adminEnabled: true, mode: 'personal' })).toBe(false)
    expect(isDiagnosticsEnabled({ adminEnabled: true, mode: 'enterprise' })).toBe(true)
  })

  it('个人模式不发送任何数据（优先级高于开关）', () => {
    const r = sendDiagnosticReport({ ok: true, report: {}, rejectedFields: [] },
      { adminEnabled: true, mode: 'personal' })
    expect(r).toEqual({ sent: false, reason: 'personal-mode' })
  })

  it('企业模式且开关打开，但 P1 无控制面 → 明确不发送', () => {
    const r = sendDiagnosticReport({ ok: true, report: {}, rejectedFields: [] },
      { adminEnabled: true, mode: 'enterprise' })
    expect(r).toEqual({ sent: false, reason: 'control-plane-not-connected' })
  })

  it('开关关闭时不发送', () => {
    const r = sendDiagnosticReport({ ok: true, report: {}, rejectedFields: [] },
      { adminEnabled: false, mode: 'enterprise' })
    expect(r).toEqual({ sent: false, reason: 'disabled' })
  })
})

describe('§7.1 字段白名单', () => {
  it('白名单恰为需求书列出的 9 项', () => {
    expect([...DIAGNOSTIC_ALLOWED_FIELDS]).toEqual([
      'runtimeVersion', 'platform', 'profileCheck', 'pluginInventory',
      'errorType', 'errorCode', 'errorSummary', 'timestamp', 'anonymousInstallId',
    ])
  })

  it('白名单外字段被拒并列出（含禁止上报字段）', () => {
    const r = buildDiagnosticReport({
      runtimeVersion: '0.2.0-rc.1',
      prompt: '用户正文不应上报',
      sessionTitle: '会话标题',
      filePath: 'D:\\secret\\path.docx',
      apiKey: 'sk-abcdefghijklmnop',
    })
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(Object.keys(r.report)).toEqual(['runtimeVersion'])
    expect(r.rejectedFields).toEqual(['apiKey', 'filePath', 'prompt', 'sessionTitle'])
  })
})

describe('脱敏', () => {
  it('Bearer token 被替换', () => {
    expect(redactText('Authorization: Bearer abc.def-123')).toBe('Authorization: Bearer [REDACTED]')
  })

  it('sk- 开头的密钥被替换', () => {
    expect(redactText('key=sk-abcdefghijklmnopqrst')).toBe('key=sk-[REDACTED]')
  })

  it('验证码语境下的 6 位数字被替换；无语境时不误伤', () => {
    expect(redactText('您的验证码是 123456，5 分钟内有效')).toContain('[REDACTED-CODE]')
    expect(redactText('验证码 123456')).not.toContain('123456')
    expect(redactText('build 123456 completed')).toContain('123456')
  })

  it('已知密钥原值被整体替换（优先于前缀规则）', () => {
    const secret = 'very-secret-value-123'
    expect(redactText(`conn=${secret}&x=1`, { knownSecrets: [secret] })).toBe('conn=[REDACTED-SECRET]&x=1')
  })

  it('errorSummary 与 profileCheck.detail 在上报前被脱敏', () => {
    const r = buildDiagnosticReport({
      errorSummary: 'request failed: Bearer eyJhbGciOi.J9',
      profileCheck: { ok: false, detail: 'token sk-abcdefghijklmnop rejected' },
    })
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.report.errorSummary).toBe('request failed: Bearer [REDACTED]')
    expect(r.report.profileCheck?.detail).toBe('token sk-[REDACTED] rejected')
  })
})

describe('stderr 截断', () => {
  it('短 stderr 原样返回（仍会被脱敏后用于本地查看）', () => {
    expect(truncateStderr('boom')).toBe('boom')
  })

  it('长 stderr 被截断并标注丢弃的插件输出长度', () => {
    const long = 'x'.repeat(5000)
    const out = truncateStderr(long, 1000)
    expect(out.startsWith('x'.repeat(1000))).toBe(true)
    expect(out).toContain('[truncated 4000 chars of plugin output]')
  })

  it('本地查看返回 stderr 预览但不发送', () => {
    const { report, stderrPreview } = inspectLocally(
      { runtimeVersion: '0.2.0-rc.1' },
      { officialStderr: `error Bearer abc.def\n${'y'.repeat(3000)}` },
    )
    expect(report.ok).toBe(true)
    expect(stderrPreview).toContain('Bearer [REDACTED]')
    expect(stderrPreview).toContain('[truncated')
  })
})

describe('留存期', () => {
  it('默认 30 天，上限 180 天', () => {
    expect(clampRetentionDays(0)).toBe(RETENTION_DEFAULT_DAYS)
    expect(clampRetentionDays(Number.NaN)).toBe(RETENTION_DEFAULT_DAYS)
    expect(clampRetentionDays(45)).toBe(45)
    expect(clampRetentionDays(365)).toBe(RETENTION_MAX_DAYS)
  })
})
