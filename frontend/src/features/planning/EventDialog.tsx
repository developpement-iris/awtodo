import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { Checkbox } from "../../components/Checkbox";
import {
  addEventParticipant,
  cancelEvent,
  createEvent,
  getEvent,
  removeEventParticipant,
  respondToEvent,
  updateEvent,
} from "../../api/client";
import type { CalendarEventDetail, User } from "../../types/watodo";
import { isoToLocalInput, localInputToIso } from "./calendarMath";
import { RecurrenceEditor } from "./RecurrenceEditor";
import { buildRrule, describeRrule, EMPTY_RECURRENCE, parseRrule, type RecurrenceForm } from "./recurrence";

interface EventDialogProps {
  /** "create" avec des dates pré-remplies, ou "edit" d'un événement existant. */
  mode: "create" | "edit";
  eventId?: string;
  initialStart?: string;
  initialEnd?: string;
  assignableUsers: User[];
  onClose: () => void;
  onSaved: () => void;
}

function displayName(user: { first_name: string; last_name: string; username: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function EventDialog({
  mode,
  eventId,
  initialStart,
  initialEnd,
  assignableUsers,
  onClose,
  onSaved,
}: EventDialogProps) {
  const [detail, setDetail] = useState<CalendarEventDetail | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [location, setLocation] = useState("");
  const [start, setStart] = useState(initialStart ? isoToLocalInput(initialStart) : "");
  const [end, setEnd] = useState(initialEnd ? isoToLocalInput(initialEnd) : "");
  const [allDay, setAllDay] = useState(false);
  const [recurrence, setRecurrence] = useState<RecurrenceForm>(EMPTY_RECURRENCE);
  const [participantToAdd, setParticipantToAdd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const readOnly = mode === "edit" && detail !== null && !detail.permissions.can_edit;
  const isParticipant = detail !== null && !detail.is_owner;

  useEffect(() => {
    if (mode !== "edit" || !eventId) return;
    let cancelled = false;
    getEvent(eventId)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setTitle(data.title);
        setDescription(data.description);
        setLocation(data.location);
        setStart(isoToLocalInput(data.start));
        setEnd(isoToLocalInput(data.end));
        setAllDay(data.all_day);
        setRecurrence(parseRrule(data.recurrence_rule));
      })
      .catch(() => setError("Impossible de charger l'événement."));
    return () => {
      cancelled = true;
    };
  }, [mode, eventId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim() || !start || !end) {
      setError("Titre, début et fin sont obligatoires.");
      return;
    }
    const payload = {
      title: title.trim(),
      description,
      location,
      start: localInputToIso(start),
      end: localInputToIso(end),
      all_day: allDay,
      recurrence_rule: buildRrule(recurrence),
    };
    setBusy(true);
    try {
      if (mode === "create") {
        await createEvent(payload);
      } else if (eventId) {
        await updateEvent(eventId, payload);
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelEvent() {
    if (!eventId) return;
    setBusy(true);
    try {
      await cancelEvent(eventId);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Annulation impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function handleAddParticipant() {
    if (!eventId || !participantToAdd) return;
    try {
      setDetail(await addEventParticipant(eventId, participantToAdd));
      setParticipantToAdd("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ajout impossible.");
    }
  }

  async function handleRemoveParticipant(participantId: string) {
    if (!eventId) return;
    try {
      await removeEventParticipant(eventId, participantId);
      setDetail(await getEvent(eventId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retrait impossible.");
    }
  }

  async function handleRespond(response: "accepte" | "refuse") {
    if (!eventId) return;
    try {
      setDetail(await respondToEvent(eventId, response));
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Réponse impossible.");
    }
  }

  const existingParticipantIds = new Set((detail?.participants ?? []).map((p) => p.user.id));
  const pickable = assignableUsers.filter(
    (u) => u.account_type === "interne" && !existingParticipantIds.has(u.id) && u.id !== detail?.owner.id,
  );

  return (
    <div className="planning-dialog__overlay" onClick={onClose}>
      <div className="planning-dialog" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="planning-dialog__header">
          <h2>{mode === "create" ? "Nouvel événement" : readOnly ? "Événement" : "Modifier l'événement"}</h2>
          <button type="button" className="planning-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {error && <p className="planning-dialog__error">{error}</p>}

        {readOnly && detail ? (
          <div className="planning-dialog__body">
            <p className="planning-dialog__readonly-title">{detail.title}</p>
            <p className="planning-dialog__readonly-meta">
              {new Date(detail.start).toLocaleString("fr-FR")} → {new Date(detail.end).toLocaleString("fr-FR")}
            </p>
            {detail.location && <p className="planning-dialog__readonly-meta">Lieu : {detail.location}</p>}
            {detail.is_recurring && (
              <p className="planning-dialog__readonly-meta">{describeRrule(detail.recurrence_rule)}</p>
            )}
            {detail.description && <p className="planning-dialog__readonly-desc">{detail.description}</p>}
            <p className="planning-dialog__readonly-meta">Organisé par {displayName(detail.owner)}</p>
            {isParticipant && (
              <div className="planning-dialog__respond">
                <span>Votre réponse :</span>
                <button
                  type="button"
                  className="planning-btn planning-btn--primary"
                  onClick={() => handleRespond("accepte")}
                >
                  Accepter
                </button>
                <button type="button" className="planning-btn" onClick={() => handleRespond("refuse")}>
                  Refuser
                </button>
              </div>
            )}
          </div>
        ) : (
          <form className="planning-dialog__body" onSubmit={handleSubmit}>
            <label className="planning-field">
              <span>Titre</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus required />
            </label>

            <div className="planning-field-row">
              <label className="planning-field">
                <span>Début</span>
                <input
                  type="datetime-local"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  required
                />
              </label>
              <label className="planning-field">
                <span>Fin</span>
                <input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} required />
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

            <RecurrenceEditor value={recurrence} onChange={setRecurrence} />

            {mode === "edit" && detail && (
              <div className="planning-dialog__participants">
                <span className="planning-field-label">Participants</span>
                <ul>
                  {detail.participants.map((p) => (
                    <li key={p.id}>
                      <span>{displayName(p.user)}</span>
                      <span className="planning-dialog__participant-status">{p.response_display}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveParticipant(p.id)}
                        aria-label="Retirer"
                      >
                        <X size={13} strokeWidth={1.75} aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                  {detail.participants.length === 0 && <li className="planning-dialog__muted">Aucun participant</li>}
                </ul>
                <div className="planning-field-row">
                  <select value={participantToAdd} onChange={(e) => setParticipantToAdd(e.target.value)}>
                    <option value="">Ajouter un participant…</option>
                    {pickable.map((u) => (
                      <option key={u.id} value={u.id}>
                        {displayName(u)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="planning-btn"
                    onClick={handleAddParticipant}
                    disabled={!participantToAdd}
                  >
                    Ajouter
                  </button>
                </div>
              </div>
            )}

            <div className="planning-dialog__footer">
              {mode === "edit" && (
                <button
                  type="button"
                  className="planning-btn planning-btn--danger"
                  onClick={handleCancelEvent}
                  disabled={busy}
                >
                  Annuler l'événement
                </button>
              )}
              <span className="planning-dialog__footer-spacer" />
              <button type="button" className="planning-btn" onClick={onClose} disabled={busy}>
                Fermer
              </button>
              <button type="submit" className="planning-btn planning-btn--primary" disabled={busy}>
                {mode === "create" ? "Créer" : "Enregistrer"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
