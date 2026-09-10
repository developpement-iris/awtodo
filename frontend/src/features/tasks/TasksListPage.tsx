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
import { Combobox } from "../../components/Combobox";
import { InlineEditableText } from "../../components/InlineEditableText";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonTable } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { StatusFilterDropdown } from "../../components/StatusFilterDropdown";
import { TypeBadge } from "../../components/TypeBadge";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import { priorityTone, statusTone, taskStatusIcon } from "../../lib/badges";
import { defaultStatusSelection, TASK_STATUS_FILTER_OPTIONS } from "../../lib/statusFilterOptions";
import type { AuditLogEntry, Project, Task, TaskComment, Team } from "../../types/watodo";
import { CompleteDialog } from "./CompleteDialog";
import { RejectDialog } from "./RejectDialog";
import { TaskAccordion } from "./TaskAccordion";
import { useTaskTransitions } from "./useTaskTransitions";
import "./TasksListPage.css";

type Mode = "mine" | "team";

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
    setExpandedTaskId(focusTaskId);
    const timeout = window.setTimeout(() => {
      document.getElementById(`task-row-${focusTaskId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    return () => window.clearTimeout(timeout);
  }, [focusTaskId]);

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
              Tâches de mon groupe
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
                  <th>Réf.</th>
                  <th>Type</th>
                  <th>Statut</th>
                  <th>Priorité</th>
                  <th>Assigné à</th>
                  <th>Projet</th>
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
                      <td>
                        {task.external_reference_id && (
                          <span className="tasks-list-page__ref">{task.external_reference_id}</span>
                        )}
                      </td>
                      <td>
                        <TypeBadge type={task.task_type} label={task.task_type_display} />
                      </td>
                      <td>
                        <StatusBadge label={task.status_display} tone={statusTone(task.status)} icon={taskStatusIcon(task.status)} />
                      </td>
                      <td>
                        <StatusBadge label={task.priority_display} tone={priorityTone(task.priority)} />
                      </td>
                      <td>
                        {task.assignee
                          ? `${task.assignee.first_name} ${task.assignee.last_name}`.trim() || task.assignee.username
                          : <span className="tasks-list-page__empty-cell">Non assignée</span>}
                      </td>
                      <td>{projectNameById.get(task.project) ?? "—"}</td>
                    </tr>
                    {mode === "mine" && expandedTaskId === task.id && (
                      <tr className="tasks-list-page__accordion-row">
                        <td colSpan={7}>
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
