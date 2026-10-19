import type { TaskCreatePayload } from "../../api/client";
import type { TaskCreateFormValues } from "./TaskCreateDialog";

// Projet vide = tâche personnelle (session du 2026-10-19) : le backend
// l'assigne d'office au créateur, l'assigné n'est donc jamais envoyé.
export function buildTaskCreatePayload(values: TaskCreateFormValues): TaskCreatePayload {
  const payload: TaskCreatePayload = {
    project: values.project || null,
    title: values.title.trim(),
    task_type: values.task_type,
    priority: values.priority,
  };
  if (values.description.trim()) payload.description = values.description.trim();
  if (values.deadline) payload.deadline = values.deadline;
  if (values.external_reference_id.trim()) payload.external_reference_id = values.external_reference_id.trim();
  if (values.project && values.assignee) payload.assignee = values.assignee;
  if (values.estimated_hours.trim()) payload.estimated_hours = values.estimated_hours.trim();
  return payload;
}
