import { ChevronUp } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Combobox } from "../../components/Combobox";
import { InlineEditableText } from "../../components/InlineEditableText";
import { InlineEditableTextarea } from "../../components/InlineEditableTextarea";
import { StatusBadge } from "../../components/StatusBadge";
import { TypeBadge } from "../../components/TypeBadge";
import { priorityTone, statusTone, taskStatusIcon } from "../../lib/badges";
import { auditFieldLabel } from "../../lib/auditFieldLabels";
import type { AuditLogEntry, Task, TaskComment, User } from "../../types/watodo";
import "./TaskAccordion.css";

function displayName(user: User): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

interface TaskAccordionProps {
  task: Task;
  assignableUsers: User[];
  onClose: () => void;
  onValidate: (task: Task) => void;
  onReject: (task: Task) => void;
  onClaim: (task: Task) => void;
  onAssign: (task: Task, userId: string) => void;
  onStart: (task: Task) => void;
  onComplete: (task: Task) => void;
  onSaveDescription: (task: Task, description: string) => void;
  onSaveEstimatedHours: (task: Task, value: string | null) => void;
  auditLog: AuditLogEntry[];
  comments: TaskComment[] | null;
  commentsError: string | null;
  commentSubmitting: boolean;
  onAddComment: (content: string) => void;
  pending?: boolean;
}

