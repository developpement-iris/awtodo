import { motion } from "motion/react";
import { useState } from "react";
import "./CancelDialog.css";

interface CancelDialogProps {
  title: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

// Partagé entre tâches et incidents (session du 2026-09-24) — même patron que
// RejectDialog (frontend/src/features/tasks/RejectDialog.tsx), généralisé sur
// un simple titre plutôt qu'un `Task` puisque les deux entités ont besoin du
// même formulaire (motif obligatoire).
export function CancelDialog({ title, onConfirm, onCancel }: CancelDialogProps) {
  const [reason, setReason] = useState("");

  return (
    <div className="cancel-dialog__overlay" onClick={onCancel}>
      <div className="cancel-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="cancel-dialog__title">Annuler « {title} »</h2>
        <label className="cancel-dialog__label" htmlFor="cancel-reason">
          Motif de l'annulation
        </label>
        <textarea
          id="cancel-reason"
          className="cancel-dialog__textarea"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={3}
          autoFocus
        />
        <div className="cancel-dialog__actions">
          <motion.button type="button" className="cancel-dialog__cancel" onClick={onCancel} whileTap={{ scale: 0.96 }}>
            Retour
          </motion.button>
          <motion.button
            type="button"
            className="cancel-dialog__confirm"
            disabled={reason.trim().length === 0}
            onClick={() => onConfirm(reason.trim())}
            whileTap={{ scale: 0.96 }}
          >
            Confirmer l'annulation
          </motion.button>
        </div>
      </div>
    </div>
  );
}
