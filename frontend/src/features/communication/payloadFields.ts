// Catalogue des champs disponibles pour un gabarit de payload de canal —
// miroir de apps.communication.payload.AVAILABLE_FIELDS (backend, source de
// vérité sur ce qui est réellement résolu). À garder synchronisé.
export const PAYLOAD_FIELD_CATALOG: Record<string, string[]> = {
  message: ["subject", "body", "trigger", "created_at", "sent_at"],
  project: ["name", "id"],
  sender: ["username", "first_name", "last_name", "email", "display_name"],
  channel: ["id", "name", "label"],
  task: ["title", "description", "status", "priority", "type", "deadline", "estimated_hours", "assignee"],
  incident: ["title", "description", "status", "priority", "assigned_to", "author_name", "author_email"],
};

export function placeholderFor(namespace: string, field: string): string {
  return `{{${namespace}.${field}}}`;
}
