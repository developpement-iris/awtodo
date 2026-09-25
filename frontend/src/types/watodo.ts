export type OrganisationRole = "admin" | "chef_de_projet" | "membre";

export interface User {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  teams: string[];
  organisation: string;
  organisation_role: OrganisationRole;
  organisation_role_display: string;
  is_platform_admin: boolean;
  account_type: "interne" | "externe";
  account_type_display: string;
  account_status: "pending" | "active" | "desactive";
  account_status_display: string;
  /** Vide = pas de choix, repli sur l'accent thémé (frontend). */
  planning_color: string;
}

// `User` + préférences strictement personnelles — renvoyé uniquement par
// `/accounts/me/` et les deux endpoints de l'écran Paramètres (jamais nested
// ailleurs, voir `MeSerializer` côté backend : pas la peine de le savoir
// pour un autre utilisateur).
export interface Me extends User {
  email_notifications_enabled: boolean;
  /** Synchronisation Outlook, sens unique Awtodo → Outlook (session du
   * 2026-09-22/23) — câblée réellement (événements, participants,
   * créneaux, occurrences uniques). */
  outlook_calendar_sync_enabled: boolean;
  /** Couleur d'accent de l'interface, par utilisateur (session du
   * 2026-09-23, écran Réglages) — vide = habillage Awtodo par défaut. */
  accent_color: string;
}

// Connexion par mot de passe — voir docs/organisation-et-comptes.md >
// "Comptes et invitations" > authentification, session du 2026-08-06.
// `user` est en réalité un `Me` (LoginView renvoie `MeSerializer(user).data`,
// même chose que `GET /accounts/me/`) — typé comme tel depuis la session du
// 2026-09-23 pour que `CurrentUserContext.currentUser` porte `accent_color`
// sans caster.
export interface LoginResponse {
  access: string;
  refresh: string;
  user: Me;
}

export interface Invitation {
  id: string;
  email: string;
  user: User;
  organisation: string;
  organisation_name: string;
  team: string | null;
  project: string | null;
  invited_by: User;
  token: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  status_display: string;
  created_at: string;
  accepted_at: string | null;
}

export interface PasswordResetToken {
  id: string;
  status: "pending" | "used" | "expired";
  status_display: string;
  is_expired: boolean;
}

export interface Organisation {
  id: string;
  name: string;
  created_at: string;
}

export type TeamMembershipRole = "membre" | "administrateur";

export interface TeamMembership {
  id: string;
  user: User;
  role: TeamMembershipRole;
  role_display: string;
}

export interface Team {
  id: string;
  name: string;
  description: string;
  organisation: string;
  created_by: string | null;
  // Liste plate — utilisée pour peupler des sélecteurs ailleurs (création de
  // projet, admin d'un projet). Pour le rôle par membre, voir `memberships`.
  members: User[];
  memberships: TeamMembership[];
  // Créateur du groupe, admin d'organisation/de plateforme, OU un membre
  // promu `role="administrateur"` sur CE groupe (session du 2026-09-16) —
  // voir docs/organisation-et-comptes.md > "Groupes" > administration.
  can_manage: boolean;
}

export type ProjectRole = "chef_de_projet" | "membre" | "lecteur";

export interface ProjectMembership {
  id: string;
  user: User;
  role: ProjectRole;
  role_display: string;
}

// Voir CLAUDE.md > "Permissions API — flags calculés" : une seule source de
// vérité pour ces règles (apps/*/services.py côté backend) — le frontend ne
// recalcule jamais lui-même une condition de rôle/statut, il lit ces flags.
export interface ProjectPermissions {
  // `false` pour un membre `lecteur` — le frontend s'en sert pour masquer les
  // onglets Budget/Incidents/Planning/Statistiques et toutes les affordances
  // de création/édition.
  can_contribute: boolean;
  can_edit_spec: boolean;
  can_edit_notepad: boolean;
  can_manage_members: boolean;
  can_convert_to_collaborative: boolean;
  can_close: boolean;
  can_reopen: boolean;
  can_create_version: boolean;
  can_manage_budget: boolean;
  can_edit_documentation: boolean;
  can_manage_project_planning: boolean;
  can_manage_project_communication: boolean;
  can_send_project_communication: boolean;
}

// --- Communication de projet (onglet hub) --------------------------------
// Voir docs/modeles-et-api.md > "Module Communication". Câblage d'envoi
// (Microsoft Graph / Power Automate) reporté au déploiement AWS.

export interface O365Connection {
  tenant_id: string;
  client_id: string;
  has_client_secret: boolean;
  sender_mailbox: string;
  is_enabled: boolean;
  is_configured: boolean;
}

