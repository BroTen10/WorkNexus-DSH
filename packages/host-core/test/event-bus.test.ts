import { describe, expect, it } from 'vitest'

import { createEnterpriseEventChannel, type OfficialEventContext } from '../src/event-bus.js'
import type { EnterpriseEvent } from '@worknexus/contracts'

class FakeOfficialContext implements OfficialEventContext {
  readonly registeredTopics = new Set<string>()
  readonly officialTopics = new Set<string>()
  readonly listeners = new Map<string, Array<(event: EnterpriseEvent) => void>>()

  on(topic: string, handler: (event: EnterpriseEvent) => void): () => void {
    this.registeredTopics.add(topic)
    const list = this.listeners.get(topic) ?? []
    list.push(handler)
    this.listeners.set(topic, list)
    return () => {
      const current = this.listeners.get(topic)
      if (current) this.listeners.set(topic, current.filter(item => item !== handler))
    }
  }

  emit(topic: string, event: EnterpriseEvent): void {
    this.officialTopics.add(topic)
    for (const handler of this.listeners.get(topic) ?? []) handler(event)
  }
}

const baseEvent = {
  topic: 'ent.identity.changed',
  occurredAt: '2026-09-29T00:00:00.000Z',
  actorUserId: 'u1',
  organizationId: 'o1',
  payload: {},
  source: 'test',
} as const satisfies EnterpriseEvent

describe('enterprise event channel', () => {
  it('isolates a throwing subscriber from the others and the official dispatch', () => {
    const official = new FakeOfficialContext()
    const errors: string[] = []
    const seen: string[] = []
    const bus = createEnterpriseEventChannel({
      official,
      onError: (input) => { errors.push(input.error instanceof Error ? input.error.message : String(input.error)) },
    })
    bus.subscribe('ent.identity.changed', () => { throw new Error('bad subscriber') })
    bus.subscribe('ent.identity.changed', (event) => { seen.push(event.source) })
    bus.publish(baseEvent)
    expect(seen).toEqual(['test'])
    expect(errors).toEqual(['bad subscriber'])
  })

  it('stops delivery after unsubscribe', () => {
    const official = new FakeOfficialContext()
    const bus = createEnterpriseEventChannel({ official })
    let count = 0
    const off = bus.subscribe('ent.identity.changed', () => { count += 1 })
    off()
    bus.publish(baseEvent)
    expect(count).toBe(0)
  })

  it('only registers enterprise topics on the official context', () => {
    const official = new FakeOfficialContext()
    const bus = createEnterpriseEventChannel({ official })
    bus.subscribe('ent.identity.changed', () => {})
    expect([...official.registeredTopics]).toEqual(['ent.identity.changed'])
    expect([...official.officialTopics]).toEqual([])
    bus.publish(baseEvent)
    expect([...official.officialTopics]).toEqual(['ent.identity.changed'])
  })

  it('rejects topics outside the enterprise namespace', () => {
    const official = new FakeOfficialContext()
    const bus = createEnterpriseEventChannel({ official })
    expect(() => bus.subscribe('official.topic', () => {})).toThrow(/not in the enterprise whitelist/)
    expect(() => bus.publish({ ...baseEvent, topic: 'official.topic' })).toThrow(/not in the enterprise whitelist/)
    expect(official.registeredTopics.size).toBe(0)
    expect(official.officialTopics.size).toBe(0)
  })
})
