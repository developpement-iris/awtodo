import {
  DndContext,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useEffect, useState } from "react";
import {
  addTaskComment,
  createTask,
  getTask,
  getTasks,
  renameTask,
  updateTaskEstimatedHours,
  type TaskCreatePayload,
} from "../../api/client";
import { CreationCard } from "../../components/CreationCard";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonKanban } from "../../components/Skeleton";
import { StatusFilterDropdown } from "../../components/StatusFilterDropdown";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import {
  isDropAllowed,
  KANBAN_COLUMNS,
  KANBAN_COLUMN_LABELS,
  resolveDragAction,
  type KanbanStatus,
} from "../../lib/taskTransitions";
import { defaultStatusSelection, TASK_STATUS_FILTER_OPTIONS } from "../../lib/statusFilterOptions";
import type { AuditLogEntry, Project, Task, TaskComment } from "../../types/watodo";
import { CompleteDialog } from "./CompleteDialog";
import { RejectDialog } from "./RejectDialog";
import { TaskCard } from "./TaskCard";
import { TaskCreateDialog, type TaskCreateFormValues } from "./TaskCreateDialog";
import { TaskDrawer } from "./TaskDrawer";
import { useTaskTransitions } from "./useTaskTransitions";
import "./KanbanBoard.css";

function KanbanColumn({ status, tasks, onOpen, onReject, onRename, pendingTaskId, onCreate, dropDisabled }: {
  status: KanbanStatus;
  tasks: Task[];
  onOpen: (task: Task) => void;
  onReject?: (task: Task) => void;
  onRename: (task: Task, title: string) => void;
  pendingTaskId: string | null;
  onCreate?: () => void;
  dropDisabled: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status, disabled: dropDisabled });

  return (
    <div
      ref={setNodeRef}
      className={`kanban-column${isOver ? " kanban-column--over" : ""}${dropDisabled ? " kanban-column--disabled" : ""}`}
    >
      <div className="kanban-column__header">
        <span>{KANBAN_COLUMN_LABELS[status]}</span>
        <span className="kanban-column__count">{tasks.length}</span>
      </div>
      <div className="kanban-column__cards">
        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onOpen={onOpen}
            onReject={task.permissions.can_reject ? onReject : undefined}
            onRename={onRename}
            pending={pendingTaskId === task.id}
          />
        ))}
        {onCreate && <CreationCard label="Nouvelle tâche" onClick={onCreate} compact />}
      </div>
    </div>
  );
}

function buildCreatePayload(values: TaskCreateFormValues): TaskCreatePayload {
  const payload: TaskCreatePayload = {
    project: values.project,
    title: values.title.trim(),
    task_type: values.task_type,
    priority: values.priority,
  };
  if (values.description.trim()) payload.description = values.description.trim();
  if (values.deadline) payload.deadline = values.deadline;
  if (values.external_reference_id.trim()) payload.external_reference_id = values.external_reference_id.trim();
  if (values.assignee) payload.assignee = values.assignee;
  if (values.estimated_hours.trim()) payload.estimated_hours = values.estimated_hours.trim();
  return payload;
}

interface KanbanBoardProps {
  project: Project;
  /** Voir docs/modeles-et-api.md > "ProjectVersion" — sélecteur partagé avec
   * la Roadmap, possédé par `TasksTab`. `undefined` = version courante. */
  versionId?: string;
}

