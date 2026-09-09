import { AlertTriangle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { addTaskComment, getTask, getTasks, updateTaskEstimatedHours } from "../../api/client";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonRows } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type { AuditLogEntry, Project, Task, TaskComment } from "../../types/watodo";
import { CompleteDialog } from "./CompleteDialog";
import { RejectDialog } from "./RejectDialog";
import { TaskDrawer } from "./TaskDrawer";
import { useTaskTransitions } from "./useTaskTransitions";
import "./RoadmapView.css";

const INACTIVE_STATUSES = new Set(["archivee", "rejetee"]);
const LATE_ALERT_PRIORITIES = new Set(["haute", "critique"]);
const DAY_MS = 24 * 60 * 60 * 1000;

const PRIORITY_LEGEND: { value: Task["priority"]; label: string }[] = [
  { value: "basse", label: "Basse" },
  { value: "moyenne", label: "Moyenne" },
  { value: "haute", label: "Haute" },
  { value: "critique", label: "Critique" },
];

interface TimelineWindow {
  start: number;
  end: number;
}

function computeWindow(tasks: Task[]): TimelineWindow {
  const starts = tasks.map((task) => new Date(task.created_at).getTime());
  const ends = tasks.map((task) => new Date(task.deadline as string).getTime());
  const rawStart = Math.min(...starts);
  const rawEnd = Math.max(...ends);
  const span = Math.max(rawEnd - rawStart, DAY_MS);
  const padding = Math.max(span * 0.03, DAY_MS);
  return { start: rawStart - padding, end: rawEnd + padding };
}

function percentInWindow(timestamp: number, timeWindow: TimelineWindow): number {
  const span = timeWindow.end - timeWindow.start;
  if (span <= 0) return 0;
  return Math.min(100, Math.max(0, ((timestamp - timeWindow.start) / span) * 100));
}

interface Gridline {
  position: number;
  label: string;
}

function buildGridlines(timeWindow: TimelineWindow): Gridline[] {
  const spanDays = (timeWindow.end - timeWindow.start) / DAY_MS;
  const lines: Gridline[] = [];

  if (spanDays > 60) {
    const cursor = new Date(timeWindow.start);
    cursor.setDate(1);
    cursor.setHours(0, 0, 0, 0);
    while (cursor.getTime() <= timeWindow.end) {
      if (cursor.getTime() >= timeWindow.start) {
        lines.push({
          position: percentInWindow(cursor.getTime(), timeWindow),
          label: cursor.toLocaleDateString("fr-FR", { month: "short", year: "numeric" }),
        });
      }
      cursor.setMonth(cursor.getMonth() + 1);
    }
  } else {
    const cursor = new Date(timeWindow.start);
    const day = cursor.getDay();
    const diffToMonday = day === 0 ? -6 : 1 - day;
    cursor.setDate(cursor.getDate() + diffToMonday);
    cursor.setHours(0, 0, 0, 0);
    while (cursor.getTime() <= timeWindow.end) {
      if (cursor.getTime() >= timeWindow.start) {
        lines.push({
          position: percentInWindow(cursor.getTime(), timeWindow),
          label: cursor.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }),
        });
      }
      cursor.setDate(cursor.getDate() + 7);
    }
  }

  return lines;
}

interface RoadmapViewProps {
  project: Project;
  /** Voir docs/modeles-et-api.md > "ProjectVersion" — sélecteur partagé avec
   * le Kanban, possédé par `TasksTab`. `undefined` = version courante. */
  versionId?: string;
}

