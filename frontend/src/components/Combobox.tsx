import { Command } from "cmdk";
import { Check, ChevronsUpDown } from "lucide-react";
import { useId, useRef, useState } from "react";
import { AnchoredPanel } from "./AnchoredPanel";
import "./Combobox.css";

export interface ComboboxOption {
  value: string;
  label: string;
  /** Ligne secondaire optionnelle (ex. « invitation en attente »). */
  hint?: string;
}

interface ComboboxProps {
  options: ComboboxOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyLabel?: string;
  disabled?: boolean;
  /** Affiche le champ de recherche. Par défaut : seulement au-delà de 7 options. */
  searchable?: boolean;
  /** Autorise le retour à la valeur vide en re-sélectionnant l'option active.
   * `false` pour un choix obligatoire (type, priorité…). */
  clearable?: boolean;
  id?: string;
}

const SEARCH_THRESHOLD = 7;

/**
 * Sélecteur unique (cmdk), remplaçant unifié des `<select>` de l'app. Le
 * panneau est rendu dans un portail (`AnchoredPanel`) — il s'affranchit de
 * l'`overflow` des dialogues qui l'accueillent et bascule vers le haut au
 * besoin.
 */
export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Choisir…",
  searchPlaceholder = "Rechercher…",
  emptyLabel = "Aucun résultat.",
  disabled = false,
  searchable,
  clearable = true,
  id,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const fallbackId = useId();
  const listboxId = `${id ?? fallbackId}-listbox`;
  const showSearch = searchable ?? options.length > SEARCH_THRESHOLD;

  const selected = options.find((option) => option.value === value) ?? null;

  return (
    <div className="combobox">
      <button
        type="button"
        id={id}
        ref={triggerRef}
        className="combobox__trigger"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => setOpen((previous) => !previous)}
      >
        <span className={selected ? "combobox__value" : "combobox__value combobox__value--placeholder"}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronsUpDown size={15} strokeWidth={1.75} className="combobox__chevron" aria-hidden="true" />
      </button>

      {open && (
        <AnchoredPanel anchorRef={triggerRef} onClose={() => setOpen(false)} className="combobox__panel">
          <Command loop label={placeholder} shouldFilter={showSearch}>
            {showSearch && (
              <Command.Input autoFocus placeholder={searchPlaceholder} className="combobox__input" />
            )}
            <Command.List id={listboxId} className="combobox__list">
              {showSearch && <Command.Empty className="combobox__empty">{emptyLabel}</Command.Empty>}
              {options.length === 0 && !showSearch && <div className="combobox__empty">{emptyLabel}</div>}
              {options.map((option) => (
                <Command.Item
                  key={option.value || "__empty__"}
                  value={`${option.label} ${option.hint ?? ""}`}
                  className="combobox__item"
                  onSelect={() => {
                    onChange(clearable && option.value === value ? "" : option.value);
                    setOpen(false);
                  }}
                >
                  <Check
                    size={14}
                    strokeWidth={2}
                    className="combobox__check"
                    data-checked={option.value === value}
                    aria-hidden="true"
                  />
                  <span className="combobox__item-text">
                    {option.label}
                    {option.hint && <span className="combobox__item-hint">{option.hint}</span>}
                  </span>
                </Command.Item>
              ))}
            </Command.List>
          </Command>
        </AnchoredPanel>
      )}
    </div>
  );
}
