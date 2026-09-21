import type { SortDirection } from "../hooks/useSort";

// Valeurs manquantes toujours en dernier, quel que soit le sens de tri —
// partagé entre TasksListPage et IncidentsPage (colonnes "temps
// estimé/passé", "échéance"...).

export function compareNullableNumbers(a: string | null, b: string | null, direction: SortDirection): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  const diff = Number(a) - Number(b);
  return direction === "asc" ? diff : -diff;
}

export function compareNullableStrings(a: string | null, b: string | null, direction: SortDirection): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  const diff = a.localeCompare(b, "fr");
  return direction === "asc" ? diff : -diff;
}
