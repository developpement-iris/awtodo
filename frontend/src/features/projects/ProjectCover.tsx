import { useEffect, useState } from "react";
import { getProjectCoverUrl } from "../../api/client";
import { projectPhaseIcon } from "../../lib/badges";
import { initials } from "../../lib/initials";
import { coverImageSrc } from "../../lib/projectCovers";
import type { Project } from "../../types/watodo";
import { coverTone } from "./projectDisplay";
import "./ProjectCover.css";

type CoverProject = Pick<Project, "id" | "name" | "phase" | "cover_image" | "cover_updated_at">;

// URL de l'image importée d'un projet (récupérée avec le jeton, en cache).
function useUploadedCoverUrl(project: CoverProject): string | undefined {
  const [url, setUrl] = useState<string>();
  const version = project.cover_image === "upload" ? project.cover_updated_at : null;

  useEffect(() => {
    if (!version) {
      setUrl(undefined);
      return;
    }
    let cancelled = false;
    getProjectCoverUrl(project.id, version)
      .then((next) => {
        if (!cancelled) setUrl(next);
      })
      .catch(() => {
        if (!cancelled) setUrl(undefined);
      });
    return () => {
      cancelled = true;
    };
  }, [project.id, version]);

  return url;
}

interface ProjectCoverProps {
  project: CoverProject;
  size?: "row" | "gallery" | "mini";
  /** Aperçu local (image choisie mais pas encore envoyée). */
  previewSrc?: string;
}

/**
 * Visuel d'identification d'un projet (session du 2026-11-03) : image
 * importée, ou image de la bibliothèque, sinon monogramme sur une teinte
 * attribuée au projet (aussi affiché le temps du chargement). Icône de phase
 * en coin.
 */
export function ProjectCover({ project, size = "row", previewSrc }: ProjectCoverProps) {
  const PhaseIcon = project.phase ? projectPhaseIcon(project.phase) : undefined;
  const uploadedSrc = useUploadedCoverUrl(project);
  const src =
    previewSrc ?? (project.cover_image === "upload" ? uploadedSrc : coverImageSrc(project.cover_image));
  return (
    <span
      className={`project-cover project-cover--${size} project-cover--tone-${coverTone(project.id)}${src ? " project-cover--image" : ""}`}
      aria-hidden="true"
    >
      {src ? (
        <img src={src} alt="" loading="lazy" className="project-cover__image" />
      ) : (
        <span className="project-cover__monogram">{initials(project.name)}</span>
      )}
      {PhaseIcon && size !== "mini" && (
        <span className="project-cover__phase">
          <PhaseIcon size={size === "gallery" ? 14 : 11} strokeWidth={2} />
        </span>
      )}
    </span>
  );
}
