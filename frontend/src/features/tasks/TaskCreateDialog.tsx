import { motion } from "motion/react";
import { useState } from "react";
import { Combobox } from "../../components/Combobox";
import { DatePickerField } from "../../components/DatePickerField";
import type { Project, Task, User } from "../../types/watodo";
import "./TaskCreateDialog.css";

const TASK_TYPE_OPTIONS: { value: Task["task_type"]; label: string }[] = [
  { value: "correction", label: "Correction" },
  { value: "ajout", label: "Ajout" },
  { value: "evolution", label: "Évolution" },
  { value: "test", label: "Test" },
];

const PRIORITY_OPTIONS: { value: Task["priority"]; label: string }[] = [
  { value: "basse", label: "Basse" },
  { value: "moyenne", label: "Moyenne" },
  { value: "haute", label: "Haute" },
  { value: "critique", label: "Critique" },
];

export interface TaskCreateFormValues {
  project: string;
  title: string;
  description: string;
  task_type: Task["task_type"];
  priority: Task["priority"];
  deadline: string;
  external_reference_id: string;
  assignee: string;
  estimated_hours: string;
}

interface TaskCreateDialogProps {
  projects: Project[];
  users: User[];
  defaultProjectId?: string;
  /** Assigné pré-rempli à l'ouverture — sur un projet individuel, le chef de
   * projet appelant passe son propre id (voir `KanbanBoard`) : la tâche lui
   * revient de toute façon automatiquement côté backend si le champ reste
   * vide, mais le laisser sur "Non assignée" à l'écran donne l'impression
   * (à tort) que l'auto-assignation ne fonctionne pas. */
  defaultAssigneeId?: string;
  onCancel: () => void;
  onSubmit: (values: TaskCreateFormValues) => void;
  submitting?: boolean;
  error?: string | null;
}

function displayName(user: User): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function TaskCreateDialog({
  projects,
  users,
  defaultProjectId,
  defaultAssigneeId,
  onCancel,
  onSubmit,
  submitting = false,
  error = null,
}: TaskCreateDialogProps) {
  const [values, setValues] = useState<TaskCreateFormValues>({
    project: defaultProjectId ?? projects[0]?.id ?? "",
    title: "",
    description: "",
    task_type: "correction",
    priority: "moyenne",
    deadline: "",
    external_reference_id: "",
    assignee: defaultAssigneeId ?? "",
    estimated_hours: "",
  });

  const isValid = values.project.trim().length > 0 && values.title.trim().length > 0;

  function update<K extends keyof TaskCreateFormValues>(key: K, value: TaskCreateFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="task-create-dialog__overlay" onClick={onCancel}>
      <div className="task-create-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="task-create-dialog__title">Nouvelle tâche</h2>

        <div className="task-create-dialog__grid">
          <label className="task-create-dialog__field">
            <span>Projet</span>
            <Combobox
              options={projects.map((project) => ({ value: project.id, label: project.name }))}
              value={values.project}
              onChange={(value) => update("project", value)}
              placeholder="Choisir un projet"
              searchPlaceholder="Rechercher un projet…"
            />
          </label>

          <label className="task-create-dialog__field">
            <span>Titre</span>
            <input
              type="text"
              value={values.title}
              onChange={(event) => update("title", event.target.value)}
              autoFocus
            />
          </label>

          <label className="task-create-dialog__field task-create-dialog__field--full">
            <span>Description</span>
            <textarea
              rows={3}
              value={values.description}
              onChange={(event) => update("description", event.target.value)}
            />
          </label>

          <label className="task-create-dialog__field">
            <span>Type</span>
            <Combobox
              options={TASK_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
              value={values.task_type}
              onChange={(value) => update("task_type", value as Task["task_type"])}
              clearable={false}
            />
          </label>

          <label className="task-create-dialog__field">
            <span>Priorité</span>
            <Combobox
              options={PRIORITY_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
              value={values.priority}
              onChange={(value) => update("priority", value as Task["priority"])}
              clearable={false}
            />
          </label>

          <label className="task-create-dialog__field">
            <span>Échéance</span>
            <DatePickerField value={values.deadline} onChange={(value) => update("deadline", value)} />
          </label>

          <label className="task-create-dialog__field">
            <span>Temps estimé (heures)</span>
            <input
              type="number"
              min="0"
              step="0.5"
              value={values.estimated_hours}
              onChange={(event) => update("estimated_hours", event.target.value)}
            />
          </label>

          <label className="task-create-dialog__field">
            <span>Assigné à</span>
            <Combobox
              options={[
                { value: "", label: "Non assignée" },
                ...users.map((user) => ({ value: user.id, label: displayName(user) })),
              ]}
              value={values.assignee}
              onChange={(value) => update("assignee", value)}
              placeholder="Non assignée"
              searchPlaceholder="Rechercher un nom…"
            />
          </label>

          <label className="task-create-dialog__field task-create-dialog__field--full">
            <span>Référence externe (ticket)</span>
            <input
              type="text"
              className="task-create-dialog__mono"
              placeholder="ex. TCK-88231 — laisser vide si aucune"
              value={values.external_reference_id}
              onChange={(event) => update("external_reference_id", event.target.value)}
            />
          </label>
        </div>

        {error && <p className="task-create-dialog__error">{error}</p>}

        <div className="task-create-dialog__actions">
          <motion.button
            type="button"
            className="task-create-dialog__cancel"
            onClick={onCancel}
            disabled={submitting}
            whileTap={{ scale: 0.96 }}
          >
            Annuler
          </motion.button>
          <motion.button
            type="button"
            className="task-create-dialog__confirm"
            disabled={!isValid || submitting}
            onClick={() => onSubmit(values)}
            whileTap={{ scale: 0.96 }}
          >
            {submitting ? "Création…" : "Créer la tâche"}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
