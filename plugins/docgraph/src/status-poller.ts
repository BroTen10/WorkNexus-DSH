/**
 * 任务状态轮询（T-072，需求书 P4-F04）。
 *
 * 规则：
 *  - 五态：排队 / 运行中 / 成功 / 失败 / 取消（`DocGraphJobState`），未知状态映射为 `unknown` 且不猜测；
 *  - **有上限**（`maxPolls`）与**退避**（`backoffFactor` / `maxIntervalMs`），避免高频轮询拖垮主界面；
 *  - 轮询失败（网络/超时/远端 5xx）不抛未捕获异常：记为 `unknown` 并继续退避重试，直到上限。
 */

import type { DocGraphJob, DocGraphJobState } from './client.js'

export type DocGraphStatusPort = {
  status(jobId: string): Promise<DocGraphJob>
}

export type CollectStatusesOptions = {
  intervalMs?: number
  maxPolls?: number
  backoffFactor?: number
  maxIntervalMs?: number
  /** 注入式等待，便于测试；默认使用 setTimeout。 */
  sleep?: (ms: number) => Promise<void>
}

export const TERMINAL_STATES: readonly DocGraphJobState[] = Object.freeze([
  'succeeded',
  'failed',
  'cancelled',
])

export const DEFAULT_POLL_INTERVAL_MS = 2000
export const DEFAULT_MAX_POLLS = 30
export const DEFAULT_BACKOFF_FACTOR = 1.5
export const DEFAULT_MAX_INTERVAL_MS = 15000

export function isTerminal(state: DocGraphJobState): boolean {
  return TERMINAL_STATES.includes(state)
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 轮询任务状态直到终态或达到上限，返回观察到的状态序列（含 `unknown`）。
 * 该函数**不会抛出**：任何异常都会被转换成一次 `unknown` 观测。
 */
export async function collectStatuses(
  client: DocGraphStatusPort,
  jobId: string,
  options: CollectStatusesOptions = {},
): Promise<DocGraphJobState[]> {
  const intervalMs = options.intervalMs ?? DEFAULT_POLL_INTERVAL_MS
  const maxPolls = Math.max(1, options.maxPolls ?? DEFAULT_MAX_POLLS)
  const backoffFactor = options.backoffFactor ?? DEFAULT_BACKOFF_FACTOR
  const maxIntervalMs = options.maxIntervalMs ?? DEFAULT_MAX_INTERVAL_MS
  const sleep = options.sleep ?? defaultSleep

  const seen: DocGraphJobState[] = []
  let delay = intervalMs
  for (let poll = 0; poll < maxPolls; poll += 1) {
    if (poll > 0) {
      await sleep(delay)
      delay = Math.min(Math.round(delay * backoffFactor), maxIntervalMs)
    }
    let state: DocGraphJobState = 'unknown'
    try {
      const job = await client.status(jobId)
      state = job?.state ?? 'unknown'
    } catch {
      state = 'unknown'
    }
    seen.push(state)
    if (isTerminal(state)) break
  }
  return seen
}
