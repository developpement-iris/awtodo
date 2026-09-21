import { AnimatePresence } from "motion/react";
import { Fragment, useEffect, useState } from "react";
import {
  addTaskComment,
  getProjects,
  getTask,
  getTasks,
  getTeams,
  renameTask,
  updateTaskDescription,
  updateTaskEstimatedHours,
} from "../../api/client";
import { ColumnPicker, type ColumnDef } from "../../components/ColumnPicker";
import { Combobox } from "../../components/Combobox";
import { InlineEditableText } from "../../components/InlineEditableText";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonTable } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { StatusFilterDropdown } from "../../components/StatusFilterDropdown";
import { TypeBadge } from "../../components/TypeBadge";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import { useColumnPreferences } from "../../hooks/useColumnPreferences";
import { priorityTone, statusTone, taskStatusIcon } from "../../lib/badges";
import { defaultStatusSelection, TASK_STATUS_FILTER_OPTIONS } from "../../lib/statusFilterOptions";
import type { AuditLogEntry, Project, Task, TaskComment, Team } from "../../types/watodo";
import { CompleteDialog } from "./CompleteDialog";
import { RejectDialog } from "./RejectDialog";
import { TaskAccordion } from "./TaskAccordion";
import { useTaskTransitions } from "./useTaskTransitions";
import "./TasksListPage.css";

type Mode = "mine" | "team";

// Colonnes personnalisables (session du 2026-09-18) — "Titre" reste
// obligatoire (identifiant primaire de la ligne, édition inline), les autres
// sont optionnelles et mémorisées en cache local par utilisateur (voir
// `useColumnPreferences`). Les 6 premières sont visibles par défaut
// (comportement inchangé pour qui n'a jamais rien réglé) ; échéance/temps
// estimé/temps passé/version, ajoutées après coup (retour direct : "il
// manque des critères, par exemple date d'échéance"), démarrent masquées
// pour ne pas surcharger un tableau déjà réglé — l'utilisateur les active
// lui-même via le sélecteur de colonnes.
type TaskColumnKey =
  | "ref"
  | "type"
  | "status"
  | "priority"
  | "assignee"
  | "project"
  | "deadline"
  | "estimated_hours"
  | "time_spent"
  | "version";

const TASK_COLUMNS: ColumnDef<TaskColumnKey>[] = [
  { key: "ref", label: "Réf." },
  { key: "type", label: "Type" },
  { key: "status", label: "Statut" },
  { key: "priority", label: "Priorité" },
  { key: "assignee", label: "Assigné à" },
  { key: "project", label: "Projet" },
  { key: "deadline", label: "Échéance" },
  { key: "estimated_hours", label: "Temps estimé" },
  { key: "time_spent", label: "Temps passé" },
  { key: "version", label: "Version" },
];
const TASK_COLUMN_KEYS = TASK_COLUMNS.map((c) => c.key);
const TASK_COLUMNS_DEFAULT_VISIBLE: TaskColumnKey[] = [
  "ref",
  "type",
  "status",
  "priority",
  "assignee",
  "project",
];

