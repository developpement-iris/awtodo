import { ArrowUpRight, CalendarDays, Lock, MoreHorizontal, Star, Unlock } from "lucide-react";
import { useRef, useState } from "react";
import { AnchoredPanel } from "../../components/AnchoredPanel";
import { ProgressBar } from "../../components/ProgressBar";
import { StatusBadge } from "../../components/StatusBadge";
import { priorityTone, projectPhaseIcon, projectStatusIcon, projectStatusTone } from "../../lib/badges";
import { initials } from "../../lib/initials";
import type { Project } from "../../types/watodo";
import { ProjectCover } from "./ProjectCover";
import { deadlineLabel, memberName, projectProgress, teamLabel } from "./projectDisplay";

export interface ProjectItemProps {
  project: Project;
  favorite: boolean;
  onOpen: () => void;
  onToggleFavorite: () => void;
  onClose: () => void;
  onReopen: () => void;
}

export function ProjectBadges({ project }: { project: Project }) {
  return (
    <>
      {project.phase && (
        <StatusBadge
          label={project.phase_display ?? project.phase}
          tone="neutral"
          icon={projectPhaseIcon(project.phase)}
        />
      )}
      {project.status !== "actif" && (
        <StatusBadge
          label={project.status_display}
          tone={projectStatusTone(project.status)}
          icon={projectStatusIcon(project.status)}
        />
      )}
      {project.priority && (
        <StatusBadge label={project.priority_display ?? project.priority} tone={priorityTone(project.priority)} />
      )}
    </>
  );
}

function MemberStack({ project }: { project: Project }) {
  const shown = project.members.slice(0, 3);
  const rest = project.members.length - shown.length;
  return (
    <span className="project-members" aria-label={`${project.members.length} membre(s)`}>
      {shown.map((membership) => {
        const name = memberName(membership);
        return (
          <span key={membership.id} className="project-members__avatar" title={`${name} — ${membership.role_display}`}>
            {initials(name)}
          </span>
        );
      })}
      {rest > 0 && <span className="project-members__avatar project-members__avatar--more">+{rest}</span>}
    </span>
  );
}

function FavoriteButton({ project, favorite, onToggleFavorite }: ProjectItemProps) {
  return (
    <button
      type="button"
      className={`project-icon-button project-favorite${favorite ? " project-favorite--on" : ""}`}
      onClick={onToggleFavorite}
      aria-pressed={favorite}
      aria-label={favorite ? `Retirer ${project.name} des favoris` : `Ajouter ${project.name} aux favoris`}
    >
      <Star size={16} strokeWidth={1.75} fill={favorite ? "currentColor" : "none"} aria-hidden="true" />
    </button>
  );
}

function ActionsMenu({ project, onOpen, onClose, onReopen }: ProjectItemProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { can_close, can_reopen } = project.permissions;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="project-icon-button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Actions pour ${project.name}`}
      >
        <MoreHorizontal size={18} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {open && (
        <AnchoredPanel anchorRef={triggerRef} onClose={() => setOpen(false)} width="auto" className="project-menu">
          <div role="menu">
            <button type="button" role="menuitem" onClick={onOpen}>
              <ArrowUpRight size={15} strokeWidth={1.75} aria-hidden="true" />
              Ouvrir le projet
            </button>
            {can_close && (
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  onClose();
                }}
              >
                <Lock size={15} strokeWidth={1.75} aria-hidden="true" />
                Clôturer le projet
              </button>
            )}
            {can_reopen && (
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  onReopen();
                }}
              >
                <Unlock size={15} strokeWidth={1.75} aria-hidden="true" />
                Réouvrir le projet
              </button>
            )}
          </div>
        </AnchoredPanel>
      )}
    </>
  );
}

function progressLabel(project: Project): string {
  return `${project.tasks_done} tâche${project.tasks_done > 1 ? "s" : ""} terminée${project.tasks_done > 1 ? "s" : ""} sur ${project.tasks_total}`;
}

