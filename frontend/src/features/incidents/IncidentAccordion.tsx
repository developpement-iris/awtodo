import { ChevronUp } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { InlineEditableTextarea } from "../../components/InlineEditableTextarea";
import { StatusBadge } from "../../components/StatusBadge";
import { incidentStatusIcon, incidentStatusTone, priorityTone } from "../../lib/badges";
import { auditFieldLabel } from "../../lib/auditFieldLabels";
import { formatRelativeTime } from "../../lib/relativeTime";
import type { AuditLogEntry, Incident, IncidentComment, Project } from "../../types/watodo";
import "./IncidentAccordion.css";

interface IncidentAccordionProps {
  incident: Incident;
  projectName?: string;
  teamName?: string;
  projects?: Project[];
  comments: IncidentComment[] | null;
  commentsError: string | null;
  commentSubmitting: boolean;
  auditLog: AuditLogEntry[];
  onAddComment: (content: string) => void;
  onClose: () => void;
  onStart: (incident: Incident) => void;
  onResolve: (incident: Incident) => void;
  onArchive: (incident: Incident) => void;
  onAssignProject?: (incident: Incident, projectId: string) => void;
  onSaveDescription: (incident: Incident, description: string) => void;
  pending?: boolean;
}

// Déroulé sous la ligne du tableau (voir IncidentsPage) — remplace l'ancien
// drawer latéral, même contenu (badges/actions/réassignation/description/
// commentaires), rendu en accordéon vertical plutôt qu'en overlay.
export function IncidentAccordion({
  incident,
  projectName,
  teamName,
  projects = [],
  comments,
  commentsError,
  commentSubmitting,
  auditLog,
  onAddComment,
  onClose,
  onStart,
  onResolve,
  onArchive,
  onAssignProject,
  onSaveDescription,
  pending = false,
}: IncidentAccordionProps) {
  const [draft, setDraft] = useState("");
  const [assignProjectId, setAssignProjectId] = useState("");

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
      className="incident-accordion"
    >
      <div className="incident-accordion__inner" onClick={(event) => event.stopPropagation()}>
        <div className="incident-accordion__header">
          <div className="incident-accordion__badges">
            <StatusBadge
              label={incident.status_display}
              tone={incidentStatusTone(incident.status)}
              icon={incidentStatusIcon(incident.status)}
            />
            <StatusBadge label={incident.priority_display} tone={priorityTone(incident.priority)} />
          </div>
          <button type="button" className="incident-accordion__collapse" onClick={onClose} aria-label="Réduire">
            <ChevronUp size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        <p className="incident-accordion__meta">
          {projectName && <>Projet : {projectName} · </>}
          {teamName && <>Groupe : {teamName} (non affecté à un projet) · </>}
          Signalé{" "}
          <time dateTime={incident.created_at} title={new Date(incident.created_at).toLocaleString("fr-FR")}>
            {formatRelativeTime(incident.created_at)}
          </time>
        </p>

        {incident.external_reference_id && (
          <p className="incident-accordion__ref">
            Réf. externe : <span>{incident.external_reference_id}</span>
          </p>
        )}

        <div className="incident-accordion__actions">
          {incident.permissions.can_start && (
            <motion.button
              type="button"
              className="incident-accordion__action"
              onClick={() => onStart(incident)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              Démarrer
            </motion.button>
          )}
          {incident.permissions.can_resolve && (
            <motion.button
              type="button"
              className="incident-accordion__action"
              onClick={() => onResolve(incident)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              Résoudre
            </motion.button>
          )}
          {incident.permissions.can_archive && (
            <motion.button
              type="button"
              className="incident-accordion__action"
              onClick={() => onArchive(incident)}
              disabled={pending}
              whileTap={{ scale: 0.96 }}
            >
              Archiver
            </motion.button>
          )}
        </div>

        {incident.permissions.can_assign_project && onAssignProject && (
          <div className="incident-accordion__assign">
            <select
              className="incident-accordion__assign-select"
              value={assignProjectId}
              onChange={(event) => setAssignProjectId(event.target.value)}
              disabled={pending}
            >
              <option value="" disabled>
                Choisir un projet…
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            <motion.button
              type="button"
              className="incident-accordion__action"
              onClick={() => onAssignProject(incident, assignProjectId)}
              disabled={pending || !assignProjectId}
              whileTap={{ scale: 0.96 }}
            >
              Rattacher au projet
            </motion.button>
          </div>
        )}

        <section className="incident-accordion__section">
          <h3 className="incident-accordion__section-title">Description</h3>
          <InlineEditableTextarea
            value={incident.description}
            onSave={(description) => onSaveDescription(incident, description)}
            ariaLabel="Description de l'incident"
            disabled={!incident.permissions.can_edit_description || pending}
            emptyLabel="Aucune description."
            rows={4}
          />
        </section>

        <section className="incident-accordion__section">
          <h3 className="incident-accordion__section-title">Historique</h3>
          {auditLog.length === 0 ? (
            <p className="incident-accordion__empty">Aucune modification enregistrée.</p>
          ) : (
            <ul className="incident-accordion__audit-list">
              {auditLog.map((entry) => (
                <li key={entry.id} className="incident-accordion__audit-entry">
                  <span className="incident-accordion__audit-field">{auditFieldLabel(entry.field_name)}</span>
                  <span className="incident-accordion__audit-change">
                    {entry.old_value || "—"} → {entry.new_value || "—"}
                  </span>
                  <span className="incident-accordion__audit-meta">
                    {`${entry.actor.first_name} ${entry.actor.last_name}`.trim() || entry.actor.username} ·{" "}
                    <time dateTime={entry.created_at} title={new Date(entry.created_at).toLocaleString("fr-FR")}>
                      {new Date(entry.created_at).toLocaleDateString("fr-FR")}
                    </time>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="incident-accordion__section">
          <h3 className="incident-accordion__section-title">Commentaires</h3>

          {comments === null && !commentsError && <p className="incident-accordion__empty">Chargement…</p>}
          {commentsError && <p className="incident-accordion__error">{commentsError}</p>}
          {comments !== null && comments.length === 0 && (
            <p className="incident-accordion__empty">Aucun commentaire pour l'instant.</p>
          )}
          {comments !== null && comments.length > 0 && (
            <ul className="incident-accordion__comment-list">
              {comments.map((comment) => (
                <li key={comment.id} className="incident-accordion__comment">
                  <div className="incident-accordion__comment-meta">
                    <span className="incident-accordion__comment-author">
                      {`${comment.author.first_name} ${comment.author.last_name}`.trim() || comment.author.username}
                    </span>
                    <time dateTime={comment.created_at} title={new Date(comment.created_at).toLocaleString("fr-FR")}>
                      {formatRelativeTime(comment.created_at)}
                    </time>
                  </div>
                  <p className="incident-accordion__comment-content">{comment.content}</p>
                </li>
              ))}
            </ul>
          )}

          {incident.permissions.can_comment && (
            <div className="incident-accordion__comment-composer">
              <textarea
                className="incident-accordion__comment-input"
                placeholder="Ajouter un commentaire…"
                rows={2}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={commentSubmitting}
              />
              <button
                type="button"
                className="incident-accordion__comment-submit"
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
