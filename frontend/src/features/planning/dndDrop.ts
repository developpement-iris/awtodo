import type { DragEndEvent, DragMoveEvent } from "@dnd-kit/core";
import { GRID_START_HOUR, PX_PER_MINUTE, clampMinutes, minutesToOffset, snapMinutes } from "./calendarMath";

export interface DropResult {
  dayIso: string;
  minutes: number;
}

/** Résout la cible d'un drop (ou d'un survol) sur la grille semaine à partir
 * de la position **absolue du pointeur** : jour survolé + minute (snap 30
 * min). Correct quand il n'y a pas de position de départ à corriger — dépôt
 * d'une tâche externe (le pointeur EST l'endroit visé), et redimensionnement
 * (la poignée est au bord de l'item, pas en son centre). */
export function resolveDrop(event: DragEndEvent | DragMoveEvent): DropResult | null {
  const overId = event.over ? String(event.over.id) : "";
  if (!overId.startsWith("day:")) return null;
  const dayIso = overId.slice(4);
  const el = document.querySelector(`[data-planning-day="${dayIso}"]`);
  if (!(el instanceof HTMLElement)) return null;
  const rect = el.getBoundingClientRect();
  const activator = event.activatorEvent as PointerEvent | MouseEvent;
  const clientY = "clientY" in activator ? activator.clientY : rect.top;
  const y = clientY + event.delta.y - rect.top;
  const minutes = clampMinutes(snapMinutes(y / PX_PER_MINUTE + GRID_START_HOUR * 60));
  return { dayIso, minutes };
}

/** Résout la cible du **déplacement** d'un item déjà positionné sur la
 * grille : jour survolé + nouvelle heure de début, dérivée du décalage du
 * glissé (`event.delta.y`) appliqué à l'heure de départ de l'item — pas de la
 * position absolue du pointeur. Sans ça, le point de référence est l'endroit
 * où le pointeur a saisi l'item (souvent son milieu), pas son bord haut : un
 * item de 15h-16h saisi en son centre retombait décalé d'une demi-heure. */
export function resolveMove(event: DragEndEvent | DragMoveEvent, itemStartIso: string): DropResult | null {
  const overId = event.over ? String(event.over.id) : "";
  if (!overId.startsWith("day:")) return null;
  const dayIso = overId.slice(4);
  const start = new Date(itemStartIso);
  const startMinutes = start.getHours() * 60 + start.getMinutes();
  const topPx = minutesToOffset(startMinutes) + event.delta.y;
  const minutes = clampMinutes(snapMinutes(topPx / PX_PER_MINUTE + GRID_START_HOUR * 60));
  return { dayIso, minutes };
}

export function isoAt(dayIso: string, minutes: number): string {
  const d = new Date(`${dayIso}T00:00:00`);
  d.setMinutes(minutes);
  return d.toISOString();
}
