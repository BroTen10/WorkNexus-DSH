/**
 * 引用展示（T-064，需求书 P3-F06）。
 *
 * 契约：Agent 回答中的知识库来源必须可追溯到**文档、片段或链接**——
 * 因此每条引用都保留 `documentId`、`title`、`snippet`，有链接时一并展示。
 *
 * 上游技术栈：使用官方 Web 端的 React 18 组件形态（不引入第二套设计系统）；
 * 具体视觉样式跟随官方主题（B 类真机项）。
 */

import type { ReactElement } from 'react'
import type { KnowledgeChunk } from '@worknexus/contracts'

export type CitationItem = {
  documentId: string
  title: string
  snippet: string
  url?: string
  score?: number
}

/** 把检索命中转成可追溯的引用条目（丢弃缺文档标识的脏数据）。 */
export function toCitationItems(chunks: readonly KnowledgeChunk[]): CitationItem[] {
  return chunks
    .filter((chunk) => typeof chunk.documentId === 'string' && chunk.documentId.length > 0)
    .map((chunk) =>
      chunk.url === undefined
        ? { documentId: chunk.documentId, title: chunk.title, snippet: chunk.snippet, score: chunk.score }
        : { documentId: chunk.documentId, title: chunk.title, snippet: chunk.snippet, url: chunk.url, score: chunk.score },
    )
}

export function Citations({ chunks }: { chunks: readonly KnowledgeChunk[] }): ReactElement {
  const items = toCitationItems(chunks)
  if (items.length === 0) {
    return <p className="worknexus-knowledge-citations-empty">无引用</p>
  }
  return (
    <ul className="worknexus-knowledge-citations">
      {items.map((item) => (
        <li key={item.documentId} data-document-id={item.documentId}>
          <span className="worknexus-knowledge-citation-title">{item.title}</span>
          <span className="worknexus-knowledge-citation-snippet">{item.snippet}</span>
          {item.url === undefined ? null : (
            <a className="worknexus-knowledge-citation-link" href={item.url} rel="noreferrer" target="_blank">
              {item.url}
            </a>
          )}
        </li>
      ))}
    </ul>
  )
}
