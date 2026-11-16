import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { saveProjectPhases } from "../../api/client";
import { DatePickerField } from "../../components/DatePickerField";
import { useToast } from "../../context/ToastContext";
import type { Project } from "../../types/watodo";
import { formatProjectDate } from "./projectDisplay";
import "./ProjectPhasesEditor.css";

interface Row {
  key: string;
  id?: string;
  name: string;
  due_date: string;
}

let nextKey = 0;

function rowsFrom(project: Project): Row[] {
  return project.phases.map((phase) => ({ key: phase.id, id: phase.id, name: phase.name, due_date: phase.due_date }));
}

interface ProjectPhasesEditorProps {
  project: Project;
  onUpdated: (project: Project) => void;
}

/**
 * Phases personnalisées du projet (session du 2026-11-16), saisies par le chef
 * de projet : un nom et une échéance par phase. Une phase commence le lendemain
 * de la précédente (la première à la création du projet) ; elles sont dessinées
 * sur la feuille de route et donnent la « phase en cours » du projet.
 */
export function ProjectPhasesEditor({ project, onUpdated }: ProjectPhasesEditorProps) {
  const { showToast } = useToast();
  const [rows, setRows] = useState<Row[]>(() => rowsFrom(project));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRows(rowsFrom(project));
    // Réinitialisé au changement de projet seulement, pour ne pas écraser une saisie en cours.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  const saved = JSON.stringify(rowsFrom(project).map(({ id, name, due_date }) => ({ id, name, due_date })));
  const current = JSON.stringify(rows.map(({ id, name, due_date }) => ({ id, name, due_date })));
  const dirty = saved !== current;
  const periodById = new Map(project.phases.map((phase) => [phase.id, phase]));

  function update(key: string, changes: Partial<Row>) {
    setRows((list) => list.map((row) => (row.key === key ? { ...row, ...changes } : row)));
  }

  function addRow() {
    nextKey += 1;
    setRows((list) => [...list, { key: `new-${nextKey}`, name: "", due_date: "" }]);
  }

  async function handleSave() {
    if (rows.some((row) => !row.name.trim())) {
      setError("Chaque phase doit avoir un nom.");
      return;
    }
    if (rows.some((row) => !row.due_date)) {
      setError("Chaque phase doit avoir une échéance.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await saveProjectPhases(
        project.id,
        rows.map((row) => ({ ...(row.id ? { id: row.id } : {}), name: row.name.trim(), due_date: row.due_date })),
      );
      onUpdated(updated);
      setRows(rowsFrom(updated));
      showToast("Phases enregistrées.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'enregistrement a échoué.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="project-phases">
      <div className="project-phases__head">
        <h3>Phases du projet</h3>
        {project.current_phase && (
          <span className="project-phases__current">
            En cours : <strong>{project.current_phase.name}</strong>
          </span>
        )}
      </div>
      <p className="project-phases__hint">
        Donnez à chaque phase un nom et une échéance. Une phase commence le lendemain de la précédente ; elles sont
        rangées par date à l'enregistrement et s'affichent sur la feuille de route.
      </p>

      {rows.length === 0 ? (
        <p className="project-phases__empty">Aucune phase pour l'instant.</p>
      ) : (
        <ol className="project-phases__list">
          {rows.map((row, index) => {
            const period = row.id ? periodById.get(row.id) : undefined;
            const unchanged = period && period.due_date === row.due_date;
            return (
              <li key={row.key} className="project-phases__row">
                <span className="project-phases__index">{index + 1}</span>
                <input
                  type="text"
                  value={row.name}
                  maxLength={80}
                  placeholder="Nom de la phase (ex. Cadrage)"
                  aria-label={`Nom de la phase ${index + 1}`}
                  onChange={(event) => update(row.key, { name: event.target.value })}
                />
                <div className="project-phases__date">
                  <DatePickerField value={row.due_date} onChange={(value) => update(row.key, { due_date: value })} placeholder="Échéance" />
                </div>
                <span className="project-phases__period">
                  {unchanged ? `du ${formatProjectDate(period.start_date, true)} au ${formatProjectDate(period.due_date, true)}` : ""}
                </span>
                <button
                  type="button"
                  className="project-phases__remove"
                  onClick={() => setRows((list) => list.filter((item) => item.key !== row.key))}
                  aria-label={`Retirer la phase ${row.name || index + 1}`}
                  title="Retirer"
                >
                  <X size={14} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ol>
      )}

      <button type="button" className="project-phases__add" onClick={addRow}>
        <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
        Ajouter une phase
      </button>

      {error && <p className="project-phases__error">{error}</p>}

      <div className="project-phases__actions">
        <button type="button" className="project-phases__cancel" onClick={() => setRows(rowsFrom(project))} disabled={!dirty || saving}>
          Annuler
        </button>
        <button type="button" className="project-phases__save" onClick={() => void handleSave()} disabled={!dirty || saving}>
          {saving ? "Enregistrement…" : "Enregistrer les phases"}
        </button>
      </div>
    </section>
  );
}
