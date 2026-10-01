/**
 * T-063：空间绑定与会话继承（P3-F03 / P3-F04）。
 */

import { describe, expect, it, vi } from 'vitest'

import {
  resolveKnowledgeForSpace,
  type KnowledgeBindingRecord,
  type KnowledgeBindingsApi,
} from '../src/binding.js'

function bindingsApi(rows: KnowledgeBindingRecord[]): KnowledgeBindingsApi {
  return { listBindings: vi.fn(async () => rows) }
}

const row = (over: Partial<KnowledgeBindingRecord> & { id: string }): KnowledgeBindingRecord => ({
  providerId: 'ragflow',
  enabled: true,
  ...over,
})

describe('session inherits space knowledge', () => {
  it('returns only bindings bound to the session space', async () => {
    const out = await resolveKnowledgeForSpace(
      { organizationId: 'o', projectSpaceId: 's1', role: 'member' },
      bindingsApi([
        row({ id: 'b1', spaceId: 's1' }),
        row({ id: 'b2', spaceId: 's2' }),
      ]),
    )
    expect(out.map((binding) => binding.bindingId)).toEqual(['b1'])
  })

  it('ignores disabled bindings', async () => {
    const out = await resolveKnowledgeForSpace(
      { organizationId: 'o', projectSpaceId: 's1', role: 'member' },
      bindingsApi([row({ id: 'b1', spaceId: 's1', enabled: false })]),
    )
    expect(out).toEqual([])
  })

  it('inherits department-level bindings into that department project spaces', async () => {
    const out = await resolveKnowledgeForSpace(
      { organizationId: 'o', departmentId: 'd1', projectSpaceId: 's1', role: 'member' },
      bindingsApi([
        row({ id: 'b-dept', departmentId: 'd1' }),
        row({ id: 'b-space', projectSpaceId: 's1' }),
        row({ id: 'b-other-dept', departmentId: 'd2' }),
        row({ id: 'b-other-space', projectSpaceId: 's2' }),
      ]),
    )
    expect(out.map((binding) => binding.bindingId)).toEqual(['b-dept', 'b-space'])
    expect(out.map((binding) => binding.scopeId)).toEqual(['d1', 's1'])
  })

  it('does not treat the organization itself as a binding scope (P3-F03)', async () => {
    const out = await resolveKnowledgeForSpace(
      { organizationId: 'o', projectSpaceId: 's1', role: 'member' },
      bindingsApi([row({ id: 'b-org', organizationId: 'o' })]),
    )
    expect(out).toEqual([])
  })

  it('orders multiple knowledge bases of one space by weight then id, and skips sessions without a space', async () => {
    const out = await resolveKnowledgeForSpace(
      { organizationId: 'o', projectSpaceId: 's1', role: 'member' },
      bindingsApi([
        row({ id: 'b2', projectSpaceId: 's1', weight: 1 }),
        row({ id: 'b1', projectSpaceId: 's1', weight: 5 }),
        row({ id: 'b3', projectSpaceId: 's1', weight: 5 }),
      ]),
    )
    expect(out.map((binding) => binding.bindingId)).toEqual(['b1', 'b3', 'b2'])

    const none = await resolveKnowledgeForSpace(
      { organizationId: 'o', role: 'viewer' },
      bindingsApi([row({ id: 'b1', projectSpaceId: 's1' })]),
    )
    expect(none).toEqual([])
  })

  it('degrades to an empty list when the control plane is unreachable', async () => {
    const failing: KnowledgeBindingsApi = {
      listBindings: async () => {
        throw new Error('control plane down')
      },
    }
    await expect(
      resolveKnowledgeForSpace({ organizationId: 'o', projectSpaceId: 's1', role: 'member' }, failing),
    ).resolves.toEqual([])
  })
})
