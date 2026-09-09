import type {
  CalendarEventOccurrence,
  ProjectPlanningOccurrence,
  ScheduledBlock,
} from "../../types/watodo";

export type CalendarItemKind = "event" | "block" | "project_entry" | "shared";

/** Représentation unifiée d'une occurrence pour la grille. */
export interface CalendarItem {
  key: string;
  kind: CalendarItemKind;
  id: string;
  title: string;
  subtitle?: string;
  start: string;
  end: string;
  allDay: boolean;
  editable: boolean;
  /** À quel calendrier appartient l'item : "mine" ou l'id du propriétaire d'un
   * calendrier partagé — sert au filtre d'affichage (façon Outlook). */
  calendarId: string;
  /** Couleur d'identité du calendrier (calendrier partagé uniquement). */
  color?: string;
  raw: CalendarEventOccurrence | ScheduledBlock | ProjectPlanningOccurrence;
}

export function calendarUserLabel(u: { first_name: string; last_name: string; username: string }): string {
  return `${u.first_name} ${u.last_name}`.trim() || u.username;
}

export function eventToItem(
  occ: CalendarEventOccurrence,
  opts: { shared?: boolean; color?: string } = {},
): CalendarItem {
  const shared = opts.shared ?? false;
  return {
    key: `${shared ? "shared" : "event"}:${occ.id}:${occ.occurrence_start}`,
    kind: shared ? "shared" : "event",
    id: occ.id,
    title: occ.title,
    subtitle: shared ? calendarUserLabel(occ.owner) : occ.location,
    start: occ.start,
    end: occ.end,
    allDay: occ.all_day,
    editable: !shared && occ.permissions.can_edit,
    calendarId: shared ? occ.owner.id : "mine",
    color: opts.color,
    raw: occ,
  };
}

export function blockToItem(block: ScheduledBlock): CalendarItem {
  return {
    key: `block:${block.id}`,
    kind: "block",
    id: block.id,
    title: block.title,
    subtitle: block.task ? "Tâche planifiée" : "Incident planifié",
    start: block.start,
    end: block.end,
    allDay: false,
    editable: true,
    calendarId: "mine",
    raw: block,
  };
}

export function projectEntryToItem(occ: ProjectPlanningOccurrence): CalendarItem {
  return {
    key: `project_entry:${occ.id}:${occ.occurrence_start}`,
    kind: "project_entry",
    id: occ.id,
    title: occ.title,
    subtitle: occ.kind_display,
    start: occ.start,
    end: occ.end,
    allDay: occ.all_day,
    editable: occ.permissions.can_manage,
    calendarId: "mine",
    raw: occ,
  };
}
