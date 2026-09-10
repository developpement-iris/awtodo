import { X } from "lucide-react";
import { useState } from "react";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import { DateTimeField } from "../../components/DateTimeField";
import {
  cancelProjectPlanningEntry,
  createProjectPlanningEntry,
  updateProjectPlanningEntry,
} from "../../api/client";
import type { ProjectPlanningKind, ProjectPlanningOccurrence, User } from "../../types/watodo";
import { isoToLocalInput, localInputToIso } from "./calendarMath";
import { RecurrenceEditor } from "./RecurrenceEditor";
import { buildRrule, EMPTY_RECURRENCE, parseRrule, type RecurrenceForm } from "./recurrence";

const KIND_OPTIONS: { value: ProjectPlanningKind; label: string }[] = [
  { value: "jalon", label: "Jalon" },
  { value: "phase", label: "Phase" },
  { value: "reunion", label: "Réunion" },
  { value: "autre", label: "Autre" },
];

interface ProjectEntryDialogProps {
  projectId: string;
  members: User[];
  entry?: ProjectPlanningOccurrence;
  initialStart?: string;
  initialEnd?: string;
  onClose: () => void;
  onSaved: () => void;
}

function displayName(user: { first_name: string; last_name: string; username: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function ProjectEntryDialog({
  projectId,
  members,
  entry,
  initialStart,
  initialEnd,
  onClose,
  onSaved,
}: ProjectEntryDialogProps) {
  const editing = Boolean(entry);
  const [title, setTitle] = useState(entry?.title ?? "");
  const [description, setDescription] = useState(entry?.description ?? "");
  const [kind, setKind] = useState<ProjectPlanningKind>(entry?.kind ?? "autre");
  const [start, setStart] = useState(
    isoToLocalInput(entry?.start ?? initialStart ?? new Date().toISOString()),
  );
  const [end, setEnd] = useState(isoToLocalInput(entry?.end ?? initialEnd ?? new Date().toISOString()));
  const [allDay, setAllDay] = useState(entry?.all_day ?? false);
  const [assignee, setAssignee] = useState(entry?.assignee?.id ?? "");
  const [recurrence, setRecurrence] = useState<RecurrenceForm>(
    entry ? parseRrule(entry.recurrence_rule) : EMPTY_RECURRENCE,
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
      kind,
      start: localInputToIso(start),
      end: localInputToIso(end),
      all_day: allDay,
      assignee: assignee || null,
      recurrence_rule: buildRrule(recurrence),
    };
    setBusy(true);
    try {
      if (editing && entry) {
        await updateProjectPlanningEntry(projectId, entry.id, payload);
      } else {
        await createProjectPlanningEntry(projectId, payload);
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancelEntry() {
    if (!entry) return;
    setBusy(true);
    try {
      await cancelProjectPlanningEntry(projectId, entry.id);
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
          <h2>{editing ? "Modifier l'entrée" : "Nouvelle entrée de planning"}</h2>
          <button type="button" className="planning-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {error && <p className="planning-dialog__error">{error}</p>}

        <form className="planning-dialog__body" onSubmit={handleSubmit}>
          <label className="planning-field">
            <span>Titre</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus required />
          </label>

          <div className="planning-field-row">
            <label className="planning-field">
              <span>Type</span>
              <Combobox
                options={KIND_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                value={kind}
                onChange={(v) => setKind(v as ProjectPlanningKind)}
                clearable={false}
              />
            </label>
            <label className="planning-field">
              <span>Assigné à</span>
              <Combobox
                options={[
                  { value: "", label: "Personne" },
                  ...members.map((u) => ({ value: u.id, label: displayName(u) })),
                ]}
                value={assignee}
                onChange={setAssignee}
                placeholder="Personne"
                searchPlaceholder="Rechercher un nom…"
              />
            </label>
          </div>

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
            <span>Description</span>
            <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>

          <RecurrenceEditor value={recurrence} onChange={setRecurrence} />

          <div className="planning-dialog__footer">
            {editing && (
              <button
                type="button"
                className="planning-btn planning-btn--danger"
                onClick={handleCancelEntry}
                disabled={busy}
              >
                Annuler l'entrée
              </button>
            )}
            <span className="planning-dialog__footer-spacer" />
            <button type="button" className="planning-btn" onClick={onClose} disabled={busy}>
              Fermer
            </button>
            <button type="submit" className="planning-btn planning-btn--primary" disabled={busy}>
              {editing ? "Enregistrer" : "Créer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
