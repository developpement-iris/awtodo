import { Flag } from "lucide-react";
import { StatusBadge } from "../../components/StatusBadge";
import { projectPhaseIcon } from "../../lib/badges";
import type { Project } from "../../types/watodo";

/** Pastille de la phase actuelle : la phase personnalisée en cours (session
 * du 2026-11-16) si le projet en a, sinon la phase à 4 valeurs fixes. */
export function ProjectPhaseBadge({ project }: { project: Pick<Project, "phase" | "phase_display" | "current_phase"> }) {
  if (project.current_phase) {
    return <StatusBadge label={project.current_phase.name} tone="neutral" icon={Flag} />;
  }
  if (!project.phase) return null;
  return (
    <StatusBadge label={project.phase_display ?? project.phase} tone="neutral" icon={projectPhaseIcon(project.phase)} />
  );
}
