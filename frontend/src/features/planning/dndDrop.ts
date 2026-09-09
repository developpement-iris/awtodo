import type { DragEndEvent } from "@dnd-kit/core";
import { GRID_START_HOUR, PX_PER_MINUTE, clampMinutes, snapMinutes } from "./calendarMath";

export interface DropResult {
  dayIso: string;
  minutes: number;
}

/** Résout la cible d'un drop sur la grille semaine : jour survolé + minute
 * (snap 30 min) calculée à partir de la position finale du pointeur. */
export function resolveDrop(event: DragEndEvent): DropResult | null {
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

export function isoAt(dayIso: string, minutes: number): string {
  const d = new Date(`${dayIso}T00:00:00`);
  d.setMinutes(minutes);
  return d.toISOString();
}
