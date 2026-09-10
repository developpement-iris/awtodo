import { Command } from "cmdk";
import { Check, ChevronsUpDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
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
  id?: string;
}

/**
 * Sélecteur unique avec recherche (cmdk). Le panneau s'ouvre dans le flux,
 * sous le déclencheur — pas de portail : les dialogues qui l'accueillent ont
 * `overflow-y: auto`, un panneau en `position: absolute` y serait rogné.
 */
export function Combobox({
  options,
  value,
  onChange,
  placeholder = "Choisir…",
  searchPlaceholder = "Rechercher…",
  emptyLabel = "Aucun résultat.",
  disabled = false,
  id,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const fallbackId = useId();
  const listboxId = `${id ?? fallbackId}-listbox`;

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: PointerEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const selected = options.find((option) => option.value === value) ?? null;

  return (
    <div className="combobox" ref={wrapperRef}>
      <button
        type="button"
        id={id}
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
        <div className="combobox__panel">
          <Command loop label={placeholder}>
            <Command.Input autoFocus placeholder={searchPlaceholder} className="combobox__input" />
            <Command.List id={listboxId} className="combobox__list">
              <Command.Empty className="combobox__empty">{emptyLabel}</Command.Empty>
              {options.map((option) => (
                <Command.Item
                  key={option.value}
                  value={`${option.label} ${option.hint ?? ""}`}
                  className="combobox__item"
                  onSelect={() => {
                    onChange(option.value === value ? "" : option.value);
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
        </div>
      )}
    </div>
  );
}
