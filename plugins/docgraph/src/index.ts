import { DocGraphConnectionPage } from './pages/Connection.js'
import { DocGraphJobListPage } from './pages/JobList.js'
import { DocGraphSubmitPage } from './pages/SubmitTask.js'

export const DOCGRAPH_PAGES = Object.freeze([DocGraphConnectionPage, DocGraphSubmitPage, DocGraphJobListPage])

export {
  DEFAULT_BACKOFF_FACTOR,
  DEFAULT_MAX_INTERVAL_MS,
  DEFAULT_MAX_POLLS,
  DEFAULT_POLL_INTERVAL_MS,
  TERMINAL_STATES,
  collectStatuses,
  isTerminal,
  type CollectStatusesOptions,
  type DocGraphStatusPort,
} from './status-poller.js'

export {
  UNSUPPORTED_AGENT_CAPABILITIES,
  buildReferencePrompt,
  buildResultReference,
  decideReference,
  referenceIsVisible,
  requestUnsupportedCapability,
  type BuildReferenceInput,
  type DocGraphResultReference,
  type ReferenceDecision,
  type UnsupportedCapability,
} from './agent-bridge.js'

export {
  DOCGRAPH_DEFAULT_TIMEOUT_MS,
  DOCGRAPH_HEALTH_PATH,
  DOCGRAPH_REVIEW_PATH,
  DOCGRAPH_START_PATH,
  DocGraphHttpError,
  createDocGraphClient,
  mapRemoteStatus,
  sanitizeDetail,
  type DocGraphCancelResult,
  type DocGraphClient,
  type DocGraphConfig,
  type DocGraphConnectionDescriptor,
  type DocGraphFetchLike,
  type DocGraphJob,
  type DocGraphJobState,
  type DocGraphSubmitTask,
} from './client.js'
