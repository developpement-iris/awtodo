import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { addTaskComment, getProject, getTask, updateTaskDescription, updateTaskEstimatedHours } from "../../api/client";
import type { Task, TaskDetail, User } from "../../types/watodo";
import { CompleteDialog } from "./CompleteDialog";
import { RejectDialog } from "./RejectDialog";
import { TaskAccordion } from "./TaskAccordion";
import { useTaskTransitions } from "./useTaskTransitions";
import "./TaskCardDialog.css";

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
            if (!cancelled) setAssignableUsers(project.members.map((m) => m.user));
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
          <h2 className="task-card-dialog__title">{task?.title ?? "Tâche"}</h2>
          <button type="button" className="task-card-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={18} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {loadError && <p className="task-card-dialog__message task-card-dialog__message--error">{loadError}</p>}
        {actionError && <p className="task-card-dialog__message task-card-dialog__message--error">{actionError}</p>}
        {!task && !loadError && <p className="task-card-dialog__message">Chargement…</p>}

        {task && (
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
              comments={task.comments}
              commentsError={commentsError}
              commentSubmitting={commentSubmitting}
              onAddComment={handleAddComment}
              auditLog={task.audit_log}
              pending={pendingTaskId === task.id}
            />
          </AnimatePresence>
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
