/**
 * T-064：引用可追溯到文档 / 片段 / 链接（P3-F06）。
 */

import { describe, expect, it } from 'vitest'
import { renderToString } from 'react-dom/server'

import { Citations, toCitationItems } from '../src/citations.js'
import type { KnowledgeChunk } from '@worknexus/contracts'

type ChunkOverride = Partial<Omit<KnowledgeChunk, 'url'>> & { url?: string | undefined }

const chunk = (over: ChunkOverride = {}): KnowledgeChunk => {
  const merged = {
    documentId: 'd1',
    title: '合同模板',
    snippet: '条款 A',
    score: 0.9,
    url: 'https://x/1' as string | undefined,
    ...over,
  }
  if (merged.url === undefined) {
    const { url: _omitted, ...rest } = merged
    return { ...rest }
  }
  const { url, ...rest } = merged
  return { ...rest, url }
}

describe('citations', () => {
  it('renders title, snippet and link for each chunk', () => {
    const html = renderToString(<Citations chunks={[chunk()]} />)
    expect(html).toContain('合同模板')
    expect(html).toContain('条款 A')
    expect(html).toContain('https://x/1')
    expect(html).toContain('data-document-id="d1"')
  })

  it('keeps chunks traceable without a link and escapes html in the snippet', () => {
    const html = renderToString(<Citations chunks={[chunk({ url: undefined, snippet: '<script>x</script>' })]} />)
    expect(html).toContain('data-document-id="d1"')
    expect(html).toContain('&lt;script&gt;')
    expect(html).not.toContain('<script>')
  })

  it('renders an explicit empty state and drops chunks without a document id', () => {
    const html = renderToString(
      <Citations chunks={[chunk({ documentId: '' })]} />,
    )
    expect(html).toContain('无引用')
    expect(toCitationItems([chunk({ documentId: '' })])).toEqual([])
  })
})
