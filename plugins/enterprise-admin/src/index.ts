import { AuditPage } from './pages/Audit.js'
import { MembersPage } from './pages/Members.js'
import { OrganizationsPage } from './pages/Organizations.js'
import { RolesPage } from './pages/Roles.js'
import { SpacesPage } from './pages/Spaces.js'
import { UsagePage } from './pages/Usage.js'

export const ENTERPRISE_ADMIN_PAGES = Object.freeze([
  OrganizationsPage,
  MembersPage,
  RolesPage,
  SpacesPage,
  AuditPage,
  UsagePage,
])