export function RoadmapView({ project, versionId }: RoadmapViewProps) {
  const { showToast } = useToast();
  const projectMembers = project.members.map((membership) => membership.user);
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openTask, setOpenTask] = useState<Task | null>(null);
  const [comments, setComments] = useState<TaskComment[] | null>(null);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const now = Date.now();

  useEffect(() => {
    let cancelled = false;
    setTasks(null);
    setError(null);

    getTasks({ project: project.id, version: versionId })
      .then((data) => {
        if (!cancelled) setTasks(data);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger les tâches.");
      });

    return () => {
      cancelled = true;
    };
  }, [project.id, versionId]);

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

  const activeTasks = useMemo(() => (tasks ?? []).filter((task) => !INACTIVE_STATUSES.has(task.status)), [tasks]);
  const withDeadline = useMemo(
    () =>
      [...activeTasks]
        .filter((task) => task.deadline)
        .sort((a, b) => new Date(a.deadline as string).getTime() - new Date(b.deadline as string).getTime()),
    [activeTasks],
  );
  const withoutDeadline = useMemo(() => activeTasks.filter((task) => !task.deadline), [activeTasks]);

  const timeWindow = withDeadline.length > 0 ? computeWindow(withDeadline) : null;
  const gridlines = timeWindow ? buildGridlines(timeWindow) : [];
  const todayPct = timeWindow ? percentInWindow(now, timeWindow) : null;

  return (
    <div className="roadmap">
      {actionError && <p className="roadmap__error">{actionError}</p>}
      {error && <p className="roadmap__error">{error}</p>}

      {!error && (
        <LoadingTransition loading={tasks === null} skeleton={<SkeletonRows rows={5} />}>
      {tasks !== null && withDeadline.length === 0 && (
        <p className="roadmap__empty">Aucune tâche active avec échéance pour l'instant.</p>
      )}

      {withDeadline.length > 0 && (
        <div className="roadmap__card">
          <div className="roadmap__legend">
            {PRIORITY_LEGEND.map((item) => (
              <span key={item.value} className="roadmap__legend-item">
                <span className={`roadmap__legend-swatch roadmap__legend-swatch--${item.value}`} />
                {item.label}
              </span>
            ))}
          </div>

          {timeWindow && (
            <div className="roadmap__scroll">
              <div className="roadmap__timeline">
                <div className="roadmap__axis-row">
                  <div className="roadmap__label-spacer" />
                  <div className="roadmap__axis">
                    {gridlines.map((line, index) => (
                      <div key={index} className="roadmap__gridline" style={{ left: `${line.position}%` }}>
                        <span>{line.label}</span>
                      </div>
                    ))}
                    {todayPct !== null && (
                      <div className="roadmap__today" style={{ left: `${todayPct}%` }}>
                        <span>Aujourd'hui</span>
                      </div>
                    )}
                  </div>
                </div>

                {withDeadline.map((task) => {
                  const start = new Date(task.created_at).getTime();
                  const end = new Date(task.deadline as string).getTime();
                  const left = percentInWindow(start, timeWindow);
                  const width = Math.max(percentInWindow(end, timeWindow) - left, 1.5);
                  const isLate = end < now && LATE_ALERT_PRIORITIES.has(task.priority);

                  return (
                    <div key={task.id} className="roadmap__row">
                      <span className="roadmap__row-label" title={task.title}>
                        {task.title}
                      </span>
                      <div className="roadmap__row-track">
                        {gridlines.map((line, index) => (
                          <div key={index} className="roadmap__row-gridline" style={{ left: `${line.position}%` }} />
                        ))}
                        <button
                          type="button"
                          className={`roadmap__segment roadmap__segment--${task.priority}`}
                          style={{ left: `${left}%`, width: `${width}%` }}
                          onClick={() => setOpenTask(task)}
                        >
                          {isLate && (
                            <AlertTriangle
                              size={12}
                              strokeWidth={2}
                              className="roadmap__late-icon"
                              aria-label="En retard"
                            />
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {withoutDeadline.length > 0 && (
        <div className="roadmap__no-deadline">
          <h3 className="roadmap__no-deadline-title">Sans échéance</h3>
          <ul className="roadmap__no-deadline-list">
            {withoutDeadline.map((task) => (
              <li key={task.id}>
                <button type="button" className="roadmap__no-deadline-item" onClick={() => setOpenTask(task)}>
                  <span>{task.title}</span>
                  <span className={`roadmap__priority-dot roadmap__priority-dot--${task.priority}`} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
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
    </div>
  );
}
