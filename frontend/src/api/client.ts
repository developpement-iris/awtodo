import type {
  BudgetCategory,
  BudgetLine,
  BudgetSummaryRow,
  CalendarBundle,
  CalendarEventDetail,
  CalendarShare,
  CalendarShareList,
  CommunicationChannel,
  CommunicationChannelType,
  CommunicationMessage,
  O365Connection,
  ProjectPlanningBundle,
  ProjectPlanningOccurrence,
  ScheduledBlock,
  DocEntry,
  DocEntryKind,
  DocPage,
  DocSpace,
  DocumentationBundle,
  GlobalTaskStats,
  Incident,
  IncidentComment,
  IncidentDetail,
  Invitation,
  LoginResponse,
  Notification,
  Organisation,
  PasswordResetToken,
  Project,
  ProjectMembership,
  ProjectUserStats,
  ProjectVersion,
  PublicDocs,
  SpecSection,
  Task,
  TaskComment,
  TaskDetail,
  TaskInsights,
  Team,
  User,
} from "../types/watodo";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// Identifiant de l'utilisateur factice courant (voir CLAUDE.md — mécanisme
// d'identification temporaire dev uniquement), tenu à jour par CurrentUserContext.
let debugUserId: string | null = null;

export function setDebugUserId(id: string | null) {
  debugUserId = id;
}

// Token d'accès JWT de la connexion réelle (voir docs/organisation-et-comptes.md
// > "Comptes et invitations" > authentification, session du 2026-08-06) —
// prioritaire sur le header debug quand présent, mutuellement exclusifs
// (tenu à jour par CurrentUserContext).
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

function authHeaders(): Record<string, string> {
  if (accessToken) return { Authorization: `Bearer ${accessToken}` };
  return debugUserId ? { "X-Debug-User-Id": debugUserId } : {};
}

