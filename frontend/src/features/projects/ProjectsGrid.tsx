import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { createProject, getProjects, getTeams, type ProjectCreatePayload } from "../../api/client";
import { CreationCard } from "../../components/CreationCard";
import { LoadingTransition } from "../../components/LoadingTransition";
import { ProgressBar } from "../../components/ProgressBar";
import { Skeleton } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { StatusFilterDropdown } from "../../components/StatusFilterDropdown";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import { priorityTone, projectStatusIcon, projectStatusTone } from "../../lib/badges";
import { defaultStatusSelection, PROJECT_STATUS_FILTER_OPTIONS } from "../../lib/statusFilterOptions";
import type { Project, Team } from "../../types/watodo";
import { ProjectCreateDialog, type ProjectCreateFormValues } from "./ProjectCreateDialog";
import "./ProjectsGrid.css";

interface ProjectsGridProps {
  onSelectProject: (project: Project) => void;
  createTrigger?: number;
}

function buildCreatePayload(values: ProjectCreateFormValues): ProjectCreatePayload {
  const payload: ProjectCreatePayload = {
    name: values.name.trim(),
    project_type: values.project_type,
  };
  if (values.description.trim()) payload.description = values.description.trim();
  if (values.already_in_production) {
    payload.already_in_production = true;
  } else if (values.deadline) {
    payload.deadline = values.deadline;
  }
  if (values.priority) payload.priority = values.priority;
  if (values.team) payload.team = values.team;
  if (values.member_ids.length > 0) payload.member_ids = values.member_ids;
  return payload;
}

