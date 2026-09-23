import { X } from "lucide-react";
import { useState } from "react";
import { cancelEventOccurrence, updateEventOccurrence } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { DateTimeField } from "../../components/DateTimeField";
import type { CalendarEventOccurrence } from "../../types/watodo";
import { isoToLocalInput, localInputToIso } from "./calendarMath";

interface EventOccurrenceDialogProps {
  occurrence: CalendarEventOccurrence;
  onClose: () => void;
  onSaved: () => void;
}

/** Édite ou annule UNE occurrence d'une série, pas la série entière (session
 * du 2026-09-23 — "si on modifie un évènement de la série, ça ne doit
 * modifier que l'évènement"). Formulaire volontairement plus simple que
 * `EventDialog` : pas de récurrence (ne s'applique qu'à la série), pas de
 * participants (invitation = toute la série, voir `EventDialog`). */
export function EventOccurrenceDialog({ occurrence, onClose, onSaved }: EventOccurrenceDialogProps) {
  const [title, setTitle] = useState(occurrence.title);
  const [description, setDescription] = useState(occurrence.description);
  const [location, setLocation] = useState(occurrence.location);
  const [start, setStart] = useState(isoToLocalInput(occurrence.start));
  const [end, setEnd] = useState(isoToLocalInput(occurrence.end));
  const [allDay, setAllDay] = useState(occurrence.all_day);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const readOnly = !occurrence.permissions.can_edit;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim() || !start || !end) {
      setError("Titre, début et fin sont obligatoires.");
      return;
    }
    setBusy(true);
    try {
      await updateEventOccurrence(occurrence.id, {
        occurrence_start: occurrence.occurrence_start,
        title: title.trim(),
        description,
        location,
        start: localInputToIso(start),
        end: localInputToIso(end),
        all_day: allDay,
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelOccurrence() {
    setBusy(true);
    setError(null);
    try {
      await cancelEventOccurrence(occurrence.id, occurrence.occurrence_start);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Annulation impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="planning-dialog__overlay" onClick={onClose}>
      <div className="planning-dialog" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="planning-dialog__header">
          <h2>Cette occurrence</h2>
          <button type="button" className="planning-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {error && <p className="planning-dialog__error">{error}</p>}

        {readOnly ? (
          <div className="planning-dialog__body">
            <p className="planning-dialog__readonly-title">{occurrence.title}</p>
            <p className="planning-dialog__readonly-meta">
              {new Date(occurrence.start).toLocaleString("fr-FR")} → {new Date(occurrence.end).toLocaleString("fr-FR")}
            </p>
            {occurrence.location && <p className="planning-dialog__readonly-meta">Lieu : {occurrence.location}</p>}
            {occurrence.description && <p className="planning-dialog__readonly-desc">{occurrence.description}</p>}
          </div>
        ) : (
          <form className="planning-dialog__body" onSubmit={handleSubmit}>
            <p className="planning-dialog__muted">
              Les changements ci-dessous ne s'appliquent qu'à cette occurrence — le reste de la série n'est pas
              affecté.
            </p>

            <label className="planning-field">
              <span>Titre</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus required />
            </label>

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

            <label className="planning-field planning-field--inline">
              <Checkbox checked={allDay} onCheckedChange={setAllDay} aria-label="Toute la journée" />
              <span>Toute la journée</span>
            </label>

            <label className="planning-field">
              <span>Lieu</span>
              <input value={location} onChange={(e) => setLocation(e.target.value)} />
            </label>

            <label className="planning-field">
              <span>Description</span>
              <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>

            <div className="planning-dialog__footer">
              <button
                type="button"
                className="planning-btn planning-btn--danger"
                onClick={handleCancelOccurrence}
                disabled={busy}
              >
                Supprimer cette occurrence
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
        )}
      </div>
    </div>
  );
}