// Clé API machine-à-machine (session du 2026-09-25, voir apps.integrations)
// — la valeur en clair (`key`) n'existe que sur la réponse de génération,
// jamais dans un listing.
export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export type CommunicationChannelType = "email" | "teams";

export interface CommunicationChannel {
  id: string;
  channel_type: CommunicationChannelType;
  channel_type_display: string;
  label: string;
  email: string;
  teams_webhook_url: string;
  notify_incident_created: boolean;
  status: "active" | "archived";
}

export interface CommunicationMessage {
  id: string;
  subject: string;
  body: string;
  trigger: "manuel" | "incident_cree";
  trigger_display: string;
  status: "en_attente" | "envoye" | "echec";
  status_display: string;
  created_by: User | null;
  channels: CommunicationChannel[];
  incident: string | null;
  created_at: string;
  sent_at: string | null;
}

// --- Documentation de projet (onglet hub + page publique) -----------------
// Voir docs/modeles-et-api.md > "Documentation de projet".

export type DocStatus = "brouillon" | "publie" | "archive";
export type DocEntryKind = "fonctionnalite" | "resolution";

export interface DocPage {
  id: string;
  parent_id: string | null;
  title: string;
  slug: string;
  content: string;
  order: number;
  status: DocStatus;
  status_display: string;
  created_at: string;
  updated_at: string;
  children: DocPage[];
}

// "contributeurs" : fiche unique auto-générée (session du 2026-09-23), pas
// une file "à documenter" comme les deux autres — voir DocumentationTab.
export type DocEntryFullKind = DocEntryKind | "contributeurs";

export interface DocEntry {
  id: string;
  kind: DocEntryFullKind;
  title: string;
  description: string;
  order: number;
  source: string;
  source_task_id: string | null;
  source_incident_id: string | null;
  version_id: string | null;
  version_label: string | null;
  status: DocStatus;
  status_display: string;
  created_at: string;
  updated_at: string;
}

export interface PendingDocEntry {
  id: string;
  kind: DocEntryKind;
  source_label: string;
  source_title: string;
  created_at: string;
}

export interface DocSpace {
  id: string;
  is_public: boolean;
  public_token: string | null;
  public_url: string | null;
  custom_slug: string;
  accent_color: string;
  header_content: string;
  footer_content: string;
}

export interface DocumentationBundle {
  space: DocSpace;
  pages: DocPage[];
  features: DocEntry[];
  resolutions: DocEntry[];
  contributors: DocEntry[];
  pending_features: PendingDocEntry[];
  pending_resolutions: PendingDocEntry[];
}

export interface PublicDocsNode {
  id: string;
  title: string;
  slug: string;
  content: string;
  children: PublicDocsNode[];
}

export interface PublicDocsEntry {
  id: string;
  title: string;
  description: string;
  created_at: string;
  version_label: string | null;
}

export interface PublicDocs {
  project_name: string;
  pages: PublicDocsNode[];
  features: PublicDocsEntry[];
  resolutions: PublicDocsEntry[];
  contributors: PublicDocsEntry[];
  accent_color: string;
  header_content: string;
  footer_content: string;
}

export type ProjectStatus = "actif" | "cloture";

export interface Project {
  id: string;
  name: string;
  description: string;
  project_type: "individuel" | "collaboratif";
  project_type_display: string;
  status: ProjectStatus;
  status_display: string;
  deadline: string | null;
  already_in_production: boolean;
  priority: "basse" | "moyenne" | "haute" | "critique" | null;
  priority_display: string | null;
  team: string | null;
  team_name: string | null;
  tasks_total: number;
  tasks_done: number;
  notepad_content: string;
  notepad_updated_at: string | null;
  members: ProjectMembership[];
  permissions: ProjectPermissions;
  current_version_id: string | null;
}

// Cahier des charges — voir docs/modeles-et-api.md > "Projets — Hub complet"
// > "Cahier des charges" : 12 sous-sections fixes, `is_active` = cochée dans
// le sommaire, toujours renvoyées même si jamais éditées (content: "").
export type SpecSectionKey =
  | "contexte"
  | "objectifs"
  | "besoin"
  | "perimetre"
  | "exigences_fonctionnelles"
  | "exigences_techniques"
  | "contraintes"
  | "livrables"
  | "planning"
  | "budget"
  | "organisation"
  | "annexes";

export interface SpecSection {
  section_key: SpecSectionKey;
  label: string;
  is_active: boolean;
  content: string;
  updated_at: string | null;
}

