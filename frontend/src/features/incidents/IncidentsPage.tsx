import { ArrowDown, ArrowUp, ArrowUpDown, Plus } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import {
  addIncidentComment,
  archiveIncident,
  assignIncidentProject,
  createIncident,
  getIncident,
  getIncidents,
  getIncidentsInbox,
  getProjects,
  resolveIncident,
  startIncident,
  updateIncidentDescription,
  type IncidentCreatePayload,
} from "../../api/client";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SkeletonTable } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { StatusFilterDropdown } from "../../components/StatusFilterDropdown";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import { incidentStatusIcon, incidentStatusTone, priorityRank, priorityTone } from "../../lib/badges";
import { formatRelativeTime } from "../../lib/relativeTime";
import { defaultStatusSelection, INCIDENT_STATUS_FILTER_OPTIONS } from "../../lib/statusFilterOptions";
import type { AuditLogEntry, Incident, IncidentComment, Project } from "../../types/watodo";
import { IncidentAccordion } from "./IncidentAccordion";
import { IncidentCreateDialog, type IncidentCreateFormValues } from "./IncidentCreateDialog";
import "./IncidentsPage.css";

function buildCreatePayload(values: IncidentCreateFormValues): IncidentCreatePayload {
  const payload: IncidentCreatePayload = {
    project: values.project,
    title: values.title.trim(),
    priority: values.priority,
  };
  if (values.description.trim()) payload.description = values.description.trim();
  if (values.external_reference_id.trim()) payload.external_reference_id = values.external_reference_id.trim();
  return payload;
}

type SortKey = "delay" | "priority" | null;

