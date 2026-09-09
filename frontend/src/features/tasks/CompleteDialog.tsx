import { motion } from "motion/react";
import { useState } from "react";
import type { Task } from "../../types/watodo";
import "./CompleteDialog.css";

interface CompleteDialogProps {
  task: Task;
  onConfirm: (timeSpent: string) => void;
  onCancel: () => void;
}

export function CompleteDialog({ task, onConfirm, onCancel }: CompleteDialogProps) {
  const [timeSpent, setTimeSpent] = useState("");
  const value = Number(timeSpent);
  const isValid = timeSpent.trim().length > 0 && Number.isFinite(value) && value > 0;

  return (
    <div className="complete-dialog__overlay" onClick={onCancel}>
      <div className="complete-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="complete-dialog__title">Clôturer « {task.title} »</h2>
        <label className="complete-dialog__label" htmlFor="complete-time-spent">
          Temps passé (heures)
        </label>
        <input
          id="complete-time-spent"
          className="complete-dialog__input"
          type="number"
          min="0"
          step="0.25"
          value={timeSpent}
          onChange={(event) => setTimeSpent(event.target.value)}
          autoFocus
        />
        <div className="complete-dialog__actions">
          <motion.button type="button" className="complete-dialog__cancel" onClick={onCancel} whileTap={{ scale: 0.96 }}>
            Annuler
          </motion.button>
          <motion.button
            type="button"
            className="complete-dialog__confirm"
            disabled={!isValid}
            onClick={() => onConfirm(timeSpent.trim())}
            whileTap={{ scale: 0.96 }}
          >
            Clôturer la tâche
          </motion.button>
        </div>
      </div>
    </div>
  );
}