// Rend lisible un corps d'erreur DRF : soit `{detail: "..."}`, soit un
// dictionnaire d'erreurs par champ (`{password: ["..."]}`) que
// `serializer.is_valid(raise_exception=True)` renvoie — jusqu'ici masqué
// derrière le message générique "(400)".
function errorMessage(payload: unknown, path: string, status: number): string {
  const fallback = `Échec de la requête ${path} (${status})`;
  if (!payload || typeof payload !== "object") return fallback;
  const record = payload as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  const parts: string[] = [];
  for (const value of Object.values(record)) {
    if (typeof value === "string") parts.push(value);
    else if (Array.isArray(value)) parts.push(...value.filter((v): v is string => typeof v === "string"));
  }
  return parts.length > 0 ? parts.join(" ") : fallback;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  if (!response.ok) {
    throw new Error(`Échec de la requête ${path} (${response.status})`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(errorMessage(payload, path, response.status));
  }
  // Certaines actions (cancel/revoke/ignore…) renvoient 204 sans corps —
  // `.json()` sur une réponse vide lève "Unexpected end of JSON input".
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function patchJson<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(errorMessage(payload, path, response.status));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function putJson<T>(path: string, body: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(errorMessage(payload, path, response.status));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// DELETE : certains endpoints renvoient un corps (fiche archivée, espace mis
// à jour), d'autres un 204 vide — `T` peut donc être `void`.
async function deleteJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(errorMessage(payload, path, response.status));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// Lecture publique de la documentation : jamais d'en-tête d'authentification
// (l'endpoint est `AllowAny`, et l'appelant peut n'avoir aucune session).
async function getPublicJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Échec de la requête ${path} (${response.status})`);
  }
  return response.json() as Promise<T>;
}

interface ProjectFilters {
  status?: string[];
  [key: string]: string | string[] | undefined;
}

export function getProjects(filters: ProjectFilters = {}): Promise<Project[]> {
  return getJson<Project[]>(`/projects/${buildQuery(filters)}`);
}

export interface ProjectCreatePayload {
  name: string;
  project_type: Project["project_type"];
  description?: string;
  deadline?: string;
  already_in_production?: boolean;
  priority?: Exclude<Project["priority"], null>;
  team?: string;
  member_ids?: string[];
  [key: string]: unknown;
}

export function createProject(payload: ProjectCreatePayload): Promise<Project> {
  return postJson<Project>("/projects/", payload);
}

export function getProject(projectId: string): Promise<Project> {
  return getJson<Project>(`/projects/${projectId}/`);
}

export interface ProjectNotepadUpdatePayload {
  notepad_content: string;
  [key: string]: unknown;
}

export function updateProjectNotepad(projectId: string, payload: ProjectNotepadUpdatePayload): Promise<Project> {
  return patchJson<Project>(`/projects/${projectId}/`, payload);
}

// Cahier des charges structuré en sous-sections — voir
// docs/modeles-et-api.md > "Projets — Hub complet" > "Cahier des charges".
export function getSpecSections(projectId: string): Promise<SpecSection[]> {
  return getJson<SpecSection[]>(`/projects/${projectId}/spec-sections/`);
}

export interface SpecSectionUpdatePayload {
  is_active?: boolean;
  content?: string;
  [key: string]: unknown;
}

export function updateSpecSection(
  projectId: string,
  sectionKey: string,
  payload: SpecSectionUpdatePayload,
): Promise<SpecSection> {
  return patchJson<SpecSection>(`/projects/${projectId}/spec-sections/${sectionKey}/`, payload);
}

export interface ProjectMemberAddPayload {
  user?: string;
  email?: string;
  role?: ProjectMembership["role"];
  [key: string]: unknown;
}

export function addProjectMember(projectId: string, payload: ProjectMemberAddPayload): Promise<Project> {
  return postJson<Project>(`/projects/${projectId}/members/`, payload);
}

// Ouvre un projet individuel (lecteurs uniquement, voir ProjectPermissions
// > can_convert_to_collaborative) à d'autres rôles en le faisant passer en
// collaboratif — nécessite un groupe de rattachement, sens inverse non
// proposé (voir apps.projects.services.convert_to_collaborative).
export function convertProjectToCollaborative(projectId: string, teamId: string): Promise<Project> {
  return postJson<Project>(`/projects/${projectId}/convert-to-collaborative/`, { team: teamId });
}

export function changeProjectMemberRole(
  projectId: string,
  membershipId: string,
  role: ProjectMembership["role"],
): Promise<Project> {
  return postJson<Project>(`/projects/${projectId}/members/role/`, { membership: membershipId, role });
}

export function removeProjectMember(projectId: string, membershipId: string): Promise<Project> {
  return postJson<Project>(`/projects/${projectId}/members/remove/`, { membership: membershipId });
}

export interface ProjectInviteExternalPayload {
  email: string;
  first_name?: string;
  last_name?: string;
  [key: string]: unknown;
}

export function inviteProjectExternalMember(projectId: string, payload: ProjectInviteExternalPayload): Promise<Project> {
  return postJson<Project>(`/projects/${projectId}/members/invite/`, payload);
}

export function getTeams(): Promise<Team[]> {
  return getJson<Team[]>("/accounts/teams/");
}

export function createTeam(name: string, description?: string): Promise<Team> {
  return postJson<Team>("/accounts/teams/", description ? { name, description } : { name });
}

export function addTeamMember(teamId: string, userId: string): Promise<Team> {
  return postJson<Team>(`/accounts/teams/${teamId}/members/`, { user: userId });
}

export function removeTeamMember(teamId: string, userId: string): Promise<Team> {
  return postJson<Team>(`/accounts/teams/${teamId}/members/remove/`, { user: userId });
}

export function renameTeam(teamId: string, name: string): Promise<Team> {
  return patchJson<Team>(`/accounts/teams/${teamId}/rename/`, { name });
}

export function setOrganisationRole(userId: string, role: User["organisation_role"]): Promise<User> {
  return patchJson<User>(`/accounts/users/${userId}/organisation-role/`, { organisation_role: role });
}

export function getOrganisations(): Promise<Organisation[]> {
  return getJson<Organisation[]>("/accounts/organisations/");
}

export interface OrganisationCreatePayload {
  organisation_name: string;
  admin_name: string;
  admin_email: string;
  [key: string]: unknown;
}

export function createOrganisation(payload: OrganisationCreatePayload): Promise<Organisation & { admin: User }> {
  return postJson<Organisation & { admin: User }>("/accounts/organisations/", payload);
}

export function getInvitations(): Promise<Invitation[]> {
  return getJson<Invitation[]>("/accounts/invitations/");
}

export interface InvitationCreatePayload {
  email: string;
  first_name?: string;
  last_name?: string;
  team?: string;
  [key: string]: unknown;
}

export function createInvitation(payload: InvitationCreatePayload): Promise<Invitation> {
  return postJson<Invitation>("/accounts/invitations/", payload);
}

export function resendInvitation(token: string): Promise<Invitation> {
  return postJson<Invitation>(`/accounts/invitations/${token}/resend/`, {});
}

export function getInvitationByToken(token: string): Promise<Invitation> {
  return getJson<Invitation>(`/accounts/invitations/${token}/`);
}

export function acceptInvitation(token: string, password: string): Promise<Invitation> {
  return postJson<Invitation>(`/accounts/invitations/${token}/accept/`, { password });
}

// Réinitialisation de mot de passe — voir docs/organisation-et-comptes.md >
// "Réinitialisation de mot de passe". En mode "email" (cible), la réponse
// est un message générique (pas d'énumération de comptes). En mode "lien
// direct" (phase de test, `PASSWORD_RESET_DIRECT_LINK` côté backend), la
// réponse inclut `reset_path` si un compte correspond — le frontend y
// redirige directement — ou renvoie un 404 sinon.
export function requestPasswordReset(identifier: string): Promise<{ detail: string; reset_path?: string }> {
  return postJson<{ detail: string; reset_path?: string }>("/accounts/password-reset/request/", { identifier });
}

export function getPasswordResetToken(token: string): Promise<PasswordResetToken> {
  return getJson<PasswordResetToken>(`/accounts/password-reset/${token}/`);
}

export function confirmPasswordReset(token: string, password: string): Promise<{ detail: string }> {
  return postJson<{ detail: string }>(`/accounts/password-reset/${token}/confirm/`, { password });
}

// Authentification par mot de passe — voir docs/organisation-et-comptes.md >
// "Comptes et invitations" > authentification, session du 2026-08-06.
export function login(username: string, password: string): Promise<LoginResponse> {
  return postJson<LoginResponse>("/accounts/login/", { username, password });
}

export function getMe(): Promise<User> {
  return getJson<User>("/accounts/me/");
}

interface TaskFilters {
  project?: string;
  assignee?: string;
  team?: string;
  version?: string;
  status?: string[];
  [key: string]: string | string[] | undefined;
}

// Certains filtres (le statut, voir "Filtre d'état généralisé") acceptent
// plusieurs valeurs — un tableau devient autant de paramètres répétés
// (`?status=a&status=b`), ce que `MultipleChoiceFilter` côté DRF attend.
function buildQuery(filters: Record<string, string | string[] | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item) params.append(key, item);
      }
    } else if (value) {
      params.set(key, value);
    }
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getTasks(filters: TaskFilters = {}): Promise<Task[]> {
  return getJson<Task[]>(`/tasks/${buildQuery(filters)}`);
}

interface IncidentFilters {
  project?: string;
  status?: string[];
  [key: string]: string | string[] | undefined;
}

export function getIncidents(filters: IncidentFilters = {}): Promise<Incident[]> {
  return getJson<Incident[]>(`/incidents/${buildQuery(filters)}`);
}

interface IncidentInboxFilters {
  status?: string[];
  [key: string]: string | string[] | undefined;
}

export function getIncidentsInbox(filters: IncidentInboxFilters = {}): Promise<Incident[]> {
  return getJson<Incident[]>(`/incidents/inbox/${buildQuery(filters)}`);
}

export function assignIncidentProject(incidentId: string, projectId: string): Promise<Incident> {
  return postJson<Incident>(`/incidents/${incidentId}/assign-project/`, { project: projectId });
}

export interface IncidentCreatePayload {
  project: string;
  title: string;
  description?: string;
  priority?: Incident["priority"];
  external_reference_id?: string;
  [key: string]: unknown;
}

export function createIncident(payload: IncidentCreatePayload): Promise<Incident> {
  return postJson<Incident>("/incidents/", payload);
}

export function startIncident(incidentId: string): Promise<Incident> {
  return postJson<Incident>(`/incidents/${incidentId}/start/`, {});
}

export function resolveIncident(incidentId: string): Promise<Incident> {
  return postJson<Incident>(`/incidents/${incidentId}/resolve/`, {});
}

export function archiveIncident(incidentId: string): Promise<Incident> {
  return postJson<Incident>(`/incidents/${incidentId}/archive/`, {});
}

export function getIncident(incidentId: string): Promise<IncidentDetail> {
  return getJson<IncidentDetail>(`/incidents/${incidentId}/`);
}

export function addIncidentComment(incidentId: string, content: string): Promise<IncidentComment> {
  return postJson<IncidentComment>(`/incidents/${incidentId}/comments/`, { content });
}

export function updateIncidentDescription(incidentId: string, description: string): Promise<Incident> {
  return postJson<Incident>(`/incidents/${incidentId}/update-description/`, { description });
}

export function getUsers(): Promise<User[]> {
  return getJson<User[]>("/accounts/users/");
}

export interface TaskCreatePayload {
  project: string;
  title: string;
  task_type: Task["task_type"];
  description?: string;
  priority?: Task["priority"];
  deadline?: string;
  external_reference_id?: string;
  assignee?: string;
  estimated_hours?: string;
  [key: string]: unknown;
}

export function createTask(payload: TaskCreatePayload): Promise<Task> {
  return postJson<Task>("/tasks/", payload);
}

export function validateTask(taskId: string, assignee?: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/validate/`, assignee ? { assignee } : {});
}

export function rejectTask(taskId: string, rejectionReason: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/reject/`, { rejection_reason: rejectionReason });
}

export function claimTask(taskId: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/claim/`, {});
}

