import { motion } from "motion/react";
import { useState } from "react";
import { Combobox } from "../../components/Combobox";
import type { Incident, Project } from "../../types/watodo";
import "./IncidentCreateDialog.css";

const PRIORITY_OPTIONS: { value: Incident["priority"]; label: string }[] = [
  { value: "basse", label: "Basse" },
  { value: "moyenne", label: "Moyenne" },
  { value: "haute", label: "Haute" },
  { value: "critique", label: "Critique" },
];

export interface IncidentCreateFormValues {
  project: string;
  title: string;
  description: string;
  priority: Incident["priority"];
  external_reference_id: string;
}

interface IncidentCreateDialogProps {
  projects: Project[];
  defaultProjectId?: string;
  onCancel: () => void;
  onSubmit: (values: IncidentCreateFormValues) => void;
  submitting?: boolean;
  error?: string | null;
}

export function IncidentCreateDialog({
  projects,
  defaultProjectId,
  onCancel,
  onSubmit,
  submitting = false,
  error = null,
}: IncidentCreateDialogProps) {
  const [values, setValues] = useState<IncidentCreateFormValues>({
    project: defaultProjectId ?? projects[0]?.id ?? "",
    title: "",
    description: "",
    priority: "moyenne",
    external_reference_id: "",
  });

  const isValid = values.project.trim().length > 0 && values.title.trim().length > 0;

  function update<K extends keyof IncidentCreateFormValues>(key: K, value: IncidentCreateFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="incident-create-dialog__overlay" onClick={onCancel}>
      <div className="incident-create-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="incident-create-dialog__title">Signaler un incident</h2>

        <div className="incident-create-dialog__grid">
          <label className="incident-create-dialog__field">
            <span>Projet</span>
            <Combobox
              options={projects.map((project) => ({ value: project.id, label: project.name }))}
              value={values.project}
              onChange={(value) => update("project", value)}
              placeholder="Choisir un projet"
              searchPlaceholder="Rechercher un projet…"
            />
          </label>

          <label className="incident-create-dialog__field">
            <span>Priorité</span>
            <Combobox
              options={PRIORITY_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
              value={values.priority}
              onChange={(value) => update("priority", value as Incident["priority"])}
              clearable={false}
            />
          </label>

          <label className="incident-create-dialog__field incident-create-dialog__field--full">
            <span>Titre</span>
            <input type="text" value={values.title} onChange={(event) => update("title", event.target.value)} autoFocus />
          </label>

          <label className="incident-create-dialog__field incident-create-dialog__field--full">
            <span>Description</span>
            <textarea
              rows={3}
              value={values.description}
              onChange={(event) => update("description", event.target.value)}
            />
          </label>

          <label className="incident-create-dialog__field incident-create-dialog__field--full">
            <span>Référence externe (ticket)</span>
            <input
              type="text"
              className="incident-create-dialog__mono"
              placeholder="ex. TCK-88231 — laisser vide si aucune"
              value={values.external_reference_id}
              onChange={(event) => update("external_reference_id", event.target.value)}
            />
          </label>
        </div>

        {error && <p className="incident-create-dialog__error">{error}</p>}

        <div className="incident-create-dialog__actions">
          <motion.button
            type="button"
            className="incident-create-dialog__cancel"
            onClick={onCancel}
            disabled={submitting}
            whileTap={{ scale: 0.96 }}
          >
            Annuler
          </motion.button>
          <motion.button
            type="button"
            className="incident-create-dialog__confirm"
            disabled={!isValid || submitting}
            onClick={() => onSubmit(values)}
            whileTap={{ scale: 0.96 }}
          >
            {submitting ? "Signalement…" : "Signaler l'incident"}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
