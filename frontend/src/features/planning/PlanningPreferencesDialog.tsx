import { Check, X } from "lucide-react";
import { useState } from "react";
import { updatePlanningPreferences } from "../../api/client";
import type { Me } from "../../types/watodo";
import { PLANNING_PALETTE } from "./types";

interface PlanningPreferencesDialogProps {
  me: Me;
  onClose: () => void;
  onSaved: (updated: Me) => void;
}

function toHm(time: string): string {
  return time.slice(0, 5);
}

export function PlanningPreferencesDialog({ me, onClose, onSaved }: PlanningPreferencesDialogProps) {
  const [color, setColor] = useState(me.planning_color);
  const [start, setStart] = useState(toHm(me.work_hours_start));
  const [end, setEnd] = useState(toHm(me.work_hours_end));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (start >= end) {
      setError("L'heure de début doit précéder l'heure de fin.");
      return;
    }
    setBusy(true);
    try {
      const updated = await updatePlanningPreferences({
        planningColor: color,
        workHoursStart: start,
        workHoursEnd: end,
      });
      onSaved(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="planning-dialog__overlay" onClick={onClose}>
      <div
        className="planning-dialog planning-dialog--narrow"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="planning-dialog__header">
          <h2>Mon planning</h2>
          <button type="button" className="planning-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {error && <p className="planning-dialog__error">{error}</p>}

        <form className="planning-dialog__body" onSubmit={handleSubmit}>
          <div className="planning-field">
            <span>Couleur de mon calendrier</span>
            <div className="planning-color-swatches">
              <button
                type="button"
                className={`planning-color-swatch planning-color-swatch--default${color === "" ? " planning-color-swatch--selected" : ""}`}
                onClick={() => setColor("")}
                aria-label="Couleur par défaut (accent thémé)"
                title="Par défaut"
              >
                {color === "" && <Check size={13} strokeWidth={2} aria-hidden="true" />}
              </button>
              {PLANNING_PALETTE.map((hex) => (
                <button
                  key={hex}
                  type="button"
                  className={`planning-color-swatch${color === hex ? " planning-color-swatch--selected" : ""}`}
                  style={{ backgroundColor: hex }}
                  onClick={() => setColor(hex)}
                  aria-label={`Choisir la couleur ${hex}`}
                  title={hex}
                >
                  {color === hex && <Check size={13} strokeWidth={2} color="#fff" aria-hidden="true" />}
                </button>
              ))}
            </div>
          </div>

          <div className="planning-field-row">
            <label className="planning-field">
              <span>Début de journée</span>
              <input type="time" value={start} onChange={(event) => setStart(event.target.value)} />
            </label>
            <label className="planning-field">
              <span>Fin de journée</span>
              <input type="time" value={end} onChange={(event) => setEnd(event.target.value)} />
            </label>
          </div>

          <p className="planning-dialog__muted">
            Les horaires en dehors de cette plage apparaissent grisés dans la vue Semaine.
          </p>

          <div className="planning-dialog__footer">
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
