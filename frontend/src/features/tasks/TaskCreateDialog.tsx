import { motion } from "motion/react";
import { useState } from "react";
import { DatePickerField } from "../../components/DatePickerField";
import type { Project, Task, User } from "../../types/watodo";
import "./TaskCreateDialog.css";

const TASK_TYPE_OPTIONS: { value: Task["task_type"]; label: string }[] = [
  { value: "correction", label: "Correction" },
  { value: "ajout", label: "Ajout" },
  { value: "evolution", label: "Évolution" },
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
    assignee: "",
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
            <select value={values.project} onChange={(event) => update("project", event.target.value)}>
              <option value="" disabled>
                Choisir un projet
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
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
            <select
              value={values.task_type}
              onChange={(event) => update("task_type", event.target.value as Task["task_type"])}
            >
              {TASK_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="task-create-dialog__field">
            <span>Priorité</span>
            <select
              value={values.priority}
              onChange={(event) => update("priority", event.target.value as Task["priority"])}
            >
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
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
            <select value={values.assignee} onChange={(event) => update("assignee", event.target.value)}>
              <option value="">Non assignée</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {displayName(user)}
                </option>
              ))}
            </select>
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