export function assignTask(taskId: string, assignee: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/assign/`, { assignee });
}

export function startTask(taskId: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/start/`, {});
}

export function completeTask(taskId: string, timeSpent: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/complete/`, { time_spent: timeSpent });
}

export function renameTask(taskId: string, title: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/rename/`, { title });
}

export function getTask(taskId: string): Promise<TaskDetail> {
  return getJson<TaskDetail>(`/tasks/${taskId}/`);
}

export function addTaskComment(taskId: string, content: string): Promise<TaskComment> {
  return postJson<TaskComment>(`/tasks/${taskId}/comments/`, { content });
}

export function updateTaskDescription(taskId: string, description: string): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/update-description/`, { description });
}

export function updateTaskEstimatedHours(taskId: string, estimatedHours: string | null): Promise<Task> {
  return postJson<Task>(`/tasks/${taskId}/update-estimated-hours/`, { estimated_hours: estimatedHours });
}

// Fiche utilisateur (écran Administration > Membres) — voir
// docs/organisation-et-comptes.md. Réservé à `organisation_role=admin`.
export function getUserAssignedTasks(userId: string): Promise<Task[]> {
  return getJson<Task[]>(`/tasks/assigned-to/${userId}/`);
}

export function closeProject(projectId: string): Promise<Project> {
  return postJson<Project>(`/projects/${projectId}/close/`, {});
}

export function reopenProject(projectId: string): Promise<Project> {
  return postJson<Project>(`/projects/${projectId}/reopen/`, {});
}

export function getProjectVersions(projectId: string): Promise<ProjectVersion[]> {
  return getJson<ProjectVersion[]>(`/projects/${projectId}/versions/`);
}

export function createProjectVersion(projectId: string, label: string): Promise<ProjectVersion> {
  return postJson<ProjectVersion>(`/projects/${projectId}/versions/`, { label });
}

// Onglet Statistiques (projet + global) — voir docs/modeles-et-api.md.
export function getProjectStats(projectId: string): Promise<ProjectUserStats[]> {
  return getJson<ProjectUserStats[]>(`/tasks/project-stats/${projectId}/`);
}

export function getProjectTaskInsights(projectId: string): Promise<TaskInsights> {
  return getJson<TaskInsights>(`/tasks/project-insights/${projectId}/`);
}

export function getGlobalTaskStats(): Promise<GlobalTaskStats> {
  return getJson<GlobalTaskStats>("/tasks/global-stats/");
}

// Onglet Budgétisation — voir docs/modeles-et-api.md.
export function getBudgetLines(projectId: string): Promise<BudgetLine[]> {
  return getJson<BudgetLine[]>(`/budgeting/projects/${projectId}/lines/`);
}

export interface BudgetLineCreatePayload {
  category: BudgetCategory;
  label: string;
  quantity: number;
  unit_price: string;
  [key: string]: unknown;
}

export function addBudgetLine(projectId: string, payload: BudgetLineCreatePayload): Promise<BudgetLine> {
  return postJson<BudgetLine>(`/budgeting/projects/${projectId}/lines/`, payload);
}

export function removeBudgetLine(lineId: string): Promise<BudgetLine> {
  return postJson<BudgetLine>(`/budgeting/${lineId}/remove/`, {});
}

export function getBudgetSummary(): Promise<BudgetSummaryRow[]> {
  return getJson<BudgetSummaryRow[]>("/budgeting/summary/");
}

// --- Documentation de projet ---------------------------------------------

export function getDocumentation(projectId: string): Promise<DocumentationBundle> {
  return getJson<DocumentationBundle>(`/docs/${projectId}/`);
}

export function createDocPage(
  projectId: string,
  payload: { title: string; parent_id?: string | null; content?: string },
): Promise<DocPage> {
  return postJson<DocPage>(`/docs/${projectId}/pages/`, payload);
}

export function updateDocPage(
  projectId: string,
  pageId: string,
  payload: { title?: string; content?: string; parent_id?: string | null; order?: number },
): Promise<DocPage> {
  return patchJson<DocPage>(`/docs/${projectId}/pages/${pageId}/`, payload);
}

export function publishDocPage(projectId: string, pageId: string): Promise<DocPage> {
  return postJson<DocPage>(`/docs/${projectId}/pages/${pageId}/publish/`);
}

export function unpublishDocPage(projectId: string, pageId: string): Promise<DocPage> {
  return postJson<DocPage>(`/docs/${projectId}/pages/${pageId}/unpublish/`);
}

export function archiveDocPage(projectId: string, pageId: string): Promise<void> {
  return deleteJson<void>(`/docs/${projectId}/pages/${pageId}/`);
}

export function createDocEntry(
  projectId: string,
  payload: { kind: DocEntryKind; title: string; description?: string },
): Promise<DocEntry> {
  return postJson<DocEntry>(`/docs/${projectId}/entries/`, payload);
}

export function updateDocEntry(
  projectId: string,
  entryId: string,
  payload: { title?: string; description?: string; order?: number },
): Promise<DocEntry> {
  return patchJson<DocEntry>(`/docs/${projectId}/entries/${entryId}/`, payload);
}

export function publishDocEntry(projectId: string, entryId: string): Promise<DocEntry> {
  return postJson<DocEntry>(`/docs/${projectId}/entries/${entryId}/publish/`);
}

export function unpublishDocEntry(projectId: string, entryId: string): Promise<DocEntry> {
  return postJson<DocEntry>(`/docs/${projectId}/entries/${entryId}/unpublish/`);
}

export function archiveDocEntry(projectId: string, entryId: string): Promise<DocEntry> {
  return deleteJson<DocEntry>(`/docs/${projectId}/entries/${entryId}/`);
}

export function seedFeaturesFromSpec(projectId: string): Promise<{ created: DocEntry[] }> {
  return postJson<{ created: DocEntry[] }>(`/docs/${projectId}/seed-from-spec/`);
}

export function createEntryFromPending(projectId: string, pendingId: string): Promise<DocEntry> {
  return postJson<DocEntry>(`/docs/${projectId}/pending/${pendingId}/create-entry/`);
}

export function ignorePendingDocEntry(projectId: string, pendingId: string): Promise<void> {
  return postJson<void>(`/docs/${projectId}/pending/${pendingId}/ignore/`);
}

export function enablePublicDocLink(projectId: string): Promise<{ space: DocSpace }> {
  return postJson<{ space: DocSpace }>(`/docs/${projectId}/public-link/`);
}

export function rotatePublicDocLink(projectId: string): Promise<{ space: DocSpace }> {
  return postJson<{ space: DocSpace }>(`/docs/${projectId}/public-link/rotate/`);
}

export function revokePublicDocLink(projectId: string): Promise<{ space: DocSpace }> {
  return deleteJson<{ space: DocSpace }>(`/docs/${projectId}/public-link/`);
}

export function getPublicDocs(token: string): Promise<PublicDocs> {
  return getPublicJson<PublicDocs>(`/docs/public/${token}/`);
}

export function getNotifications(): Promise<Notification[]> {
  return getJson<Notification[]>("/notifications/");
}

export function getUnreadNotificationCount(): Promise<{ count: number }> {
  return getJson<{ count: number }>("/notifications/unread-count/");
}

export function markNotificationRead(notificationId: string): Promise<Notification> {
  return postJson<Notification>(`/notifications/${notificationId}/mark-read/`);
}

export async function markAllNotificationsRead(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/notifications/mark-all-read/`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error(`Échec de la requête /notifications/mark-all-read/ (${response.status})`);
  }
}