// Voir docs/modeles-et-api.md > "ProjectVersion".
export interface ProjectVersion {
  id: string;
  project: string;
  label: string;
  is_current: boolean;
  created_at: string;
  created_by: User | null;
}

export interface TaskPermissions {
  can_rename: boolean;
  can_edit_description: boolean;
  can_edit_deadline: boolean;
  can_comment: boolean;
  can_validate: boolean;
  can_reject: boolean;
  can_cancel: boolean;
  can_claim: boolean;
  can_assign: boolean;
  can_start: boolean;
  can_complete: boolean;
}

export interface Task {
  id: string;
  project: string;
  version: string;
  version_label: string;
  title: string;
  description: string;
  task_type: "correction" | "ajout" | "evolution" | "test";
  task_type_display: string;
  priority: "basse" | "moyenne" | "haute" | "critique";
  priority_display: string;
  deadline: string | null;
  assignee: User | null;
  time_spent: string | null;
  estimated_hours: string | null;
  origin: "manuelle" | "api";
  external_reference_id: string | null;
  status: "en_attente_validation" | "disponible" | "assignee" | "en_cours" | "rejetee" | "archivee" | "annulee";
  status_display: string;
  rejection_reason: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
  permissions: TaskPermissions;
}

export interface TaskComment {
  id: string;
  author: User;
  content: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  actor: User;
  field_name: string;
  old_value: string;
  new_value: string;
  created_at: string;
}

export interface TaskDetail extends Task {
  comments: TaskComment[];
  audit_log: AuditLogEntry[];
}

export interface IncidentPermissions {
  can_start: boolean;
  can_resolve: boolean;
  can_archive: boolean;
  can_cancel: boolean;
  can_comment: boolean;
  can_assign_project: boolean;
  can_edit_description: boolean;
}

export interface Incident {
  id: string;
  project: string | null;
  team: string | null;
  team_name: string | null;
  title: string;
  description: string;
  priority: "basse" | "moyenne" | "haute" | "critique";
  priority_display: string;
  status: "signale" | "en_cours" | "resolu" | "archive" | "annule";
  status_display: string;
  external_reference_id: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  /** Auteur du signalement transmis par l'outil de ticketing (vide sinon). */
  author_name: string;
  author_email: string;
  /** Renseignés à la résolution (pop-up), vides tant que l'incident n'est
   * pas passé par "resolu" — même patron que `Task.time_spent`. */
  resolution_comment: string;
  cancellation_reason: string;
  time_spent: string | null;
  created_at: string;
  permissions: IncidentPermissions;
}

export interface IncidentComment {
  id: string;
  author: User;
  content: string;
  created_at: string;
}

export interface IncidentDetail extends Incident {
  comments: IncidentComment[];
  audit_log: AuditLogEntry[];
}

// Voir docs/modeles-et-api.md > "Statistiques".
export interface ProjectUserStats {
  user: User;
  tasks_done: number;
  tasks_in_progress: number;
  hours_spent: string;
}

export interface CompletionTrendPoint {
  week_start: string;
  count: number;
}

// Widgets étendus (délais/heures/échéances/personnes sollicitées/tendance
// hebdomadaire) — sortie de `apps.tasks.services._task_insights`, partagée
// par l'onglet projet (`TaskInsights`) et l'écran global (`GlobalTaskStats`,
// qui l'étend).
export interface TaskInsights {
  hours_total: string;
  estimated_hours_total: string;
  avg_lead_time_days: number | null;
  tasks_on_time: number;
  tasks_late: number;
  tasks_over_estimate: number;
  tasks_under_estimate: number;
  contributors_count: number;
  priority_breakdown: Record<string, number>;
  completion_trend: CompletionTrendPoint[];
}

export interface GlobalTaskStats extends TaskInsights {
  projects_total: number;
  projects_active: number;
  projects_closed: number;
  tasks_done: number;
  tasks_in_progress: number;
}

// Voir docs/modeles-et-api.md > "Budgétisation".
export type BudgetCategory = "opex" | "capex";

export interface BudgetLine {
  id: string;
  project: string;
  category: BudgetCategory;
  category_display: string;
  label: string;
  quantity: number;
  unit_price: string;
  amount: string;
  created_at: string;
  created_by: User | null;
}

export interface BudgetSummaryRow {
  project_id: string;
  project_name: string;
  opex_total: string;
  capex_total: string;
}

export interface Notification {
  id: string;
  verb: "task_assigned" | "task_commented" | "incident_commented" | "event_invited";
  message: string;
  task: string | null;
  incident: string | null;
  event: string | null;
  is_read: boolean;
  created_at: string;
}

