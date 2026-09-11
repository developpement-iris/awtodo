import { useEffect, useRef, useState } from "react";
import "./InlineEditableText.css";

interface InlineEditableTextProps {
  value: string;
  onSave: (value: string) => void;
  ariaLabel: string;
  disabled?: boolean;
  className?: string;
}

export function InlineEditableText({ value, onSave, ariaLabel, disabled = false, className }: InlineEditableTextProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  function commit() {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed && trimmed !== value) {
      onSave(trimmed);
    } else {
      setDraft(value);
    }
  }

  function cancel() {
    setDraft(value);
    setEditing(false);
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        className={`inline-editable-text__input${className ? ` ${className}` : ""}`}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          // Toujours stoppée : un parent (carte Kanban, ligne de tableau…)
          // peut écouter Espace/Entrée pour ouvrir un modal — sans ça, taper
          // un espace dans le titre pendant l'édition déclenchait ce modal
          // (`role="button"` du parent qui reçoit l'événement remonté).
          event.stopPropagation();
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          }
          if (event.key === "Escape") {
            event.preventDefault();
            cancel();
          }
        }}
        aria-label={ariaLabel}
      />
    );
  }

  return (
    <span
      role={disabled ? undefined : "button"}
      tabIndex={disabled ? undefined : 0}
      className={`inline-editable-text__trigger${className ? ` ${className}` : ""}${disabled ? "" : " inline-editable-text__trigger--editable"}`}
      onClick={(event) => {
        if (disabled) return;
        event.stopPropagation();
        setEditing(true);
      }}
      onPointerDown={(event) => {
        if (!disabled) event.stopPropagation();
      }}
      onKeyDown={(event) => {
        if (disabled) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          event.stopPropagation();
          setEditing(true);
        }
      }}
      aria-label={disabled ? undefined : `${ariaLabel} — cliquer pour modifier`}
    >
      {value}
    </span>
  );
}
