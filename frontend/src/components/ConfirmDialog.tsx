import { motion } from "motion/react";
import "./ConfirmDialog.css";

interface ConfirmDialogProps {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// Remplace `window.confirm` (session du 2026-10-06, retour direct : "on a une
// vieille alert js horrible... utilise une modal comme sur les autres, avec
// une card centrale") — même patron que CancelDialog (overlay + card
// centrée), généralisé pour toute confirmation sans motif à saisir.
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirmer",
  cancelLabel = "Annuler",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <div className="confirm-dialog__overlay" onClick={onCancel}>
      <div className="confirm-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="confirm-dialog__title">{title}</h2>
        {message && <p className="confirm-dialog__message">{message}</p>}
        <div className="confirm-dialog__actions">
          <motion.button type="button" className="confirm-dialog__cancel" onClick={onCancel} whileTap={{ scale: 0.96 }}>
            {cancelLabel}
          </motion.button>
          <motion.button
            type="button"
            className={`confirm-dialog__confirm${danger ? " confirm-dialog__confirm--danger" : ""}`}
            onClick={onConfirm}
            whileTap={{ scale: 0.96 }}
            autoFocus
          >
            {confirmLabel}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
