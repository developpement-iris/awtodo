import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { SortDirection } from "../hooks/useSort";
import "./SortableColumnHeader.css";

interface SortableColumnHeaderProps<K extends string> {
  label: string;
  columnKey: K;
  sortKey: K | null;
  direction: SortDirection;
  onSort: (key: K) => void;
}

/** En-tête de colonne cliquable pour trier une liste (Tâches/Incidents…) —
 * voir `useSort`. Même habillage dans les deux écrans : icône flèche double
 * au repos, flèche simple orientée une fois la colonne active. */
export function SortableColumnHeader<K extends string>({
  label,
  columnKey,
  sortKey,
  direction,
  onSort,
}: SortableColumnHeaderProps<K>) {
  const active = sortKey === columnKey;
  return (
    <th aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" className="sortable-header" onClick={() => onSort(columnKey)}>
        {label}
        {active ? (
          direction === "asc" ? (
            <ArrowUp size={12} strokeWidth={1.75} aria-hidden="true" />
          ) : (
            <ArrowDown size={12} strokeWidth={1.75} aria-hidden="true" />
          )
        ) : (
          <ArrowUpDown size={12} strokeWidth={1.75} aria-hidden="true" className="sortable-header__idle" />
        )}
      </button>
    </th>
  );
}
