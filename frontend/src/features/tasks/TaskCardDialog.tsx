import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import {
  addTaskComment,
  getProject,
  getTask,
  updateTaskDeadline,
  updateTaskDescription,
  updateTaskEstimatedHours,
} from "../../api/client";
import type { Task, TaskDetail, User } from "../../types/watodo";
import { CompleteDialog } from "./CompleteDialog";
import { RejectDialog } from "./RejectDialog";
import { TaskAccordion } from "./TaskAccordion";
import { useTaskTransitions } from "./useTaskTransitions";
import "./TaskCardDialog.css";

// Même logique que UserMenu.tsx/ProjectAdminTab.tsx (initiales) — duplication
// volontaire d'un petit bloc plutôt qu'une abstraction partagée, cohérent
// avec les conventions déjà en place dans ce projet.
function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function displayName(user: User): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

interface TaskCardDialogProps {
  taskId: string;
  onClose: () => void;
  /** Appelé après toute transition réussie (validation/attribution/clôture/
   * rejet…) — laisse l'appelant (le planning) rafraîchir ses propres listes
   * (créneaux, tâches à planifier) sans que cette carte n'ait à les connaître. */
  onChanged?: () => void;
}

// Reprend le patron "carte extensible" : ouvre directement les informations
// et actions d'une tâche par-dessus l'écran courant (ici le planning), sans
// navigation — même contenu que la ligne dépliée de `TasksListPage`
// (`TaskAccordion`, badges/attribution/description/historique/commentaires
// + Valider/Rejeter/M'attribuer/Démarrer/Clôturer selon les droits), monté
// dans une carte centrée plutôt que sous une ligne de tableau.
export function TaskCardDialog({ taskId, onClose, onChanged }: TaskCardDialogProps) {
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [assignableUsers, setAssignableUsers] = useState<User[]>([]);
  const [projectName, setProjectName] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [commentSubmitting, setCommentSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getTask(taskId)
      .then((data) => {
        if (cancelled) return;
        setTask(data);
        getProject(data.project)
          .then((project) => {
            if (cancelled) return;
            setAssignableUsers(project.members.map((m) => m.user));
            setProjectName(project.name);
          })
          .catch(() => undefined);
      })
      .catch(() => {
        if (!cancelled) setLoadError("Impossible de charger la tâche.");
      });
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  function updateTaskLocally(updated: Task) {
    setTask((current) => (current ? { ...current, ...updated } : current));
    onChanged?.();
  }

  function removeTaskLocally() {
    onChanged?.();
    onClose();
  }

  const {
    rejectingTask,
    setRejectingTask,
    completingTask,
    setCompletingTask,
    actionError,
    pendingTaskId,
    handleValidate,
    handleClaim,
    handleAssign,
    handleStart,
    handleReject,
    handleComplete,
  } = useTaskTransitions(updateTaskLocally, removeTaskLocally);

  async function handleSaveDescription(current: Task, description: string) {
    updateTaskLocally(await updateTaskDescription(current.id, description));
  }

  async function handleSaveEstimatedHours(current: Task, value: string | null) {
    updateTaskLocally(await updateTaskEstimatedHours(current.id, value));
  }

  async function handleSaveDeadline(current: Task, value: string | null) {
    updateTaskLocally(await updateTaskDeadline(current.id, value));
  }

  async function handleAddComment(content: string) {
    if (!task) return;
    setCommentSubmitting(true);
    setCommentsError(null);
    try {
      const comment = await addTaskComment(task.id, content);
      setTask((current) => (current ? { ...current, comments: [...current.comments, comment] } : current));
    } catch (err) {
      setCommentsError(err instanceof Error ? err.message : "L'ajout du commentaire a échoué.");
    } finally {
      setCommentSubmitting(false);
    }
  }

  // "Collaborateurs" de la carte (pied de carte) : l'assigné puis les
  // auteurs de commentaires, dédupliqués — pas de photo de profil dans
  // Awtodo (voir `UserMenu`/`ProjectAdminTab`), un avatar = des initiales.
  const collaborators: User[] = [];
  if (task) {
    const seen = new Set<string>();
    if (task.assignee) {
      collaborators.push(task.assignee);
      seen.add(task.assignee.id);
    }
    for (const comment of task.comments) {
      if (!seen.has(comment.author.id)) {
        collaborators.push(comment.author);
        seen.add(comment.author.id);
      }
    }
  }

  return (
    <div className="task-card-dialog__overlay" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
        className="task-card-dialog"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="task-card-dialog__header">
          <div>
            <h2 className="task-card-dialog__title">{task?.title ?? "Tâche"}</h2>
            {projectName && <p className="task-card-dialog__subtitle">{projectName}</p>}
          </div>
          <button type="button" className="task-card-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={18} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {loadError && <p className="task-card-dialog__message task-card-dialog__message--error">{loadError}</p>}
        {actionError && <p className="task-card-dialog__message task-card-dialog__message--error">{actionError}</p>}
        {!task && !loadError && <p className="task-card-dialog__message">Chargement…</p>}

        {task && (
          <>
            <AnimatePresence>
              <TaskAccordion
                task={task}
                assignableUsers={assignableUsers}
                onClose={onClose}
                onValidate={handleValidate}
                onReject={setRejectingTask}
                onClaim={handleClaim}
                onAssign={handleAssign}
                onStart={handleStart}
                onComplete={setCompletingTask}
                onSaveDescription={handleSaveDescription}
                onSaveEstimatedHours={handleSaveEstimatedHours}
                onSaveDeadline={handleSaveDeadline}
                comments={task.comments}
                commentsError={commentsError}
                commentSubmitting={commentSubmitting}
                onAddComment={handleAddComment}
                auditLog={task.audit_log}
                pending={pendingTaskId === task.id}
              />
            </AnimatePresence>

            <div className="task-card-dialog__footer">
              <span className="task-card-dialog__footer-meta">
                Créée le {new Date(task.created_at).toLocaleDateString("fr-FR")}
              </span>
              {collaborators.length > 0 && (
                <div className="task-card-dialog__collaborators">
                  {collaborators.map((user) => (
                    <span
                      key={user.id}
                      className="task-card-dialog__avatar"
                      title={displayName(user)}
                    >
                      {initials(displayName(user))}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </motion.div>

      {rejectingTask && (
        <RejectDialog task={rejectingTask} onCancel={() => setRejectingTask(null)} onConfirm={handleReject} />
      )}
      {completingTask && (
        <CompleteDialog task={completingTask} onCancel={() => setCompletingTask(null)} onConfirm={handleComplete} />
      )}
    </div>
  );
}
