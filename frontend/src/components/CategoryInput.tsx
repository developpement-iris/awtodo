import { Plus, X } from "lucide-react";
import { useId, useMemo, useRef, useState } from "react";
import { categoryKey } from "../lib/categoryKey";
import { AnchoredPanel } from "./AnchoredPanel";
import "./CategoryInput.css";

interface CategoryInputProps {
  /** Valeurs choisies. En mode simple, au plus une. */
  values: string[];
  onChange: (values: string[]) => void;
  /** Valeurs déjà utilisées ailleurs dans l'organisation. */
  suggestions: string[];
  multiple?: boolean;
  placeholder?: string;
  id?: string;
}

/**
 * Saisie assistée d'une catégorie (session du 2026-11-14) : on choisit une
 * valeur déjà utilisée par d'autres projets, ou on en crée une. Les
 * suggestions ignorent la casse et les accents ; le serveur ramène de toute
 * façon un quasi-doublon à l'orthographe déjà en place.
 */
export function CategoryInput({
  values,
  onChange,
  suggestions,
  multiple = false,
  placeholder = "Choisir ou créer…",
  id,
}: CategoryInputProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const fieldRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fallbackId = useId();
  const listId = `${id ?? fallbackId}-list`;

  const chosenKeys = useMemo(() => new Set(values.map(categoryKey)), [values]);
  const typedKey = categoryKey(query);

  const options = useMemo(() => {
    const matches = suggestions.filter(
      (suggestion) => !chosenKeys.has(categoryKey(suggestion)) && categoryKey(suggestion).includes(typedKey),
    );
    const exists = suggestions.some((suggestion) => categoryKey(suggestion) === typedKey) || chosenKeys.has(typedKey);
    const list = matches.map((label) => ({ label, create: false }));
    if (typedKey && !exists) list.push({ label: query.trim().replace(/\s+/g, " "), create: true });
    return list;
  }, [suggestions, chosenKeys, typedKey, query]);

  function choose(label: string) {
    if (!label) return;
    onChange(multiple ? [...values, label] : [label]);
    setQuery("");
    setActive(0);
    if (!multiple) setOpen(false);
    inputRef.current?.focus();
  }

  function remove(label: string) {
    onChange(values.filter((value) => value !== label));
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((index) => Math.min(index + 1, options.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const option = options[active];
      if (option) choose(option.label);
    } else if (event.key === "Backspace" && !query && values.length) {
      remove(values[values.length - 1]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const showInput = multiple || values.length === 0;

  return (
    <div className="category-input">
      <div className="category-input__field" ref={fieldRef} onClick={() => inputRef.current?.focus()}>
        {values.map((value) => (
          <span key={value} className="category-input__chip">
            {value}
            <button type="button" onClick={() => remove(value)} aria-label={`Retirer ${value}`}>
              <X size={12} strokeWidth={2} aria-hidden="true" />
            </button>
          </span>
        ))}
        {showInput && (
          <input
            ref={inputRef}
            id={id}
            type="text"
            value={query}
            placeholder={values.length ? "" : placeholder}
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
          />
        )}
      </div>
      {open && showInput && options.length > 0 && (
        <AnchoredPanel anchorRef={fieldRef} onClose={() => setOpen(false)} className="category-input__panel">
          <ul id={listId} role="listbox" className="category-input__list">
            {options.map((option, index) => (
              <li
                key={`${option.create ? "+" : ""}${option.label}`}
                role="option"
                aria-selected={index === active}
                className={index === active ? "is-active" : undefined}
                onPointerDown={(event) => {
                  event.preventDefault();
                  choose(option.label);
                }}
                onPointerEnter={() => setActive(index)}
              >
                {option.create ? (
                  <>
                    <Plus size={13} strokeWidth={2} aria-hidden="true" />
                    Créer « {option.label} »
                  </>
                ) : (
                  option.label
                )}
              </li>
            ))}
          </ul>
        </AnchoredPanel>
      )}
    </div>
  );
}