// --- Planning / calendrier ---------------------------------------------
// Voir docs/modeles-et-api.md > "Module Planning". Les dates sont des chaînes
// ISO 8601 avec offset (ex. `2026-06-10T09:00:00+02:00`).

export interface CalendarQuery {
  from: string;
  to: string;
  owners?: string[];
  projects?: string[];
}

export function getCalendar(query: CalendarQuery): Promise<CalendarBundle> {
  const params = new URLSearchParams({ from: query.from, to: query.to });
  if (query.owners?.length) params.set("owners", query.owners.join(","));
  if (query.projects?.length) params.set("projects", query.projects.join(","));
  return getJson<CalendarBundle>(`/planning/calendar/?${params.toString()}`);
}

export interface EventPayload {
  title?: string;
  description?: string;
  location?: string;
  start?: string;
  end?: string;
  all_day?: boolean;
  recurrence_rule?: string;
  [key: string]: unknown;
}

export function listEvents(): Promise<CalendarEventDetail[]> {
  return getJson<CalendarEventDetail[]>("/planning/events/");
}

export function getEvent(eventId: string): Promise<CalendarEventDetail> {
  return getJson<CalendarEventDetail>(`/planning/events/${eventId}/`);
}

export function createEvent(payload: EventPayload): Promise<CalendarEventDetail> {
  return postJson<CalendarEventDetail>("/planning/events/", payload);
}

