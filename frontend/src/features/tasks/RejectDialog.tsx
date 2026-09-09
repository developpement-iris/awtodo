import { motion } from "motion/react";
import { useState } from "react";
import type { Task } from "../../types/watodo";
import "./RejectDialog.css";

interface RejectDialogProps {
  task: Task;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export function RejectDialog({ task, onConfirm, onCancel }: RejectDialogProps) {
  const [reason, setReason] = useState("");

  return (
    <div className="reject-dialog__overlay" onClick={onCancel}>
      <div className="reject-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="reject-dialog__title">Rejeter « {task.title} »</h2>
        <label className="reject-dialog__label" htmlFor="reject-reason">
          Motif du rejet
        </label>
        <textarea
          id="reject-reason"
          className="reject-dialog__textarea"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={3}
          autoFocus
        />
        <div className="reject-dialog__actions">
          <motion.button type="button" className="reject-dialog__cancel" onClick={onCancel} whileTap={{ scale: 0.96 }}>
            Annuler
          </motion.button>
          <motion.button
            type="button"
            className="reject-dialog__confirm"
            disabled={reason.trim().length === 0}
            onClick={() => onConfirm(reason.trim())}
            whileTap={{ scale: 0.96 }}
          >
            Rejeter la tâche
          </motion.button>
        </div>
      </div>
    </div>
  );
}