function formatDeadline(deadline: string | null): string {
  if (!deadline) return "—";
  return new Date(deadline).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

function formatHours(value: string | null): string {
  if (!value) return "—";
  return `${value} h`;
}

interface TasksListPageProps {
  /** Depuis une notification "tâche" : ouvre directement cette tâche et
   * l'amène à l'écran, symétrique à `focusIncidentId` sur `IncidentsPage`. */
  focusTaskId?: string;
}

export function TasksListPage({ focusTaskId }: TasksListPageProps = {}) {
  const { currentUser } = useCurrentUser();
  const { showToast } = useToast();
  const [mode, setMode] = useState<Mode>("mine");
  const [selectedTeam, setSelectedTeam] = useState<string>("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [comments, setComments] = useState<TaskComment[] | null>(null);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [statusFilter, setStatusFilter] = useState(() => defaultStatusSelection(TASK_STATUS_FILTER_OPTIONS));
  const [visibleColumns, setVisibleColumns] = useColumnPreferences<TaskColumnKey>(
    "tasks",
    TASK_COLUMN_KEYS,
    TASK_COLUMNS_DEFAULT_VISIBLE,
  );

  const myTeams = currentUser?.teams ?? [];
  const activeTeam = selectedTeam || myTeams[0] || "";

  useEffect(() => {
    setMode("mine");
    setSelectedTeam("");
  }, [currentUser?.id]);

  useEffect(() => {
    getProjects()
      .then(setProjects)
      .catch(() => undefined);
    getTeams()
      .then(setTeams)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setTasks(null);
    setError(null);

    if (mode === "mine") {
      if (!currentUser) {
        setTasks([]);
        return;
      }
      getTasks({ assignee: currentUser.id, status: Array.from(statusFilter) })
        .then((data) => {
          if (!cancelled) setTasks(data);
        })
        .catch(() => {
          if (!cancelled) setError("Impossible de charger vos tâches.");
        });
    } else {
      if (!activeTeam) {
        setTasks([]);
        return;
      }
      getTasks({ team: activeTeam, status: Array.from(statusFilter) })
        .then((data) => {
          if (!cancelled) setTasks(data.filter((task) => task.assignee?.id !== currentUser?.id));
        })
        .catch(() => {
          if (!cancelled) setError("Impossible de charger les tâches du groupe.");
        });
    }

    return () => {
      cancelled = true;
    };
  }, [mode, activeTeam, currentUser, statusFilter]);

  useEffect(() => {
    if (!focusTaskId) return;
    setMode("mine");
    // Garantit que la tâche ciblée est bien incluse dans le fetch, quel que
    // soit son statut — sans ça, une tâche archivée/rejetée (hors du filtre
    // par défaut) restait invisible malgré la navigation : la liste
    // s'ouvrait mais la tâche elle-même n'apparaissait jamais (retour direct).
    setStatusFilter(new Set(TASK_STATUS_FILTER_OPTIONS.map((o) => o.value)));
    setExpandedTaskId(focusTaskId);
  }, [focusTaskId]);

  // Le scroll n'a de sens qu'une fois la ligne effectivement présente dans le
  // DOM — un délai fixe (ancienne version) pouvait s'exécuter avant la fin du
  // fetch et échouer silencieusement (`getElementById` renvoie `null`).
  useEffect(() => {
    if (!focusTaskId || !tasks || !tasks.some((t) => t.id === focusTaskId)) return;
    const timeout = window.setTimeout(() => {
      document.getElementById(`task-row-${focusTaskId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    return () => window.clearTimeout(timeout);
  }, [focusTaskId, tasks]);

  useEffect(() => {
    if (!expandedTaskId) return;
    let cancelled = false;
    setComments(null);
    setCommentsError(null);
    setAuditLog([]);

    getTask(expandedTaskId)
      .then((data) => {
        if (!cancelled) {
          setComments(data.comments);
          setAuditLog(data.audit_log);
        }
      })
      .catch(() => {
        if (!cancelled) setCommentsError("Impossible de charger les commentaires.");
      });

    return () => {
      cancelled = true;
    };
  }, [expandedTaskId]);

  function updateTaskLocally(updated: Task) {
    setTasks((current) => (current ? current.map((task) => (task.id === updated.id ? updated : task)) : current));
  }

  function removeTaskLocally(taskId: string) {
    setTasks((current) => (current ? current.filter((task) => task.id !== taskId) : current));
    setExpandedTaskId((current) => (current === taskId ? null : current));
  }

  const {
    rejectingTask,
    setRejectingTask,
    completingTask,
    setCompletingTask,
    actionError,
    setActionError,
    pendingTaskId,
    handleValidate,
    handleClaim,
    handleAssign,
    handleStart,
    handleReject,
    handleComplete,
  } = useTaskTransitions(updateTaskLocally, removeTaskLocally, showToast);

  async function handleRename(task: Task, title: string) {
    setActionError(null);
    try {
      updateTaskLocally(await renameTask(task.id, title));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Le renommage a échoué.");
    }
  }

  async function handleSaveDescription(task: Task, description: string) {
    setActionError(null);
    try {
      updateTaskLocally(await updateTaskDescription(task.id, description));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "L'enregistrement a échoué.");
    }
  }

  async function handleSaveEstimatedHours(task: Task, value: string | null) {
    setActionError(null);
    try {
      updateTaskLocally(await updateTaskEstimatedHours(task.id, value));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "La mise à jour du temps estimé a échoué.");
    }
  }

  async function handleAddComment(content: string) {
    if (!expandedTaskId) return;
    setCommentSubmitting(true);
    setCommentsError(null);
    try {
      const comment = await addTaskComment(expandedTaskId, content);
      setComments((current) => (current ? [...current, comment] : [comment]));
    } catch (err) {
      setCommentsError(err instanceof Error ? err.message : "L'ajout du commentaire a échoué.");
    } finally {
      setCommentSubmitting(false);
    }
  }

  const projectNameById = new Map(projects.map((project) => [project.id, project.name]));
  const teamNameById = new Map(teams.map((team) => [team.id, team.name]));

  return (
    <div className="tasks-list-page">
      <div className="tasks-list-page__toolbar">
        <div className="tasks-list-page__modes" role="group" aria-label="Filtrer les tâches">
          <button
            type="button"
            className={`tasks-list-page__mode${mode === "mine" ? " tasks-list-page__mode--active" : ""}`}
            onClick={() => setMode("mine")}
          >
            Mes tâches
          </button>
          {myTeams.length > 0 && (
            <button
              type="button"
              className={`tasks-list-page__mode${mode === "team" ? " tasks-list-page__mode--active" : ""}`}
              onClick={() => setMode("team")}
            >
              Tâches de mes groupes
            </button>
          )}
        </div>

        {mode === "team" && myTeams.length > 1 && (
          <span className="tasks-list-page__team-select">
            <Combobox
              options={myTeams.map((teamId) => ({
                value: teamId,
                label: teamNameById.get(teamId) ?? teamId,
              }))}
              value={activeTeam}
              onChange={setSelectedTeam}
              clearable={false}
            />
          </span>
        )}

        <StatusFilterDropdown options={TASK_STATUS_FILTER_OPTIONS} selected={statusFilter} onChange={setStatusFilter} />
        <ColumnPicker columns={TASK_COLUMNS} visible={visibleColumns} onChange={setVisibleColumns} />
      </div>

      {!currentUser && (
        <p className="tasks-list-page__message">
          Choisissez un utilisateur (menu en haut à droite) pour voir vos tâches.
        </p>
      )}

      {actionError && <p className="tasks-list-page__message tasks-list-page__message--error">{actionError}</p>}
      {error && <p className="tasks-list-page__message tasks-list-page__message--error">{error}</p>}

      {currentUser && !error && (
        <LoadingTransition loading={tasks === null} skeleton={<SkeletonTable columns={7} rows={5} />}>
          {tasks && tasks.length === 0 && (
            <p className="tasks-list-page__message">
              {mode === "mine" ? "Aucune tâche assignée pour l'instant." : "Aucune tâche dans ce groupe pour l'instant."}
            </p>
          )}

          {tasks && tasks.length > 0 && (
            <table className="tasks-list-page__table">
              <thead>
                <tr>
                  <th>Titre</th>
                  {visibleColumns.has("ref") && <th>Réf.</th>}
                  {visibleColumns.has("type") && <th>Type</th>}
                  {visibleColumns.has("status") && <th>Statut</th>}
                  {visibleColumns.has("priority") && <th>Priorité</th>}
                  {visibleColumns.has("assignee") && <th>Assigné à</th>}
                  {visibleColumns.has("project") && <th>Projet</th>}
                  {visibleColumns.has("deadline") && <th>Échéance</th>}
                  {visibleColumns.has("estimated_hours") && <th>Temps estimé</th>}
                  {visibleColumns.has("time_spent") && <th>Temps passé</th>}
                  {visibleColumns.has("version") && <th>Version</th>}
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <Fragment key={task.id}>
                    <tr
                      id={`task-row-${task.id}`}
                      className={mode === "mine" ? "tasks-list-page__row--clickable" : undefined}
                      onClick={
                        mode === "mine"
                          ? () => setExpandedTaskId((current) => (current === task.id ? null : task.id))
                          : undefined
                      }
                    >
                      <td>
                        <InlineEditableText
                          value={task.title}
                          onSave={(title) => handleRename(task, title)}
                          ariaLabel="Titre de la tâche"
                          disabled={mode !== "mine" || pendingTaskId === task.id || !task.permissions.can_rename}
                        />
                      </td>
                      {visibleColumns.has("ref") && (
                        <td>
                          {task.external_reference_id && (
                            <span className="tasks-list-page__ref">{task.external_reference_id}</span>
                          )}
                        </td>
                      )}
                      {visibleColumns.has("type") && (
                        <td>
                          <TypeBadge type={task.task_type} label={task.task_type_display} />
                        </td>
                      )}
                      {visibleColumns.has("status") && (
                        <td>
                          <StatusBadge label={task.status_display} tone={statusTone(task.status)} icon={taskStatusIcon(task.status)} />
                        </td>
                      )}
                      {visibleColumns.has("priority") && (
                        <td>
                          <StatusBadge label={task.priority_display} tone={priorityTone(task.priority)} />
                        </td>
                      )}
                      {visibleColumns.has("assignee") && (
                        <td>
                          {task.assignee
                            ? `${task.assignee.first_name} ${task.assignee.last_name}`.trim() || task.assignee.username
                            : <span className="tasks-list-page__empty-cell">Non assignée</span>}
                        </td>
                      )}
                      {visibleColumns.has("project") && <td>{projectNameById.get(task.project) ?? "—"}</td>}
                      {visibleColumns.has("deadline") && <td>{formatDeadline(task.deadline)}</td>}
                      {visibleColumns.has("estimated_hours") && <td>{formatHours(task.estimated_hours)}</td>}
                      {visibleColumns.has("time_spent") && <td>{formatHours(task.time_spent)}</td>}
                      {visibleColumns.has("version") && <td>{task.version_label || "—"}</td>}
                    </tr>
                    {mode === "mine" && expandedTaskId === task.id && (
                      <tr className="tasks-list-page__accordion-row">
                        <td colSpan={1 + visibleColumns.size}>
                          <AnimatePresence>
                            <TaskAccordion
                              task={task}
                              assignableUsers={
                                projects.find((project) => project.id === task.project)?.members.map((m) => m.user) ?? []
                              }
                              onClose={() => setExpandedTaskId(null)}
                              onValidate={handleValidate}
                              onReject={setRejectingTask}
                              onClaim={handleClaim}
                              onAssign={handleAssign}
                              onStart={handleStart}
                              onComplete={setCompletingTask}
                              onSaveDescription={handleSaveDescription}
                              onSaveEstimatedHours={handleSaveEstimatedHours}
                              comments={comments}
                              commentsError={commentsError}
                              commentSubmitting={commentSubmitting}
                              onAddComment={handleAddComment}
                              auditLog={auditLog}
                              pending={pendingTaskId === task.id}
                            />
                          </AnimatePresence>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </LoadingTransition>
      )}

      {rejectingTask && (
        <RejectDialog task={rejectingTask} onCancel={() => setRejectingTask(null)} onConfirm={handleReject} />
      )}
      {completingTask && (
        <CompleteDialog task={completingTask} onCancel={() => setCompletingTask(null)} onConfirm={handleComplete} />
      )}
    </div>
  );
}