// --- Planning / calendrier -----------------------------------------------
// Voir docs/modeles-et-api.md > "Module Planning".

export interface CalendarUser {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
}

export interface EventParticipant {
  id: string;
  user: CalendarUser;
  response: "invite" | "accepte" | "refuse";
  response_display: string;
}

export interface CalendarEventPermissions {
  can_edit: boolean;
  can_manage_participants: boolean;
}

/** Occurrence concrète d'un événement (une série récurrente en produit
 * plusieurs sur une fenêtre donnée). */
export interface CalendarEventOccurrence {
  type: "event";
  id: string;
  occurrence_start: string;
  start: string;
  end: string;
  all_day: boolean;
  title: string;
  description: string;
  location: string;
  status: "confirme" | "annule";
  recurrence_rule: string;
  is_recurring: boolean;
  /** Cette occurrence précise a été modifiée individuellement (session du
   * 2026-09-23, RECURRENCE-ID) — distinct de `is_recurring`, qui reste vrai
   * pour toutes les occurrences de la série. */
  is_overridden: boolean;
  owner: CalendarUser;
  is_owner: boolean;
  read_only: boolean;
  participants: EventParticipant[];
  my_response: "invite" | "accepte" | "refuse" | null;
  permissions: CalendarEventPermissions;
}

export interface CalendarEventDetail {
  id: string;
  title: string;
  description: string;
  location: string;
  start: string;
  end: string;
  all_day: boolean;
  recurrence_rule: string;
  is_recurring: boolean;
  status: "confirme" | "annule";
  status_display: string;
  owner: CalendarUser;
  is_owner: boolean;
  participants: EventParticipant[];
  permissions: CalendarEventPermissions;
  audit_log: {
    field_name: string;
    old_value: string;
    new_value: string;
    actor: CalendarUser | null;
    created_at: string;
  }[];
}

export interface ScheduledBlock {
  type: "block";
  id: string;
  start: string;
  end: string;
  status: "planifie" | "annule";
  title: string;
  task: {
    id: string;
    title: string;
    status: string;
    status_display: string;
    priority: string;
    project_id: string;
    project_name: string;
  } | null;
  incident: {
    id: string;
    title: string;
    status: string;
    status_display: string;
    priority: string;
    project_id: string | null;
  } | null;
}

export type ProjectPlanningKind = "jalon" | "phase" | "reunion" | "autre";

export interface ProjectPlanningOccurrence {
  type: "project_entry";
  id: string;
  occurrence_start: string;
  start: string;
  end: string;
  all_day: boolean;
  title: string;
  description: string;
  kind: ProjectPlanningKind;
  kind_display: string;
  status: "confirme" | "annule";
  project_id: string;
  project_name: string;
  assignee: CalendarUser | null;
  recurrence_rule: string;
  is_recurring: boolean;
  permissions: { can_manage: boolean };
}

export interface CalendarBundle {
  window_start: string;
  window_end: string;
  events: CalendarEventOccurrence[];
  blocks: ScheduledBlock[];
  project_entries: ProjectPlanningOccurrence[];
  shared: {
    owner: CalendarUser;
    share_id: string;
    occurrences: CalendarEventOccurrence[];
    blocks: ScheduledBlock[];
  }[];
}

export interface ProjectPlanningBundle {
  can_manage: boolean;
  entries: ProjectPlanningOccurrence[];
}

export interface CalendarShare {
  id: string;
  owner: CalendarUser;
  grantee: CalendarUser;
  /** Droit additionnel, optionnel : le bénéficiaire peut modifier les
   * horaires de travail du propriétaire (voir docs/organisation-et-comptes.md
   * > "Personnalisation du planning" > délégation). */
  can_manage_work_hours: boolean;
  created_at: string;
}

export interface CalendarShareList {
  granted: CalendarShare[];
  received: CalendarShare[];
}

// Horaires de travail — session du 2026-09-18. Modèle hebdomadaire récurrent
// (7 jours) + exceptions ponctuelles par semaine calendaire. Voir
// docs/organisation-et-comptes.md > "Personnalisation du planning".
export interface WorkingHoursDay {
  weekday: number; // 0 = lundi .. 6 = dimanche
  weekday_display: string;
  enabled: boolean;
  /** Format "HH:MM". */
  start: string;
  end: string;
}

export interface WorkingHoursSchedule {
  is_override: boolean;
  /** Lundi de la semaine visée, "YYYY-MM-DD" — présent seulement si demandé. */
  week_start: string | null;
  days: WorkingHoursDay[];
}