export function KanbanBoard({ project, versionId }: KanbanBoardProps) {
  const { currentUser } = useCurrentUser();
  const projectMembers = project.members.map((membership) => membership.user);
  const { showToast } = useToast();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openTask, setOpenTask] = useState<Task | null>(null);
  const [activeDragTask, setActiveDragTask] = useState<Task | null>(null);
  const [creatingTask, setCreatingTask] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState(() => defaultStatusSelection(TASK_STATUS_FILTER_OPTIONS));
  const [comments, setComments] = useState<TaskComment[] | null>(null);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    setTasks(null);
    setError(null);

    getTasks({ project: project.id, version: versionId, status: Array.from(statusFilter) })
      .then((data) => {
        if (!cancelled) setTasks(data);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger les tâches.");
      });

    return () => {
      cancelled = true;
    };
  }, [project.id, versionId, statusFilter]);

  useEffect(() => {
    if (!openTask?.id) return;
    let cancelled = false;
    setComments(null);
    setCommentsError(null);
    setAuditLog([]);

    getTask(openTask.id)
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
  }, [openTask?.id]);

  const visibleColumns = KANBAN_COLUMNS.filter((status) => statusFilter.has(status));

  function updateTaskLocally(updated: Task) {
    setTasks((current) => (current ? current.map((task) => (task.id === updated.id ? updated : task)) : current));
    setOpenTask((current) => (current && current.id === updated.id ? updated : current));
  }

  function removeTaskLocally(taskId: string) {
    setTasks((current) => (current ? current.filter((task) => task.id !== taskId) : current));
    setOpenTask((current) => (current && current.id === taskId ? null : current));
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

  function handleDragStart(event: DragStartEvent) {
    const task = event.active.data.current?.task as Task | undefined;
    setActiveDragTask(task ?? null);
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveDragTask(null);
    const { active, over } = event;
    if (!over) return;

    const task = active.data.current?.task as Task | undefined;
    if (!task) return;

    const toStatus = over.id as string;
    const actionKind = resolveDragAction(task.status, toStatus);
    if (!actionKind) return;

    if (!currentUser) {
      setActionError("Choisissez un utilisateur (menu en haut à droite) avant d'effectuer cette action.");
      return;
    }

    if (actionKind === "start") await handleStart(task);
    else setCompletingTask(task);
  }

  async function handleRename(task: Task, title: string) {
    try {
      updateTaskLocally(await renameTask(task.id, title));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Le renommage a échoué.");
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
    if (!openTask?.id) return;
    setCommentSubmitting(true);
    setCommentsError(null);
    try {
      const comment = await addTaskComment(openTask.id, content);
      setComments((current) => (current ? [...current, comment] : [comment]));
    } catch (err) {
      setCommentsError(err instanceof Error ? err.message : "L'ajout du commentaire a échoué.");
    } finally {
      setCommentSubmitting(false);
    }
  }

  async function handleCreate(values: TaskCreateFormValues) {
    setCreateSubmitting(true);
    setCreateError(null);

    try {
      const created = await createTask(buildCreatePayload(values));
      setCreatingTask(false);
      // La création cible toujours la version courante, quelle que soit la
      // version affichée (voir docs/modeles-et-api.md > "ProjectVersion") —
      // si l'utilisateur consultait une version passée, la tâche créée
      // n'appartient pas à ce qui est affiché : ne pas l'insérer localement
      // pour ne pas faire apparaître une tâche qui ne devrait pas être là.
      if (!versionId || created.version === versionId) {
        setTasks((current) => (current ? [...current, created] : current));
      }
      showToast("Tâche créée.");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "La création a échoué.");
    } finally {
      setCreateSubmitting(false);
    }
  }

  return (
    <div className="kanban-board">
      <div className="kanban-board__toolbar">
        <StatusFilterDropdown options={TASK_STATUS_FILTER_OPTIONS} selected={statusFilter} onChange={setStatusFilter} />
      </div>

      {actionError && <p className="kanban-board__error">{actionError}</p>}
      {error && <p className="kanban-board__error">{error}</p>}

      {!error && (
        <LoadingTransition loading={tasks === null} skeleton={<SkeletonKanban columns={visibleColumns.length} />}>
          <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
            <div
              className="kanban-board__columns"
              style={{ gridTemplateColumns: `repeat(${visibleColumns.length}, minmax(220px, 1fr))` }}
            >
              {visibleColumns.map((status) => (
                <KanbanColumn
                  key={status}
                  status={status}
                  tasks={(tasks ?? []).filter((task) => task.status === status)}
                  onOpen={setOpenTask}
                  onReject={setRejectingTask}
                  onRename={handleRename}
                  pendingTaskId={pendingTaskId}
                  onCreate={
                    status === "en_attente_validation" && project.permissions.can_contribute
                      ? () => setCreatingTask(true)
                      : undefined
                  }
                  dropDisabled={activeDragTask !== null && !isDropAllowed(activeDragTask, status)}
                />
              ))}
            </div>
          </DndContext>
        </LoadingTransition>
      )}

      {openTask && (
        <TaskDrawer
          task={openTask}
          assignableUsers={projectMembers}
          onClose={() => setOpenTask(null)}
          onValidate={handleValidate}
          onReject={setRejectingTask}
          onClaim={handleClaim}
          onAssign={handleAssign}
          onStart={handleStart}
          onComplete={setCompletingTask}
          onSaveEstimatedHours={handleSaveEstimatedHours}
          comments={comments}
          commentsError={commentsError}
          commentSubmitting={commentSubmitting}
          onAddComment={handleAddComment}
          auditLog={auditLog}
          pending={pendingTaskId === openTask.id}
        />
      )}
      {rejectingTask && (
        <RejectDialog task={rejectingTask} onCancel={() => setRejectingTask(null)} onConfirm={handleReject} />
      )}
      {completingTask && (
        <CompleteDialog task={completingTask} onCancel={() => setCompletingTask(null)} onConfirm={handleComplete} />
      )}
      {creatingTask && (
        <TaskCreateDialog
          projects={[project]}
          users={projectMembers}
          defaultProjectId={project.id}
          submitting={createSubmitting}
          error={createError}
          onCancel={() => {
            setCreatingTask(false);
            setCreateError(null);
          }}
          onSubmit={handleCreate}
        />
      )}
    </div>
  );
}
