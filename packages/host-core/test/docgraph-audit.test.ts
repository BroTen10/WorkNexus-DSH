/**
 * T-074：DocGraph 审计事件与用量记录的纯函数契约。
 */

import { describe, expect, it } from 'vitest'

import {
  DOCGRAPH_AUDIT_ACTIONS,
  buildDocGraphAuditEvent,
  buildDocGraphUsageRecord,
} from '../src/docgraph-audit.js'

describe('docgraph audit and usage helpers', () => {
  it('covers the four audited actions', () => {
    expect(DOCGRAPH_AUDIT_ACTIONS).toEqual([
      'docgraph.submit',
      'docgraph.view',
      'docgraph.cancel',
      'docgraph.result',
    ])
  })

  it('builds an audit event carrying ent-prefixed remote identifiers', () => {
    const event = buildDocGraphAuditEvent({
      action: 'docgraph.submit',
      jobId: 'j1',
      organizationId: 'o',
      spaceId: 's',
      userId: 'u',
      remoteTaskId: 'task-9',
      contractId: 'c-1',
    })
    expect(event).toMatchObject({
      action: 'docgraph.submit',
      resourceType: 'background_job',
      resourceId: 'j1',
      result: 'success',
      entRemoteTaskId: 'task-9',
      entContractId: 'c-1',
    })
    expect(event.summary.length).toBeLessThanOrEqual(200)
  })

  it('marks denied events and never invents token counts', () => {
    const denied = buildDocGraphAuditEvent(
      { action: 'docgraph.view', jobId: 'j1', organizationId: 'o', spaceId: 's', userId: 'u' },
      'denied',
    )
    expect(denied.result).toBe('denied')
    expect(denied.entRemoteTaskId).toBeNull()

    const usage = buildDocGraphUsageRecord({
      jobId: 'j1',
      organizationId: 'o',
      spaceId: 's',
      userId: 'u',
      mode: 'review',
    })
    expect(usage).toMatchObject({
      usageId: 'docgraph:j1',
      pluginId: 'docgraph',
      source: 'adapter_estimate',
      promptTokens: null,
      completionTokens: null,
      totalTokens: null,
      estimatedCost: null,
    })
  })
})
