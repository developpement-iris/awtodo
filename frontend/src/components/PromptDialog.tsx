import { motion } from "motion/react";
import { useState } from "react";
import "./PromptDialog.css";

interface PromptDialogProps {
  title: string;
  label?: string;
  initialValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}

// Remplace `window.prompt` (session du 2026-10-06, retour direct : "on a une
// vieille alert js horrible... utilise une modal comme sur les autres, avec
// une card centrale") — même patron que CancelDialog/ConfirmDialog (overlay +
// card centrée), généralisé pour une simple saisie de texte obligatoire.
export function PromptDialog({
  title,
  label,
  initialValue = "",
  placeholder,
  confirmLabel = "Valider",
  cancelLabel = "Annuler",
  onConfirm,
  onCancel,
}: PromptDialogProps) {
  const [value, setValue] = useState(initialValue);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed) return;
    onConfirm(trimmed);
  }

  return (
    <div className="prompt-dialog__overlay" onClick={onCancel}>
      <div className="prompt-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="prompt-dialog__title">{title}</h2>
        {label && (
          <label className="prompt-dialog__label" htmlFor="prompt-dialog-input">
            {label}
          </label>
        )}
        <input
          id="prompt-dialog-input"
          className="prompt-dialog__input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={placeholder}
          autoFocus
          onKeyDown={(event) => {
            if (event.key === "Enter") submit();
          }}
        />
        <div className="prompt-dialog__actions">
          <motion.button type="button" className="prompt-dialog__cancel" onClick={onCancel} whileTap={{ scale: 0.96 }}>
            {cancelLabel}
          </motion.button>
          <motion.button
            type="button"
            className="prompt-dialog__confirm"
            disabled={!value.trim()}
            onClick={submit}
            whileTap={{ scale: 0.96 }}
          >
            {confirmLabel}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
