import { X } from "lucide-react";
import { useState } from "react";
import { cancelBlock, updateBlock } from "../../api/client";
import { DateTimeField } from "../../components/DateTimeField";
import type { ScheduledBlock } from "../../types/watodo";
import { isoToLocalInput, localInputToIso } from "./calendarMath";

interface BlockDialogProps {
  block: ScheduledBlock;
  onClose: () => void;
  onSaved: () => void;
}

export function BlockDialog({ block, onClose, onSaved }: BlockDialogProps) {
  const [start, setStart] = useState(isoToLocalInput(block.start));
  const [end, setEnd] = useState(isoToLocalInput(block.end));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const target = block.task ?? block.incident;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!start || !end) {
      setError("Début et fin sont obligatoires.");
      return;
    }
    setBusy(true);
    try {
      await updateBlock(block.id, { start: localInputToIso(start), end: localInputToIso(end) });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelBlock() {
    setBusy(true);
    try {
      await cancelBlock(block.id);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Suppression impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="planning-dialog__overlay" onClick={onClose}>
      <div className="planning-dialog planning-dialog--narrow" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="planning-dialog__header">
          <h2>Modifier le créneau</h2>
          <button type="button" className="planning-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {error && <p className="planning-dialog__error">{error}</p>}

        <form className="planning-dialog__body" onSubmit={handleSubmit}>
          <p className="planning-dialog__readonly-title">{target?.title}</p>
          <p className="planning-dialog__readonly-meta">
            {block.task ? "Tâche" : "Incident"}
            {block.task ? ` — ${block.task.status_display}` : ""}
          </p>

          <div className="planning-field-row">
            <label className="planning-field">
              <span>Début</span>
              <DateTimeField value={start} onChange={setStart} />
            </label>
            <label className="planning-field">
              <span>Fin</span>
              <DateTimeField value={end} onChange={setEnd} />
            </label>
          </div>

          <p className="planning-dialog__muted">
            Modifier le créneau ne change pas le statut de la tâche.
          </p>

          <div className="planning-dialog__footer">
            <button
              type="button"
              className="planning-btn planning-btn--danger"
              onClick={handleCancelBlock}
              disabled={busy}
            >
              Retirer du planning
            </button>
            <span className="planning-dialog__footer-spacer" />
            <button type="button" className="planning-btn" onClick={onClose} disabled={busy}>
              Fermer
            </button>
            <button type="submit" className="planning-btn planning-btn--primary" disabled={busy}>
              Enregistrer
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
