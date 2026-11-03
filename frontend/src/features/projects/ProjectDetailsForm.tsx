import { useEffect, useState } from "react";
import { updateProjectDetails, uploadProjectCover, type ProjectDetailsUpdatePayload } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import { DatePickerField } from "../../components/DatePickerField";
import { useToast } from "../../context/ToastContext";
import { PROJECT_PHASE_OPTIONS } from "../../lib/badges";
import type { Project } from "../../types/watodo";
import { CoverPicker } from "./CoverPicker";
import "./ProjectDetailsForm.css";

const PRIORITY_OPTIONS = [
  { value: "basse", label: "Basse" },
  { value: "moyenne", label: "Moyenne" },
  { value: "haute", label: "Haute" },
  { value: "critique", label: "Critique" },
];

interface FormValues {
  name: string;
  description: string;
  phase: string;
  cover_image: string;
  priority: string;
  deadline: string;
  already_in_production: boolean;
}

function valuesFrom(project: Project): FormValues {
  return {
    name: project.name,
    description: project.description,
    phase: project.phase ?? "",
    cover_image: project.cover_image,
    priority: project.priority ?? "",
    deadline: project.deadline ?? "",
    already_in_production: project.already_in_production,
  };
}

// N'envoie que les champs réellement modifiés (mise à jour partielle côté
// serveur, chaque changement journalisé dans l'historique du projet).
function diffPayload(initial: FormValues, current: FormValues): ProjectDetailsUpdatePayload {
  const payload: ProjectDetailsUpdatePayload = {};
  if (current.name !== initial.name) payload.name = current.name.trim();
  if (current.description !== initial.description) payload.description = current.description;
  if (current.phase !== initial.phase) payload.phase = (current.phase || null) as Project["phase"];
  if (current.cover_image !== initial.cover_image) payload.cover_image = current.cover_image;
  if (current.priority !== initial.priority) payload.priority = (current.priority || null) as Project["priority"];
  if (current.deadline !== initial.deadline) payload.deadline = current.deadline || null;
  if (current.already_in_production !== initial.already_in_production) {
    payload.already_in_production = current.already_in_production;
  }
  return payload;
}

interface ProjectDetailsFormProps {
  project: Project;
  onUpdated: (project: Project) => void;
}

export function ProjectDetailsForm({ project, onUpdated }: ProjectDetailsFormProps) {
  const { showToast } = useToast();
  const [values, setValues] = useState(() => valuesFrom(project));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Réinitialisé seulement au changement de projet : une mise à jour du
  // projet par ailleurs (import d'image, membre ajouté) ne doit pas effacer
  // une saisie en cours dans ce formulaire.
  useEffect(() => {
    setValues(valuesFrom(project));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  const payload = diffPayload(valuesFrom(project), values);
  const dirty = Object.keys(payload).length > 0;
  const isValid = values.name.trim().length > 0;

  function update<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  // L'import est envoyé tout de suite (pas au clic sur « Enregistrer ») : le
  // serveur bascule alors le projet sur l'image importée.
  async function handleImport(image: Blob) {
    const updated = await uploadProjectCover(project.id, image);
    onUpdated(updated);
    setValues((current) => ({ ...current, cover_image: updated.cover_image }));
    showToast("Image importée.");
  }

  async function handleSave() {
    setSubmitting(true);
    setError(null);
    try {
      const updated = await updateProjectDetails(project.id, payload);
      onUpdated(updated);
      setValues(valuesFrom(updated));
      showToast("Informations du projet enregistrées.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'enregistrement a échoué.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="project-details-form">
      <h3 className="project-details-form__title">Informations du projet</h3>

      <div className="project-details-form__grid">
        <label className="project-details-form__field project-details-form__field--full">
          <span>Nom</span>
          <input type="text" value={values.name} onChange={(event) => update("name", event.target.value)} />
        </label>

        <label className="project-details-form__field project-details-form__field--full">
          <span>Description</span>
          <textarea
            rows={3}
            value={values.description}
            onChange={(event) => update("description", event.target.value)}
          />
        </label>

        <div className="project-details-form__field project-details-form__field--full">
          <span>Image d'illustration</span>
          <CoverPicker
            project={{ id: project.id, name: values.name, cover_updated_at: project.cover_updated_at }}
            value={values.cover_image}
            onChange={(value) => update("cover_image", value)}
            onImport={handleImport}
          />
        </div>

        <label className="project-details-form__field">
          <span>Phase</span>
          <Combobox
            options={[{ value: "", label: "Non définie" }, ...PROJECT_PHASE_OPTIONS]}
            value={values.phase}
            onChange={(value) => update("phase", value)}
            placeholder="Non définie"
          />
        </label>

        <label className="project-details-form__field">
          <span>Priorité</span>
          <Combobox
            options={[{ value: "", label: "Non définie" }, ...PRIORITY_OPTIONS]}
            value={values.priority}
            onChange={(value) => update("priority", value)}
            placeholder="Non définie"
          />
        </label>

        <label className="project-details-form__field">
          <span>Échéance</span>
          <div className="project-details-form__deadline">
            <DatePickerField
              value={values.already_in_production ? "" : values.deadline}
              onChange={(value) => update("deadline", value)}
              disabled={values.already_in_production}
            />
            {values.deadline && !values.already_in_production && (
              <button
                type="button"
                className="project-details-form__clear"
                onClick={() => update("deadline", "")}
              >
                Effacer
              </button>
            )}
          </div>
        </label>

        <label className="project-details-form__field project-details-form__field--inline">
          <Checkbox
            checked={values.already_in_production}
            onCheckedChange={(checked) =>
              setValues((current) => ({
                ...current,
                already_in_production: checked,
                deadline: checked ? "" : current.deadline,
              }))
            }
            aria-label="Déjà en production"
          />
          <span>Déjà en production (pas d'échéance)</span>
        </label>
      </div>

      {error && <p className="project-details-form__error">{error}</p>}

      <div className="project-details-form__actions">
        <button
          type="button"
          className="project-details-form__cancel"
          onClick={() => setValues(valuesFrom(project))}
          disabled={!dirty || submitting}
        >
          Annuler
        </button>
        <button
          type="button"
          className="project-details-form__save"
          onClick={handleSave}
          disabled={!dirty || !isValid || submitting}
        >
          {submitting ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </section>
  );
}