// Déroulé sous la ligne du tableau (voir TasksListPage) — remplace l'ancien
// drawer latéral. Même contenu (badges/actions/attribution/description/
// historique/commentaires), simplement rendu en accordéon vertical plutôt
// qu'en overlay plein écran : pas de layoutId partagé (le placement "sous la
// ligne" ne s'y prête pas), une animation de hauteur suffit.
export function TaskAccordion({
  task,
  assignableUsers,
  onClose,
  onValidate,
  onReject,
  onClaim,
  onAssign,
  onStart,
  onComplete,
  onSaveDescription,
  onSaveEstimatedHours,
  auditLog,
  comments,
  commentsError,
  commentSubmitting,
  onAddComment,
  pending = false,
}: TaskAccordionProps) {
  const [assigneeSelection, setAssigneeSelection] = useState(task.assignee?.id ?? "");
  const [draft, setDraft] = useState("");

  useEffect(() => {
    setAssigneeSelection(task.assignee?.id ?? "");
  }, [task.id, task.assignee?.id]);

  function handleSubmitComment() {
    if (!draft.trim()) return;
    onAddComment(draft.trim());
    setDraft("");
  }

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="task-accordion"
    >
      <div className="task-accordion__inner" onClick={(event) => event.stopPropagation()}>
        <div className="task-accordion__header">
          <div className="task-accordion__badges">
            <TypeBadge type={task.task_type} label={task.task_type_display} />
            <StatusBadge label={task.status_display} tone={statusTone(task.status)} icon={taskStatusIcon(task.status)} />
            <StatusBadge label={task.priority_display} tone={priorityTone(task.priority)} />
          </div>
          <button type="button" className="task-accordion__collapse" onClick={onClose} aria-label="Réduire">
            <ChevronUp size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {task.external_reference_id && (
          <p className="task-accordion__ref">
            Réf. externe : <span>{task.external_reference_id}</span>
          </p>
        )}

        <div className="task-accordion__actions">
          {task.permissions.can_validate && (
            <motion.button
              type="button"
              className="task-accordion__action"
              onClick={() => onValidate(task)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              Valider
            </motion.button>
          )}
          {task.permissions.can_reject && (
            <motion.button
              type="button"
              className="task-accordion__action task-accordion__action--danger"
              onClick={() => onReject(task)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              Rejeter
            </motion.button>
          )}
          {task.permissions.can_claim && (
            <motion.button
              type="button"
              className="task-accordion__action"
              onClick={() => onClaim(task)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              M'attribuer cette tâche
            </motion.button>
          )}
          {task.permissions.can_start && (
            <motion.button
              type="button"
              className="task-accordion__action"
              onClick={() => onStart(task)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              Démarrer
            </motion.button>
          )}
          {task.permissions.can_complete && (
            <motion.button
              type="button"
              className="task-accordion__action"
              onClick={() => onComplete(task)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              Clôturer
            </motion.button>
          )}
        </div>

        <div className="task-accordion__grid">
          <section className="task-accordion__section">
            <h3 className="task-accordion__section-title">Attribution</h3>
            <p className="task-accordion__meta">
              {task.assignee ? `Assignée à ${displayName(task.assignee)}` : "Non assignée."}
            </p>
            {task.permissions.can_assign && (
              <div className="task-accordion__assign">
                <span className="task-accordion__assign-select">
                  <Combobox
                    options={assignableUsers.map((user) => ({ value: user.id, label: displayName(user) }))}
                    value={assigneeSelection}
                    onChange={setAssigneeSelection}
                    disabled={pending}
                    placeholder="Choisir un membre…"
                    searchPlaceholder="Rechercher un nom…"
                  />
                </span>
                <motion.button
                  type="button"
                  className="task-accordion__assign-submit"
                  onClick={() => assigneeSelection && onAssign(task, assigneeSelection)}
                  disabled={pending || !assigneeSelection || assigneeSelection === task.assignee?.id}
                  whileTap={{ scale: 0.96 }}
                >
                  {task.assignee ? "Réattribuer" : "Assigner"}
                </motion.button>
              </div>
            )}
          </section>

          <section className="task-accordion__section">
            <h3 className="task-accordion__section-title">Description</h3>
            <InlineEditableTextarea
              value={task.description}
              onSave={(description) => onSaveDescription(task, description)}
              ariaLabel="Description de la tâche"
              disabled={!task.permissions.can_edit_description || pending}
              emptyLabel="Aucune description."
              rows={4}
            />
          </section>

          <section className="task-accordion__section">
            <h3 className="task-accordion__section-title">Temps</h3>
            <p className="task-accordion__meta">
              Estimé :{" "}
              <InlineEditableText
                value={task.estimated_hours ?? ""}
                onSave={(value) => onSaveEstimatedHours(task, value.trim() ? value.trim() : null)}
                ariaLabel="Temps estimé (heures)"
                disabled={pending}
              />
              {" h"}
            </p>
            <p className="task-accordion__meta">
              Réel : {task.time_spent ? `${task.time_spent} h` : "—"} (renseigné à la clôture)
            </p>
          </section>
        </div>

        <section className="task-accordion__section">
          <h3 className="task-accordion__section-title">Historique</h3>
          {auditLog.length === 0 ? (
            <p className="task-accordion__empty">Aucune modification enregistrée.</p>
          ) : (
            <ul className="task-accordion__audit-list">
              {auditLog.map((entry) => (
                <li key={entry.id} className="task-accordion__audit-entry">
                  <span className="task-accordion__audit-field">{auditFieldLabel(entry.field_name)}</span>
                  <span className="task-accordion__audit-change">
                    {entry.old_value || "—"} → {entry.new_value || "—"}
                  </span>
                  <span className="task-accordion__audit-meta">
                    {displayName(entry.actor)} ·{" "}
                    <time dateTime={entry.created_at} title={new Date(entry.created_at).toLocaleString("fr-FR")}>
                      {new Date(entry.created_at).toLocaleDateString("fr-FR")}
                    </time>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="task-accordion__section">
          <h3 className="task-accordion__section-title">Commentaires</h3>

          {comments === null && !commentsError && <p className="task-accordion__empty">Chargement…</p>}
          {commentsError && <p className="task-accordion__error">{commentsError}</p>}
          {comments !== null && comments.length === 0 && (
            <p className="task-accordion__empty">Aucun commentaire pour l'instant.</p>
          )}
          {comments !== null && comments.length > 0 && (
            <ul className="task-accordion__comment-list">
              {comments.map((comment) => (
                <li key={comment.id} className="task-accordion__comment">
                  <div className="task-accordion__comment-meta">
                    <span className="task-accordion__comment-author">{displayName(comment.author)}</span>
                    <time dateTime={comment.created_at} title={new Date(comment.created_at).toLocaleString("fr-FR")}>
                      {new Date(comment.created_at).toLocaleDateString("fr-FR")}
                    </time>
                  </div>
                  <p className="task-accordion__comment-content">{comment.content}</p>
                </li>
              ))}
            </ul>
          )}

          {task.permissions.can_comment && (
            <div className="task-accordion__comment-composer">
              <textarea
                className="task-accordion__comment-input"
                placeholder="Ajouter un commentaire…"
                rows={2}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={commentSubmitting}
              />
              <button
                type="button"
                className="task-accordion__comment-submit"
                onClick={handleSubmitComment}
                disabled={commentSubmitting || !draft.trim()}
              >
                {commentSubmitting ? "Publication…" : "Publier"}
              </button>
            </div>
          )}
        </section>
      </div>
    </motion.div>
  );
}