export function updateEvent(eventId: string, payload: EventPayload): Promise<CalendarEventDetail> {
  return patchJson<CalendarEventDetail>(`/planning/events/${eventId}/`, payload);
}

export function cancelEvent(eventId: string): Promise<void> {
  return postJson<void>(`/planning/events/${eventId}/cancel/`, {});
}

export function addEventParticipant(eventId: string, userId: string): Promise<CalendarEventDetail> {
  return postJson<CalendarEventDetail>(`/planning/events/${eventId}/participants/`, { user: userId });
}

export function removeEventParticipant(eventId: string, participantId: string): Promise<void> {
  return deleteJson<void>(`/planning/events/${eventId}/participants/${participantId}/`);
}

export function respondToEvent(eventId: string, response: "accepte" | "refuse"): Promise<CalendarEventDetail> {
  return postJson<CalendarEventDetail>(`/planning/events/${eventId}/respond/`, { response });
}

export interface BlockPayload {
  task?: string | null;
  incident?: string | null;
  start?: string;
  end?: string;
  [key: string]: unknown;
}

export function createBlock(payload: BlockPayload): Promise<ScheduledBlock> {
  return postJson<ScheduledBlock>("/planning/blocks/", payload);
}

export function updateBlock(blockId: string, payload: BlockPayload): Promise<ScheduledBlock> {
  return patchJson<ScheduledBlock>(`/planning/blocks/${blockId}/`, payload);
}