function sortIncidents(list: Incident[], sortKey: SortKey, reversed: boolean): Incident[] {
  if (!sortKey) return list;
  const sorted = [...list].sort((a, b) => {
    if (sortKey === "delay") {
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
    return priorityRank(a.priority) - priorityRank(b.priority);
  });
  return reversed ? sorted.reverse() : sorted;
}

interface IncidentRowProps {
  incident: Incident;
  ownerLabel?: string;
  expanded: boolean;
  onToggle: () => void;
  onStart: () => void;
  onResolve: () => void;
  onArchive: () => void;
  pending: boolean;
  colSpan: number;
  children?: ReactNode;
}

function IncidentRow({
  incident,
  ownerLabel,
  expanded,
  onToggle,
  onStart,
  onResolve,
  onArchive,
  pending,
  colSpan,
  children,
}: IncidentRowProps) {
  return (
    <>
      <tr id={`incident-row-${incident.id}`} className="incidents-page__row--clickable" onClick={onToggle}>
        <td>{incident.title}</td>
        <td>
          {incident.external_reference_id && (
            <span className="incidents-page__ref">{incident.external_reference_id}</span>
          )}
        </td>
        {ownerLabel !== undefined && <td>{ownerLabel}</td>}
        <td>
          <StatusBadge
            label={incident.status_display}
            tone={incidentStatusTone(incident.status)}
            icon={incidentStatusIcon(incident.status)}
          />
        </td>
        <td>
          <StatusBadge label={incident.priority_display} tone={priorityTone(incident.priority)} />
        </td>
        <td>
          <time
            className="incidents-page__delay"
            dateTime={incident.created_at}
            title={new Date(incident.created_at).toLocaleString("fr-FR")}
          >
            {formatRelativeTime(incident.created_at)}
          </time>
        </td>
        <td className="incidents-page__actions">
          {incident.permissions.can_start && (
            <button
              type="button"
              className="incidents-page__action"
              onClick={(event) => {
                event.stopPropagation();
                onStart();
              }}
              disabled={pending}
            >
              Démarrer
            </button>
          )}
          {incident.permissions.can_resolve && (
            <button
              type="button"
              className="incidents-page__action"
              onClick={(event) => {
                event.stopPropagation();
                onResolve();
              }}
              disabled={pending}
            >
              Résoudre
            </button>
          )}
          {incident.permissions.can_archive && (
            <button
              type="button"
              className="incidents-page__action"
              onClick={(event) => {
                event.stopPropagation();
                onArchive();
              }}
              disabled={pending}
            >
              Archiver
            </button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="incidents-page__accordion-row">
          <td colSpan={colSpan}>
            <AnimatePresence>{children}</AnimatePresence>
          </td>
        </tr>
      )}
    </>
  );
}

interface IncidentsPageProps {
  createTrigger?: number;
  /** Réemploi contextualisé dans l'onglet Maintenance d'un projet (chantier 4) :
   * verrouille le filtre projet et masque le sélecteur + la colonne Projet. */
  scopedProject?: Project;
  /** Depuis le backlog de l'accueil : ouvre directement cet incident et
   * l'amène à l'écran, au lieu d'atterrir sur la liste sans plus de contexte. */
  focusIncidentId?: string;
}

export function IncidentsPage({ createTrigger = 0, scopedProject, focusIncidentId }: IncidentsPageProps = {}) {
  const { showToast } = useToast();
  const { currentUser } = useCurrentUser();
  const [projects, setProjects] = useState<Project[]>([]);
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [inboxIncidents, setInboxIncidents] = useState<Incident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [projectFilter, setProjectFilter] = useState<string>(scopedProject?.id ?? "");
  const [statusFilter, setStatusFilter] = useState(() => defaultStatusSelection(INCIDENT_STATUS_FILTER_OPTIONS));
  const [pendingIncidentId, setPendingIncidentId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>(null);
  const [sortReversed, setSortReversed] = useState(false);
  const [expandedIncidentId, setExpandedIncidentId] = useState<string | null>(null);
  const [comments, setComments] = useState<IncidentComment[] | null>(null);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);

  const effectiveProjectFilter = scopedProject?.id ?? projectFilter;

  useEffect(() => {
    if (createTrigger > 0) setCreating(true);
  }, [createTrigger]);

  useEffect(() => {
    if (scopedProject) {
      setProjects([scopedProject]);
      return;
    }
    getProjects()
      .then(setProjects)
      .catch(() => undefined);
  }, [scopedProject]);

  useEffect(() => {
    let cancelled = false;
    setIncidents(null);
    setError(null);

    getIncidents({ project: effectiveProjectFilter || undefined, status: Array.from(statusFilter) })
      .then((data) => {
        if (!cancelled) setIncidents(data);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger les incidents.");
      });

    return () => {
      cancelled = true;
    };
  }, [effectiveProjectFilter, statusFilter]);

  useEffect(() => {
    // Boîte de réception : jamais dans l'onglet Incidents d'un projet
    // (scopedProject), et seulement si l'utilisateur appartient à au moins
    // un groupe (sinon il n'y a jamais rien à y voir).
    if (scopedProject || !currentUser || currentUser.teams.length === 0) {
      setInboxIncidents(null);
      return;
    }
    let cancelled = false;

    getIncidentsInbox({ status: Array.from(statusFilter) })
      .then((data) => {
        if (!cancelled) setInboxIncidents(data);
      })
      .catch(() => {
        if (!cancelled) setInboxIncidents([]);
      });

    return () => {
      cancelled = true;
    };
  }, [scopedProject, currentUser, statusFilter]);

  useEffect(() => {
    if (!focusIncidentId) return;
    setExpandedIncidentId(focusIncidentId);
    const timeout = window.setTimeout(() => {
      document.getElementById(`incident-row-${focusIncidentId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    return () => window.clearTimeout(timeout);
  }, [focusIncidentId]);

  useEffect(() => {
    if (!expandedIncidentId) return;
    let cancelled = false;
    setComments(null);
    setCommentsError(null);
    setAuditLog([]);

    getIncident(expandedIncidentId)
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
  }, [expandedIncidentId]);

  function updateIncidentLocally(updated: Incident) {
    setIncidents((current) =>
      current ? current.map((incident) => (incident.id === updated.id ? updated : incident)) : current,
    );
    setInboxIncidents((current) =>
      current ? current.map((incident) => (incident.id === updated.id ? updated : incident)) : current,
    );
  }

  function toggleExpanded(incidentId: string) {
    setExpandedIncidentId((current) => (current === incidentId ? null : incidentId));
  }

  function handleSortClick(key: Exclude<SortKey, null>) {
    if (sortKey === key) {
      setSortReversed((current) => !current);
    } else {
      setSortKey(key);
      setSortReversed(false);
    }
  }

  function sortIcon(key: Exclude<SortKey, null>) {
    if (sortKey !== key) return <ArrowUpDown size={12} strokeWidth={1.75} aria-hidden="true" />;
    return sortReversed ? (
      <ArrowUp size={12} strokeWidth={1.75} aria-hidden="true" />
    ) : (
      <ArrowDown size={12} strokeWidth={1.75} aria-hidden="true" />
    );
  }

  async function handleStart(incident: Incident) {
    setActionError(null);
    setPendingIncidentId(incident.id);
    try {
      updateIncidentLocally(await startIncident(incident.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Le démarrage a échoué.");
    } finally {
      setPendingIncidentId(null);
    }
  }

  async function handleResolve(incident: Incident) {
    setActionError(null);
    setPendingIncidentId(incident.id);
    try {
      updateIncidentLocally(await resolveIncident(incident.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "La résolution a échoué.");
    } finally {
      setPendingIncidentId(null);
    }
  }

  async function handleArchive(incident: Incident) {
    setActionError(null);
    setPendingIncidentId(incident.id);
    try {
      updateIncidentLocally(await archiveIncident(incident.id));
      showToast("Incident archivé.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "L'archivage a échoué.");
    } finally {
      setPendingIncidentId(null);
    }
  }

  async function handleAssignProject(incident: Incident, projectId: string) {
    setActionError(null);
    setPendingIncidentId(incident.id);
    try {
      await assignIncidentProject(incident.id, projectId);
      // Il quitte définitivement la boîte de réception ; pas d'insertion dans
      // la liste principale (`incidents`) pour rester simple — la navigation
      // vers le projet suffit à l'y retrouver.
      setInboxIncidents((current) => (current ? current.filter((item) => item.id !== incident.id) : current));
      setExpandedIncidentId((current) => (current === incident.id ? null : current));
      showToast("Incident rattaché au projet.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Le rattachement a échoué.");
    } finally {
      setPendingIncidentId(null);
    }
  }

  async function handleSaveDescription(incident: Incident, description: string) {
    setActionError(null);
    try {
      updateIncidentLocally(await updateIncidentDescription(incident.id, description));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "L'enregistrement a échoué.");
    }
  }

  async function handleAddComment(content: string) {
    if (!expandedIncidentId) return;
    setCommentSubmitting(true);
    setCommentsError(null);
    try {
      const comment = await addIncidentComment(expandedIncidentId, content);
      setComments((current) => (current ? [...current, comment] : [comment]));
    } catch (err) {
      setCommentsError(err instanceof Error ? err.message : "L'ajout du commentaire a échoué.");
    } finally {
      setCommentSubmitting(false);
    }
  }

  async function handleCreate(values: IncidentCreateFormValues) {
    setCreateSubmitting(true);
    setCreateError(null);

    try {
      const created = await createIncident(buildCreatePayload(values));
      setCreating(false);
      if (!effectiveProjectFilter || created.project === effectiveProjectFilter) {
        setIncidents((current) => (current ? [...current, created] : current));
      }
      showToast("Incident signalé.");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Le signalement a échoué.");
    } finally {
      setCreateSubmitting(false);
    }
  }

  function renderAccordion(incident: Incident, ownerLabel?: { projectName?: string; teamName?: string }) {
    return (
      <IncidentAccordion
        incident={incident}
        projectName={ownerLabel?.projectName}
        teamName={ownerLabel?.teamName}
        projects={projects}
        comments={comments}
        commentsError={commentsError}
        commentSubmitting={commentSubmitting}
        auditLog={auditLog}
        onAddComment={handleAddComment}
        onClose={() => setExpandedIncidentId(null)}
        onStart={handleStart}
        onResolve={handleResolve}
        onArchive={handleArchive}
        onAssignProject={handleAssignProject}
        onSaveDescription={handleSaveDescription}
        pending={pendingIncidentId === incident.id}
      />
    );
  }

  const projectNameById = new Map(projects.map((project) => [project.id, project.name]));
  const displayedIncidents = incidents ? sortIncidents(incidents, sortKey, sortReversed) : null;
  const mainColSpan = scopedProject ? 6 : 7;

  return (
    <div className="incidents-page">
      <div className="incidents-page__toolbar">
        {!scopedProject && (
          <>
            <label className="incidents-page__filter-label" htmlFor="incidents-project-filter">
              Projet
            </label>
            <select
              id="incidents-project-filter"
              className="incidents-page__filter-select"
              value={projectFilter}
              onChange={(event) => setProjectFilter(event.target.value)}
            >
              <option value="">Tous les projets</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </>
        )}

        <StatusFilterDropdown
          options={INCIDENT_STATUS_FILTER_OPTIONS}
          selected={statusFilter}
          onChange={setStatusFilter}
        />

        <button type="button" className="incidents-page__create" onClick={() => setCreating(true)}>
          <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
          Signaler un incident
        </button>
      </div>

      {actionError && <p className="incidents-page__message incidents-page__message--error">{actionError}</p>}
      {error && <p className="incidents-page__message incidents-page__message--error">{error}</p>}

      {!scopedProject && inboxIncidents && inboxIncidents.length > 0 && (
        <section className="incidents-page__inbox">
          <h2 className="incidents-page__inbox-title">
            Boîte de réception
            <span className="incidents-page__inbox-count">{inboxIncidents.length}</span>
          </h2>
          <table className="incidents-page__table">
            <thead>
              <tr>
                <th>Titre</th>
                <th>Réf.</th>
                <th>Groupe</th>
                <th>Statut</th>
                <th>Priorité</th>
                <th>Délai</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {inboxIncidents.map((incident) => (
                <IncidentRow
                  key={incident.id}
                  incident={incident}
                  ownerLabel={incident.team_name ?? "—"}
                  expanded={expandedIncidentId === incident.id}
                  onToggle={() => toggleExpanded(incident.id)}
                  onStart={() => handleStart(incident)}
                  onResolve={() => handleResolve(incident)}
                  onArchive={() => handleArchive(incident)}
                  pending={pendingIncidentId === incident.id}
                  colSpan={7}
                >
                  {expandedIncidentId === incident.id &&
                    renderAccordion(incident, { teamName: incident.team_name ?? undefined })}
                </IncidentRow>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {!error && (
        <LoadingTransition loading={incidents === null} skeleton={<SkeletonTable columns={scopedProject ? 5 : 6} rows={4} />}>
          {incidents && incidents.length === 0 && <p className="incidents-page__message">Aucun incident.</p>}

          {displayedIncidents && displayedIncidents.length > 0 && (
            <table className="incidents-page__table">
              <thead>
                <tr>
                  <th>Titre</th>
                  <th>Réf.</th>
                  {!scopedProject && <th>Projet</th>}
                  <th>Statut</th>
                  <th>
                    <button type="button" className="incidents-page__sort" onClick={() => handleSortClick("priority")}>
                      Priorité {sortIcon("priority")}
                    </button>
                  </th>
                  <th>
                    <button type="button" className="incidents-page__sort" onClick={() => handleSortClick("delay")}>
                      Délai {sortIcon("delay")}
                    </button>
                  </th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {displayedIncidents.map((incident) => (
                  <IncidentRow
                    key={incident.id}
                    incident={incident}
                    ownerLabel={
                      scopedProject
                        ? undefined
                        : ((incident.project && projectNameById.get(incident.project)) ?? "—")
                    }
                    expanded={expandedIncidentId === incident.id}
                    onToggle={() => toggleExpanded(incident.id)}
                    onStart={() => handleStart(incident)}
                    onResolve={() => handleResolve(incident)}
                    onArchive={() => handleArchive(incident)}
                    pending={pendingIncidentId === incident.id}
                    colSpan={mainColSpan}
                  >
                    {expandedIncidentId === incident.id &&
                      renderAccordion(incident, {
                        projectName: incident.project ? projectNameById.get(incident.project) : undefined,
                      })}
                  </IncidentRow>
                ))}
              </tbody>
            </table>
          )}
        </LoadingTransition>
      )}

      {creating && (
        <IncidentCreateDialog
          projects={projects}
          defaultProjectId={effectiveProjectFilter || undefined}
          submitting={createSubmitting}
          error={createError}
          onCancel={() => {
            setCreating(false);
            setCreateError(null);
          }}
          onSubmit={handleCreate}
        />
      )}
    </div>
  );
}
