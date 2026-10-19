import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Combobox } from "../../components/Combobox";
import { DatePickerField } from "../../components/DatePickerField";
import { PERSONAL_SCOPE, taskTypeOptions, useTaskTypes } from "../../hooks/useTaskTypes";
import type { Project, Task, User } from "../../types/watodo";
import "./TaskCreateDialog.css";

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
  /** Propose « Aucun projet » (tâche personnelle) dans le sélecteur de projet
   * — écran Tâches global uniquement, pas le Kanban d'un projet. */
  allowPersonal?: boolean;
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
  allowPersonal = false,
  onCancel,
  onSubmit,
  submitting = false,
  error = null,
}: TaskCreateDialogProps) {
  const [values, setValues] = useState<TaskCreateFormValues>({
    project: defaultProjectId ?? (allowPersonal ? "" : (projects[0]?.id ?? "")),
    title: "",
    description: "",
    task_type: "",
    priority: "moyenne",
    deadline: "",
    external_reference_id: "",
    assignee: defaultAssigneeId ?? "",
    estimated_hours: "",
  });

  // Types du groupe du projet choisi (sinon ceux du projet lui-même) —
  // personnalisables depuis le 2026-10-09. Changer de projet peut changer la
  // liste : on retombe alors sur son premier type.
  const isPersonal = allowPersonal && !values.project;
  const taskTypes = useTaskTypes(isPersonal ? PERSONAL_SCOPE : values.project || null);
  useEffect(() => {
    if (taskTypes.length > 0 && !taskTypes.some((t) => t.key === values.task_type)) {
      setValues((current) => ({ ...current, task_type: taskTypes[0].key }));
    }
  }, [taskTypes, values.task_type]);

  // Membres du projet choisi : la liste reçue (`users`) quand le dialogue est
  // ouvert depuis un projet, sinon déduite du projet sélectionné.
  const assignableUsers = allowPersonal
    ? (projects.find((p) => p.id === values.project)?.members.map((m) => m.user) ?? [])
    : users;

  const isValid =
    (isPersonal || values.project.trim().length > 0) &&
    values.title.trim().length > 0 &&
    values.task_type.length > 0;

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
              options={[
                ...(allowPersonal ? [{ value: "", label: "Aucun — tâche personnelle" }] : []),
                ...projects.map((project) => ({ value: project.id, label: project.name })),
              ]}
              value={values.project}
              onChange={(value) => setValues((current) => ({ ...current, project: value, assignee: "" }))}
              placeholder={allowPersonal ? "Aucun — tâche personnelle" : "Choisir un projet"}
              searchPlaceholder="Rechercher un projet…"
              clearable={!allowPersonal}
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
              options={taskTypeOptions(taskTypes)}
              value={values.task_type}
              onChange={(value) => update("task_type", value)}
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

          {isPersonal ? (
            <div className="task-create-dialog__field">
              <span>Assigné à</span>
              <p className="task-create-dialog__hint">Vous — visible par vous seul.</p>
            </div>
          ) : (
            <label className="task-create-dialog__field">
              <span>Assigné à</span>
              <Combobox
                options={[
                  { value: "", label: "Non assignée" },
                  ...assignableUsers.map((user) => ({ value: user.id, label: displayName(user) })),
                ]}
                value={values.assignee}
                onChange={(value) => update("assignee", value)}
                placeholder="Non assignée"
                searchPlaceholder="Rechercher un nom…"
              />
            </label>
          )}

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