export function ProjectsGrid({ onSelectProject, createTrigger = 0 }: ProjectsGridProps) {
  const { currentUser } = useCurrentUser();
  const { showToast } = useToast();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState(() => defaultStatusSelection(PROJECT_STATUS_FILTER_OPTIONS));
  const [expandedProjectId, setExpandedProjectId] = useState<string | null>(null);

  useEffect(() => {
    if (createTrigger > 0) setCreating(true);
  }, [createTrigger]);

  useEffect(() => {
    let cancelled = false;
    setProjects(null);
    setError(null);

    getProjects({ status: Array.from(statusFilter) })
      .then((data) => {
        if (!cancelled) setProjects(data);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger les projets. Vérifiez que l'API est démarrée.");
      });

    return () => {
      cancelled = true;
    };
  }, [statusFilter]);

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setExpandedProjectId(null);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  async function handleCreate(values: ProjectCreateFormValues) {
    setCreateSubmitting(true);
    setCreateError(null);

    try {
      const created = await createProject(buildCreatePayload(values));
      setCreating(false);
      setProjects((current) => (current ? [...current, created] : current));
      showToast("Projet créé.");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "La création a échoué.");
    } finally {
      setCreateSubmitting(false);
    }
  }

  const myTeams = teams.filter((team) => currentUser?.teams.includes(team.id));
  const expandedProject = projects?.find((project) => project.id === expandedProjectId) ?? null;

  return (
    <div className="projects-grid-page">
      <div className="projects-grid-page__toolbar">
        <StatusFilterDropdown
          options={PROJECT_STATUS_FILTER_OPTIONS}
          selected={statusFilter}
          onChange={setStatusFilter}
        />
      </div>

      {error && <p className="projects-grid__message projects-grid__message--error">{error}</p>}

      {!error && (
        <LoadingTransition
          loading={projects === null}
          skeleton={
            <div className="projects-grid">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="project-card project-card--skeleton">
                  <Skeleton width="70%" height="19px" />
                  <Skeleton width="90%" />
                  <Skeleton width="40%" />
                </div>
              ))}
            </div>
          }
        >
          {projects !== null && projects.length === 0 && (
            <p className="projects-grid__message">Aucun projet pour l'instant — créez le premier.</p>
          )}

          {projects !== null && (
            <div className="projects-grid">
              {projects.map((project) => (
                <motion.button
                  key={project.id}
                  type="button"
                  layoutId={`project-card-${project.id}`}
                  className="project-card"
                  onClick={() => setExpandedProjectId(project.id)}
                  style={{ borderRadius: 10 }}
                >
                  <span className="project-card__name">{project.name}</span>
                  {project.description && <span className="project-card__description">{project.description}</span>}
                  <span className="project-card__badges">
                    <StatusBadge label={project.project_type_display} tone="neutral" />
                    <StatusBadge
                      label={project.status_display}
                      tone={projectStatusTone(project.status)}
                      icon={projectStatusIcon(project.status)}
                    />
                    {project.priority && (
                      <StatusBadge
                        label={project.priority_display ?? project.priority}
                        tone={priorityTone(project.priority)}
                      />
                    )}
                  </span>
                  {project.team_name && <span className="project-card__meta">Groupe : {project.team_name}</span>}
                  {project.deadline && <span className="project-card__meta">Échéance : {project.deadline}</span>}
                  {project.tasks_total > 0 && (
                    <div className="project-card__progress">
                      <ProgressBar
                        value={(project.tasks_done / project.tasks_total) * 100}
                        label={`${project.tasks_done} tâche${project.tasks_done > 1 ? "s" : ""} terminée${project.tasks_done > 1 ? "s" : ""} sur ${project.tasks_total}`}
                      />
                      <span className="project-card__progress-label">
                        {project.tasks_done}/{project.tasks_total} tâches terminées
                      </span>
                    </div>
                  )}
                </motion.button>
              ))}
              <CreationCard label="Nouveau projet" onClick={() => setCreating(true)} />
            </div>
          )}
        </LoadingTransition>
      )}

      <AnimatePresence>
        {expandedProject && (
          <div className="project-expanded__overlay">
            <motion.div
              className="project-expanded__backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setExpandedProjectId(null)}
            />
            <motion.div
              layoutId={`project-card-${expandedProject.id}`}
              style={{ borderRadius: 14 }}
              className="project-expanded"
            >
              <button
                type="button"
                className="project-expanded__close"
                onClick={() => setExpandedProjectId(null)}
                aria-label="Fermer"
              >
                <X size={16} strokeWidth={1.75} aria-hidden="true" />
              </button>

              <h2 className="project-expanded__name">{expandedProject.name}</h2>

              <div className="project-expanded__badges">
                <StatusBadge label={expandedProject.project_type_display} tone="neutral" />
                <StatusBadge
                  label={expandedProject.status_display}
                  tone={projectStatusTone(expandedProject.status)}
                  icon={projectStatusIcon(expandedProject.status)}
                />
                {expandedProject.priority && (
                  <StatusBadge
                    label={expandedProject.priority_display ?? expandedProject.priority}
                    tone={priorityTone(expandedProject.priority)}
                  />
                )}
              </div>

              <p className="project-expanded__meta">
                Groupe assigné : {expandedProject.team_name ?? "aucun (projet individuel)"}
              </p>
              {expandedProject.deadline && (
                <p className="project-expanded__meta">Échéance : {expandedProject.deadline}</p>
              )}

              <div className="project-expanded__section">
                <h3 className="project-expanded__section-title">Description</h3>
                <p className="project-expanded__description">
                  {expandedProject.description || "Aucune description."}
                </p>
              </div>

              {expandedProject.tasks_total > 0 && (
                <div className="project-expanded__progress">
                  <ProgressBar
                    value={(expandedProject.tasks_done / expandedProject.tasks_total) * 100}
                    label={`${expandedProject.tasks_done} tâche${expandedProject.tasks_done > 1 ? "s" : ""} terminée${expandedProject.tasks_done > 1 ? "s" : ""} sur ${expandedProject.tasks_total}`}
                  />
                  <span className="project-card__progress-label">
                    {expandedProject.tasks_done}/{expandedProject.tasks_total} tâches terminées
                  </span>
                </div>
              )}

              <button
                type="button"
                className="project-expanded__access"
                onClick={() => onSelectProject(expandedProject)}
              >
                Accéder au projet
              </button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {creating && (
        <ProjectCreateDialog
          myTeams={myTeams}
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
