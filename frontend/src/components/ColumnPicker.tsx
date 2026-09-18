import { Columns3 } from "lucide-react";
import { useRef, useState } from "react";
import { AnchoredPanel } from "./AnchoredPanel";
import { Checkbox } from "./Checkbox";
import "./ColumnPicker.css";

export interface ColumnDef<K extends string> {
  key: K;
  label: string;
}

interface ColumnPickerProps<K extends string> {
  columns: ColumnDef<K>[];
  visible: Set<K>;
  onChange: (next: Set<K>) => void;
}

/** Sélecteur de colonnes affichées sur une liste — voir `useColumnPreferences`
 * (mémorisation par utilisateur, en cache local). Même habillage bouton rond
 * que `StatusFilterDropdown`, panneau `AnchoredPanel` (pattern `Combobox`/
 * `DateTimeField`) plutôt qu'un `position: absolute` local. */
export function ColumnPicker<K extends string>({ columns, visible, onChange }: ColumnPickerProps<K>) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  function toggle(key: K) {
    const next = new Set(visible);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  return (
    <>
      <button
        type="button"
        ref={triggerRef}
        className="column-picker__trigger"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-label="Choisir les colonnes affichées"
        title="Colonnes"
      >
        <Columns3 size={16} strokeWidth={1.75} aria-hidden="true" />
      </button>

      {open && (
        <AnchoredPanel anchorRef={triggerRef} onClose={() => setOpen(false)} width="auto" className="column-picker__panel">
          <p className="column-picker__heading">Colonnes affichées</p>
          <ul className="column-picker__list">
            {columns.map((column) => (
              <li key={column.key}>
                <label className="column-picker__option">
                  <Checkbox
                    checked={visible.has(column.key)}
                    onCheckedChange={() => toggle(column.key)}
                    aria-label={column.label}
                  />
                  {column.label}
                </label>
              </li>
            ))}
          </ul>
        </AnchoredPanel>
      )}
    </>
  );
}
