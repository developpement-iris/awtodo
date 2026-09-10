import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { createProjectVersion, getProjectVersions } from "../../api/client";
import { Combobox } from "../../components/Combobox";
import { useToast } from "../../context/ToastContext";
import type { Project, ProjectVersion } from "../../types/watodo";
import { KanbanBoard } from "./KanbanBoard";
import { RoadmapView } from "./RoadmapView";
import "./TasksTab.css";

type View = "kanban" | "roadmap";

interface TasksTabProps {
  project: Project;
}

export function TasksTab({ project }: TasksTabProps) {
  const { showToast } = useToast();
  const [view, setView] = useState<View>("kanban");
  const [versions, setVersions] = useState<ProjectVersion[]>([]);
  // La version courante par défaut — connue directement depuis `project`,
  // pas besoin d'attendre la liste des versions pour l'afficher (voir
  // docs/modeles-et-api.md > "ProjectVersion").
  const [versionId, setVersionId] = useState<string | undefined>(project.current_version_id ?? undefined);
  const [creatingVersion, setCreatingVersion] = useState(false);
  const [newVersionLabel, setNewVersionLabel] = useState("");
  const [versionSubmitting, setVersionSubmitting] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);

  useEffect(() => {
    setVersionId(project.current_version_id ?? undefined);
  }, [project.id, project.current_version_id]);

  useEffect(() => {
    getProjectVersions(project.id)
      .then(setVersions)
      .catch(() => undefined);
  }, [project.id]);

  async function handleCreateVersion() {
    if (!newVersionLabel.trim()) return;
    setVersionSubmitting(true);
    setVersionError(null);
    try {
      const created = await createProjectVersion(project.id, newVersionLabel.trim());
      setVersions((current) => [...current, created]);
      setVersionId(created.id);
      setNewVersionLabel("");
      setCreatingVersion(false);
      showToast("Version créée.");
    } catch (err) {
      setVersionError(err instanceof Error ? err.message : "La création a échoué.");
    } finally {
      setVersionSubmitting(false);
    }
  }

  return (
    <div className="tasks-tab">
      <div className="tasks-tab__toolbar">
        <div className="tasks-tab__toggle" role="group" aria-label="Vue des tâches">
          <button
            type="button"
            className={`tasks-tab__toggle-btn${view === "kanban" ? " tasks-tab__toggle-btn--active" : ""}`}
            onClick={() => setView("kanban")}
          >
            Kanban
          </button>
          <button
            type="button"
            className={`tasks-tab__toggle-btn${view === "roadmap" ? " tasks-tab__toggle-btn--active" : ""}`}
            onClick={() => setView("roadmap")}
          >
            Roadmap
          </button>
        </div>

        <div className="tasks-tab__version">
          <span className="tasks-tab__version-select">
            <Combobox
              options={versions.map((version) => ({
                value: version.id,
                label: `${version.label}${version.is_current ? " · courante" : ""}`,
              }))}
              value={versionId ?? ""}
              onChange={setVersionId}
              clearable={false}
            />
          </span>
          {versionId && versionId !== project.current_version_id && (
            <span className="tasks-tab__version-note">Version passée — informationnel</span>
          )}
          {project.permissions.can_create_version && !creatingVersion && (
            <button
              type="button"
              className="tasks-tab__version-create-trigger"
              onClick={() => setCreatingVersion(true)}
              aria-label="Créer une version"
              title="Créer une version"
            >
              <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
            </button>
          )}
          {creatingVersion && (
            <div className="tasks-tab__version-create">
              <input
                type="text"
                placeholder="Libellé (ex. Sprint 2)"
                value={newVersionLabel}
                onChange={(event) => setNewVersionLabel(event.target.value)}
                autoFocus
              />
              <button type="button" onClick={handleCreateVersion} disabled={versionSubmitting || !newVersionLabel.trim()}>
                Créer
              </button>
              <button
                type="button"
                onClick={() => {
                  setCreatingVersion(false);
                  setNewVersionLabel("");
                  setVersionError(null);
                }}
                disabled={versionSubmitting}
              >
                Annuler
              </button>
            </div>
          )}
        </div>
      </div>

      {versionError && <p className="tasks-tab__version-error">{versionError}</p>}

      {view === "kanban" ? (
        <KanbanBoard project={project} versionId={versionId} />
      ) : (
        <RoadmapView project={project} versionId={versionId} />
      )}
    </div>
  );
}
