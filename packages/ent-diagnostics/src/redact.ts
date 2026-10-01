/**
 * 脱敏与截断（需求书 §7.1「脱敏要求」/ §4.2.4 同一规则）。
 *
 * 规则：
 *  - `Bearer <token>` → `Bearer [REDACTED]`
 *  - `sk-…` → `sk-[REDACTED]`
 *  - 验证码（6 位数字，且邻近「验证码 / code / otp / 校验码」语境）→ `[REDACTED-CODE]`
 *  - 已知密钥原值（调用方传入）→ `[REDACTED-SECRET]`
 *  - 官方 stderr 尾部中的插件输出：按上限**截断**并标注
 */

export const REDACTED_TOKEN = 'Bearer [REDACTED]'
export const REDACTED_API_KEY = 'sk-[REDACTED]'
export const REDACTED_CODE = '[REDACTED-CODE]'
export const REDACTED_SECRET = '[REDACTED-SECRET]'

/** stderr 截断上限（字符）：只保留头部，尾部插件输出被截断。 */
export const STDERR_MAX_CHARS = 2000

const BEARER = /Bearer\s+[A-Za-z0-9._~+/=-]+/gu
const API_KEY = /sk-[A-Za-z0-9._-]{8,}/gu
// 注意：检测用的正则**不带 g 标志**——带 g 时 RegExp.test 会推进 lastIndex，
// 导致同一正则在连续调用间给出不一致结果（本次单测实际捕获到该缺陷）。
const CODE_CONTEXT = /(验证码|校验码|动态码|otp|one[- ]time code|verification code)/iu
const SIX_DIGITS = /\b\d{6}\b/gu

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')
}

export type RedactOptions = {
  /** 已知密钥原值：出现即替换，避免按前缀规则漏网。 */
  knownSecrets?: readonly string[]
}

/**
 * 对任意文本做脱敏。顺序刻意固定：先替换已知密钥原值（最长匹配优先），
 * 再处理 Bearer / sk- / 验证码。
 */
export function redactText(text: string, options: RedactOptions = {}): string {
  let out = text
  const secrets = [...(options.knownSecrets ?? [])]
    .filter((s) => s.length >= 4)
    .sort((a, b) => b.length - a.length)
  for (const secret of secrets) {
    out = out.replace(new RegExp(escapeRegExp(secret), 'gu'), REDACTED_SECRET)
  }
  out = out.replace(BEARER, REDACTED_TOKEN)
  out = out.replace(API_KEY, REDACTED_API_KEY)
  // 只在出现验证码语境时替换 6 位数字，避免误伤版本号/时间戳
  if (CODE_CONTEXT.test(out)) {
    out = out.replace(SIX_DIGITS, REDACTED_CODE)
  }
  return out
}

/**
 * 截断 stderr：官方 stderr 尾部可能混入插件输出，故只保留头部并标注截断。
 */
export function truncateStderr(stderr: string, maxChars: number = STDERR_MAX_CHARS): string {
  const flat = stderr.replace(/\r\n/gu, '\n')
  if (flat.length <= maxChars) return flat
  return `${flat.slice(0, maxChars)}\n…[truncated ${flat.length - maxChars} chars of plugin output]`
}
