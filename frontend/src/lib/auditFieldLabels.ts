// Libellés français pour les noms de champs Django bruts renvoyés par
// `AuditLogEntry.field_name` (voir apps/common/audit.py) — partagé entre
// tâches et incidents, un champ absent du dictionnaire s'affiche tel quel
// (fallback volontaire, pas une erreur).
const AUDIT_FIELD_LABELS: Record<string, string> = {
  title: "Titre",
  description: "Description",
  status: "Statut",
  priority: "Priorité",
  task_type: "Type",
  deadline: "Échéance",
  assignee_id: "Assigné à",
  assigned_to_id: "Assigné à",
  time_spent: "Temps passé",
  rejection_reason: "Motif de rejet",
  cancellation_reason: "Motif d'annulation",
  project_id: "Projet",
  team_id: "Groupe",
  external_reference_id: "Référence externe",
  role: "Rôle",
  name: "Nom",
  category: "Catégorie",
  quantity: "Quantité",
  unit_price: "Prix unitaire",
  resolution_comment: "Commentaire de résolution",
};

export function auditFieldLabel(fieldName: string): string {
  return AUDIT_FIELD_LABELS[fieldName] ?? fieldName;
}

// Libellés pour `AuditLogEntry.verb` (session du 2026-09-29) — voir
// apps/common/audit.py::record_event pour la liste des verbes émis.
const AUDIT_VERB_LABELS: Record<string, string> = {
  field_changed: "Modifié",
  created: "Créé",
  commented: "Commentaire",
  member_added: "Membre ajouté",
  member_removed: "Membre retiré",
  removed: "Retiré",
  sent: "Envoyé",
  archived: "Archivé",
};

export function auditVerbLabel(verb: string): string {
  return AUDIT_VERB_LABELS[verb] ?? verb;
}

// Libellés pour `ProjectHistoryEntry.entity_type` (nom de modèle Django en
// minuscules, ex. "task", "projectmembership") — session du 2026-09-29.
const AUDIT_ENTITY_LABELS: Record<string, string> = {
  task: "Tâche",
  incident: "Incident",
  project: "Projet",
  projectmembership: "Membre du projet",
  projectversion: "Version",
  budgetline: "Ligne de budget",
  communicationchannel: "Canal Teams",
  communicationmessage: "Communication",
  docpage: "Page de documentation",
  docentry: "Fiche de documentation",
  projectplanningentry: "Entrée de planning",
};

export function auditEntityLabel(entityType: string): string {
  return AUDIT_ENTITY_LABELS[entityType] ?? entityType;
}