export function cancelBlock(blockId: string): Promise<void> {
  return postJson<void>(`/planning/blocks/${blockId}/cancel/`, {});
}

export interface ProjectEntryPayload {
  title?: string;
  description?: string;
  kind?: string;
  start?: string;
  end?: string;
  all_day?: boolean;
  assignee?: string | null;
  recurrence_rule?: string;
  [key: string]: unknown;
}

export function getProjectPlanningEntries(
  projectId: string,
  range: { from: string; to: string },
): Promise<ProjectPlanningBundle> {
  const params = new URLSearchParams({ from: range.from, to: range.to });
  return getJson<ProjectPlanningBundle>(`/planning/projects/${projectId}/entries/?${params.toString()}`);
}

export function createProjectPlanningEntry(
  projectId: string,
  payload: ProjectEntryPayload,
): Promise<ProjectPlanningOccurrence> {
  return postJson<ProjectPlanningOccurrence>(`/planning/projects/${projectId}/entries/`, payload);
}

export function updateProjectPlanningEntry(
  projectId: string,
  entryId: string,
  payload: ProjectEntryPayload,
): Promise<ProjectPlanningOccurrence> {
  return patchJson<ProjectPlanningOccurrence>(
    `/planning/projects/${projectId}/entries/${entryId}/`,
    payload,
  );
}

