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
  project_id: "Projet",
  team_id: "Groupe",
  external_reference_id: "Référence externe",
};

export function auditFieldLabel(fieldName: string): string {
  return AUDIT_FIELD_LABELS[fieldName] ?? fieldName;
}
