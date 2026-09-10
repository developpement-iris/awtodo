// Helpers de dates pour le calendrier (fait main, comme RoadmapView — pas de
// librairie de dates). Tout en heure locale du navigateur.

export const DAY_MS = 24 * 60 * 60 * 1000;
/** Plage horaire affichée dans la grille semaine/jour. */
export const GRID_START_HOUR = 7;
export const GRID_END_HOUR = 21;
export const SLOT_MINUTES = 30;
/** Hauteur d'une heure dans la grille, en pixels. */
export const HOUR_HEIGHT = 48;
export const PX_PER_MINUTE = HOUR_HEIGHT / 60;
/** Hauteur d'un cran de 30 min, en pixels — pas de snap du glisser-déposer. */
export const SLOT_HEIGHT = SLOT_MINUTES * PX_PER_MINUTE;

export function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Lundi de la semaine contenant `date`. */
export function startOfWeek(date: Date): Date {
  const d = startOfDay(date);
  const day = d.getDay(); // 0 = dimanche
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  return d;
}

export function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

export function addMonths(date: Date, months: number): Date {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function weekDays(weekStart: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
}

export function gridHours(): number[] {
  return Array.from({ length: GRID_END_HOUR - GRID_START_HOUR + 1 }, (_, i) => GRID_START_HOUR + i);
}

/** Marques de 30 min de la grille (minutes depuis minuit), bornes incluses —
 * sert à dessiner les « crans » sur lesquels le glisser-déposer s'aligne. */
export function gridSlots(): number[] {
  const slots: number[] = [];
  for (let m = GRID_START_HOUR * 60; m <= GRID_END_HOUR * 60; m += SLOT_MINUTES) slots.push(m);
  return slots;
}

/** Aligne un décalage vertical en px sur le cran de 30 min le plus proche. */
export function snapOffset(px: number): number {
  return Math.round(px / SLOT_HEIGHT) * SLOT_HEIGHT;
}

/** Minutes depuis minuit -> position verticale en px dans la grille. */
export function minutesToOffset(minutesFromMidnight: number): number {
  return (minutesFromMidnight - GRID_START_HOUR * 60) * PX_PER_MINUTE;
}

export function snapMinutes(minutes: number): number {
  return Math.round(minutes / SLOT_MINUTES) * SLOT_MINUTES;
}

export function clampMinutes(minutes: number): number {
  return Math.max(GRID_START_HOUR * 60, Math.min(GRID_END_HOUR * 60, minutes));
}

// --- Conversion ISO <-> champs de formulaire -----------------------------

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** ISO (avec offset) -> valeur pour `<input type="datetime-local">`. */
export function isoToLocalInput(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}`;
}

/** Valeur de `<input type="datetime-local">` -> ISO UTC (`...Z`). */
export function localInputToIso(local: string): string {
  return new Date(local).toISOString();
}

/** Construit un ISO à partir d'un jour + minutes depuis minuit. */
export function dayAndMinutesToIso(day: Date, minutesFromMidnight: number): string {
  const d = new Date(day);
  d.setHours(0, 0, 0, 0);
  d.setMinutes(minutesFromMidnight);
  return d.toISOString();
}

export function formatHour(hour: number): string {
  return `${pad(hour)}:00`;
}

export function formatTimeRange(startIso: string, endIso: string): string {
  const s = new Date(startIso);
  const e = new Date(endIso);
  return `${pad(s.getHours())}:${pad(s.getMinutes())} – ${pad(e.getHours())}:${pad(e.getMinutes())}`;
}

export function formatDayLabel(date: Date): string {
  return date.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" });
}

export function formatMonthTitle(date: Date): string {
  return date.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
}

export function formatRangeTitle(weekStart: Date): string {
  const end = addDays(weekStart, 6);
  const sameMonth = weekStart.getMonth() === end.getMonth();
  const startLabel = weekStart.toLocaleDateString("fr-FR", {
    day: "numeric",
    month: sameMonth ? undefined : "short",
  });
  const endLabel = end.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
  return `${startLabel} – ${endLabel}`;
}