export function ProjectRow(props: ProjectItemProps) {
  const { project, onOpen } = props;
  const progress = projectProgress(project);
  return (
    <article className={`project-row${project.status !== "actif" ? " project-row--closed" : ""}`}>
      <button type="button" className="project-row__main" onClick={onOpen} aria-label={`Ouvrir ${project.name}`}>
        <ProjectCover project={project} />
        <span className="project-row__identity">
          <span className="project-row__name">
            {project.name}
            <ArrowUpRight size={15} strokeWidth={1.75} aria-hidden="true" className="project-row__arrow" />
            {project.status !== "actif" && (
              <StatusBadge
                label={project.status_display}
                tone={projectStatusTone(project.status)}
                icon={projectStatusIcon(project.status)}
              />
            )}
          </span>
          {project.description && <span className="project-row__description">{project.description}</span>}
          <span className="project-row__meta">
            {teamLabel(project)}
            <span aria-hidden="true">·</span>
            {project.tasks_done} / {project.tasks_total} tâches
          </span>
        </span>
      </button>
      <div className="project-row__cell" data-label="Phase">
        {project.phase ? (
          <StatusBadge
            label={project.phase_display ?? project.phase}
            tone="neutral"
            icon={projectPhaseIcon(project.phase)}
          />
        ) : (
          <span className="project-row__empty">—</span>
        )}
      </div>
      <div className="project-row__cell" data-label="Priorité">
        {project.priority ? (
          <StatusBadge label={project.priority_display ?? project.priority} tone={priorityTone(project.priority)} />
        ) : (
          <span className="project-row__empty">—</span>
        )}
      </div>
      <div className="project-row__progress" data-label="Avancement">
        <span className="project-row__progress-figures">
          <strong>{progress}%</strong>
          <span>
            {project.tasks_done} / {project.tasks_total}
          </span>
        </span>
        <ProgressBar value={progress} label={progressLabel(project)} />
      </div>
      <div className="project-row__deadline" data-label="Échéance">
        <CalendarDays size={14} strokeWidth={1.75} aria-hidden="true" />
        {deadlineLabel(project)}
      </div>
      <div className="project-row__team" data-label="Équipe">
        <MemberStack project={project} />
      </div>
      <div className="project-row__actions">
        <FavoriteButton {...props} />
        <ActionsMenu {...props} />
      </div>
    </article>
  );
}

export function ProjectGalleryCard(props: ProjectItemProps) {
  const { project, onOpen } = props;
  const progress = projectProgress(project);
  return (
    <article className={`project-tile${project.status !== "actif" ? " project-tile--closed" : ""}`}>
      <div className="project-tile__cover">
        <ProjectCover project={project} size="gallery" />
        <div className="project-tile__floating-actions">
          <FavoriteButton {...props} />
          <ActionsMenu {...props} />
        </div>
      </div>
      <button type="button" className="project-tile__main" onClick={onOpen} aria-label={`Ouvrir ${project.name}`}>
        <span className="project-tile__name">
          {project.name}
          <ArrowUpRight size={16} strokeWidth={1.75} aria-hidden="true" className="project-row__arrow" />
        </span>
        {project.description && <span className="project-tile__description">{project.description}</span>}
        <span className="project-tile__badges">
          <ProjectBadges project={project} />
        </span>
        <span className="project-tile__progress-meta">
          <span>
            Progression · {project.tasks_done}/{project.tasks_total} tâches
          </span>
          <strong>{progress}%</strong>
        </span>
        <ProgressBar value={progress} label={progressLabel(project)} />
      </button>
      <div className="project-tile__footer">
        <MemberStack project={project} />
        <span className="project-tile__deadline">
          <CalendarDays size={13} strokeWidth={1.75} aria-hidden="true" />
          {deadlineLabel(project)}
        </span>
      </div>
    </article>
  );
}
