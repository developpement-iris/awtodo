import { motion } from "motion/react";
import { useState } from "react";
import type { Incident } from "../../types/watodo";
import "./ResolveIncidentDialog.css";

interface ResolveIncidentDialogProps {
  incident: Incident;
  onConfirm: (resolutionComment: string, timeSpent: string) => void;
  onCancel: () => void;
  submitting?: boolean;
}

// Même patron que `CompleteDialog` (clôture d'une tâche) — un petit pop-up
// qui capture ce qui a été fait avant de passer l'incident en "résolu",
// plutôt qu'un simple bouton instantané (session du 2026-09-14).
export function ResolveIncidentDialog({
  incident,
  onConfirm,
  onCancel,
  submitting = false,
}: ResolveIncidentDialogProps) {
  const [resolutionComment, setResolutionComment] = useState("");
  const [timeSpent, setTimeSpent] = useState("");
  const timeValue = Number(timeSpent);
  const isValid =
    !submitting &&
    resolutionComment.trim().length > 0 &&
    timeSpent.trim().length > 0 &&
    Number.isFinite(timeValue) &&
    timeValue > 0;

  return (
    <div className="resolve-incident-dialog__overlay" onClick={onCancel}>
      <div className="resolve-incident-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="resolve-incident-dialog__title">Résoudre « {incident.title} »</h2>

        <label className="resolve-incident-dialog__label" htmlFor="resolve-comment">
          Commentaire de résolution
        </label>
        <textarea
          id="resolve-comment"
          className="resolve-incident-dialog__textarea"
          rows={3}
          value={resolutionComment}
          onChange={(event) => setResolutionComment(event.target.value)}
          placeholder="Ce qui a été fait pour corriger l'incident…"
          autoFocus
        />

        <label className="resolve-incident-dialog__label" htmlFor="resolve-time-spent">
          Temps passé (heures)
        </label>
        <input
          id="resolve-time-spent"
          className="resolve-incident-dialog__input"
          type="number"
          min="0"
          step="0.25"
          value={timeSpent}
          onChange={(event) => setTimeSpent(event.target.value)}
        />

        <div className="resolve-incident-dialog__actions">
          <motion.button
            type="button"
            className="resolve-incident-dialog__cancel"
            onClick={onCancel}
            whileTap={{ scale: 0.96 }}
          >
            Annuler
          </motion.button>
          <motion.button
            type="button"
            className="resolve-incident-dialog__confirm"
            disabled={!isValid}
            onClick={() => onConfirm(resolutionComment.trim(), timeSpent.trim())}
            whileTap={{ scale: 0.96 }}
          >
            Résoudre l'incident
          </motion.button>
        </div>
      </div>
    </div>
  );
}