export function cancelProjectPlanningEntry(projectId: string, entryId: string): Promise<void> {
  return postJson<void>(`/planning/projects/${projectId}/entries/${entryId}/cancel/`, {});
}

export function listCalendarShares(): Promise<CalendarShareList> {
  return getJson<CalendarShareList>("/planning/shares/");
}

export function createCalendarShare(granteeId: string): Promise<CalendarShare> {
  return postJson<CalendarShare>("/planning/shares/", { grantee: granteeId });
}

export function revokeCalendarShare(shareId: string): Promise<void> {
  return postJson<void>(`/planning/shares/${shareId}/revoke/`, {});
}

// --- Communication de projet ---------------------------------------------
// Voir docs/modeles-et-api.md > "Module Communication".

export function getO365Connection(): Promise<O365Connection> {
  return getJson<O365Connection>("/communication/o365/");
}

export function updateO365Connection(
  payload: Partial<{
    tenant_id: string;
    client_id: string;
    client_secret: string;
    sender_mailbox: string;
    is_enabled: boolean;
  }>,
): Promise<O365Connection> {
  return putJson<O365Connection>("/communication/o365/", payload);
}

export function getProjectCommunicationChannels(projectId: string): Promise<CommunicationChannel[]> {
  return getJson<CommunicationChannel[]>(`/communication/projects/${projectId}/channels/`);
}

export function createProjectCommunicationChannel(
  projectId: string,
  payload: {
    channel_type: CommunicationChannelType;
    label: string;
    email?: string;
    teams_webhook_url?: string;
    notify_incident_created?: boolean;
  },
): Promise<CommunicationChannel> {
  return postJson<CommunicationChannel>(`/communication/projects/${projectId}/channels/`, payload);
}

export function updateProjectCommunicationChannel(
  projectId: string,
  channelId: string,
  payload: Partial<{
    label: string;
    email: string;
    teams_webhook_url: string;
    notify_incident_created: boolean;
  }>,
): Promise<CommunicationChannel> {
  return patchJson<CommunicationChannel>(
    `/communication/projects/${projectId}/channels/${channelId}/`,
    payload,
  );
}

export function archiveProjectCommunicationChannel(
  projectId: string,
  channelId: string,
): Promise<void> {
  return deleteJson<void>(`/communication/projects/${projectId}/channels/${channelId}/`);
}

export function getProjectCommunicationMessages(projectId: string): Promise<CommunicationMessage[]> {
  return getJson<CommunicationMessage[]>(`/communication/projects/${projectId}/messages/`);
}

export function composeProjectCommunicationMessage(
  projectId: string,
  payload: { subject: string; body: string; channel_ids: string[] },
): Promise<CommunicationMessage> {
  return postJson<CommunicationMessage>(`/communication/projects/${projectId}/messages/`, payload);
}
