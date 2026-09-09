import type { Task } from "../types/watodo";

// "rejetee" existe comme colonne (voir "Filtre d'état généralisé",
// docs/modeles-et-api.md) mais reste masquée par défaut, comme "archivee" —
// KanbanBoard ne rend que les colonnes cochées dans le filtre "Afficher".
export const KANBAN_COLUMNS = [
  "en_attente_validation",
  "disponible",
  "assignee",
  "en_cours",
  "archivee",
  "rejetee",
] as const;

export type KanbanStatus = (typeof KANBAN_COLUMNS)[number];

export const KANBAN_COLUMN_LABELS: Record<KanbanStatus, string> = {
  en_attente_validation: "En attente de validation",
  disponible: "Disponible",
  assignee: "Assignée",
  en_cours: "En cours",
  archivee: "Archivée",
  rejetee: "Rejetée",
};

// Périmètre du drag-and-drop volontairement restreint (voir CLAUDE.md —
// "Correction — périmètre du drag-and-drop dans le Kanban") : seules les
// transitions (a) sans information supplémentaire requise et (b) à acteur
// non ambigu sont draggables. `validate`/`claim`/`reject` sont retirées du
// drag (acteur ambigu ou dialog obligatoire) — restent accessibles via les
// boutons explicites du drawer/de la carte, jamais perdues, juste pas en drag.
export type DragActionKind = "start" | "complete-dialog";

const DRAG_ACTIONS: Partial<Record<KanbanStatus, Partial<Record<KanbanStatus, DragActionKind>>>> = {
  assignee: { en_cours: "start" },
  // `en_cours → archivee` n'exécute jamais la clôture directement au drop —
  // ouvre le dialog de saisie du temps existant (voir handleDragEnd).
  en_cours: { archivee: "complete-dialog" },
};

export function resolveDragAction(from: string, to: string): DragActionKind | null {
  return DRAG_ACTIONS[from as KanbanStatus]?.[to as KanbanStatus] ?? null;
}

// Un drop peut correspondre à une transition valide dans l'absolu (via
// resolveDragAction) sans que l'utilisateur courant ait le droit de
// l'effectuer — lit directement `task.permissions` (voir CLAUDE.md >
// "Permissions API — flags calculés"), jamais de règle de rôle/statut
// recalculée ici. Utilisé pour griser les colonnes non valides pendant un
// drag plutôt que d'accepter le drop et échouer après coup — seule
// exception documentée à la règle « masqué, pas grisé » : une colonne du
// Kanban est une zone structurelle, pas un bouton d'action isolé.
export function isDropAllowed(task: Task, toStatus: string): boolean {
  const actionKind = resolveDragAction(task.status, toStatus);
  if (actionKind === "start") return task.permissions.can_start;
  if (actionKind === "complete-dialog") return task.permissions.can_complete;
  return false;
}
