import { useEffect, useRef, useState } from "react";
import "./InlineEditableTextarea.css";

interface InlineEditableTextareaProps {
  value: string;
  onSave: (value: string) => void;
  ariaLabel: string;
  disabled?: boolean;
  rows?: number;
  placeholder?: string;
  /** Affiché à la place du texte quand `value` est vide et non en édition. */
  emptyLabel?: string;
}

// Variante multi-ligne d'InlineEditableText : le clic direct sur le texte
// déclenche l'édition (même affordance), mais contrairement au champ
// mono-ligne, la validation n'a jamais lieu au blur/Entrée (qui doit rester
// un retour à la ligne) — seuls les boutons Enregistrer/Annuler explicites
// valident, pour ne pas perdre un texte long sur un blur accidentel.
export function InlineEditableTextarea({
  value,
  onSave,
  ariaLabel,
  disabled = false,
  rows = 4,
  placeholder,
  emptyLabel = "Vide pour l'instant.",
}: InlineEditableTextareaProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  useEffect(() => {
    if (editing) {
      textareaRef.current?.focus();
    }
  }, [editing]);

  function startEditing() {
    if (disabled) return;
    setEditing(true);
  }

  async function commit() {
    const trimmed = draft.trim();
    if (trimmed === value.trim()) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(trimmed);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  function cancel() {
    setDraft(value);
    setEditing(false);
  }

  if (editing) {
    return (
      <div className="inline-editable-textarea__editor">
        <textarea
          ref={textareaRef}
          className="inline-editable-textarea__input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              cancel();
            }
          }}
          rows={rows}
          placeholder={placeholder}
          disabled={saving}
          aria-label={ariaLabel}
        />
        <div className="inline-editable-textarea__actions">
          <button type="button" className="inline-editable-textarea__cancel" onClick={cancel} disabled={saving}>
            Annuler
          </button>
          <button type="button" className="inline-editable-textarea__save" onClick={commit} disabled={saving}>
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      role={disabled ? undefined : "button"}
      tabIndex={disabled ? undefined : 0}
      className={`inline-editable-textarea__trigger${disabled ? "" : " inline-editable-textarea__trigger--editable"}${value ? "" : " inline-editable-textarea__trigger--empty"}`}
      onClick={startEditing}
      onKeyDown={(event) => {
        if (disabled) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          startEditing();
        }
      }}
      aria-label={disabled ? undefined : `${ariaLabel} — cliquer pour modifier`}
    >
      {value || emptyLabel}
    </div>
  );
}
