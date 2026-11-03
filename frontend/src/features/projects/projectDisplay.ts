import type { Project, ProjectMembership } from "../../types/watodo";

const COVER_TONE_COUNT = 6;

/** Teinte d'identité stable par projet (1–6), dérivée de son identifiant :
 * même couverture et même couleur de barre Gantt, sans champ à stocker. */
export function coverTone(projectId: string): number {
  let hash = 0;
  for (const char of projectId) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return (Math.abs(hash) % COVER_TONE_COUNT) + 1;
}

export function projectProgress(project: Project): number {
  return project.tasks_total > 0 ? Math.round((project.tasks_done / project.tasks_total) * 100) : 0;
}

const DATE_FORMAT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });
const SHORT_DATE_FORMAT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

/** `YYYY-MM-DD` lu en date locale (pas en UTC, qui décalerait d'un jour). */
export function parseIsoDate(value: string): Date {
  return new Date(`${value}T12:00:00`);
}

export function formatProjectDate(value: string, short = false): string {
  return (short ? SHORT_DATE_FORMAT : DATE_FORMAT).format(parseIsoDate(value));
}

export function deadlineLabel(project: Project): string {
  if (project.already_in_production) return "En production";
  return project.deadline ? formatProjectDate(project.deadline) : "Sans échéance";
}

export function memberName(membership: ProjectMembership): string {
  return `${membership.user.first_name} ${membership.user.last_name}`.trim() || membership.user.username;
}

export function teamLabel(project: Project): string {
  return project.team_name ?? "Individuel";
}
