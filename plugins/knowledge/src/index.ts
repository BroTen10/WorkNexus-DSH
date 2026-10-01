import { ConnectionsPage } from './pages/Connections.js'
import { KnowledgeAdminPage } from './pages/KnowledgeAdmin.js'

export const KNOWLEDGE_PAGES = Object.freeze([ConnectionsPage, KnowledgeAdminPage])

export {
  HTTP_RAG_DEFAULT_HEALTH_PATH,
  HTTP_RAG_DEFAULT_LIMIT,
  HTTP_RAG_DEFAULT_SEARCH_PATH,
  HTTP_RAG_DEFAULT_TIMEOUT_MS,
  createHttpRagProvider,
  describeConnection,
  sanitizeDetail,
  validateHttpRagConfig,
  type HttpRagConfig,
  type HttpRagConnectionDescriptor,
  type HttpRagFetchLike,
} from './providers/http-rag.js'

export { canManageKnowledge, canRender, visiblePages, type KnowledgePermission } from './permissions.js'

export { isChunkVisible, retrieveForSpace, sessionSpaceScope, type RetrieveForSpaceInput } from './retrieve.js'

export {
  resolveKnowledgeForSpace,
  type KnowledgeBindingRecord,
  type KnowledgeBindingsApi,
  type ResolvedKnowledgeBinding,
} from './binding.js'

export { Citations, toCitationItems, type CitationItem } from './citations.js'

export {
  KNOWLEDGE_ADMIN_ACTIONS,
  KnowledgeAdminPage,
  adminActionsFor,
  type KnowledgeAdminAction,
  type KnowledgeAdminActionId,
} from './pages/KnowledgeAdmin.js'
