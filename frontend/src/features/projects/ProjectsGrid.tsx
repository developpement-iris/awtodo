import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  FolderKanban,
  LayoutGrid,
  List as ListIcon,
  Plus,
  SlidersHorizontal,
  Star,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  closeProject,
  createProject,
  getProjects,
  getTeams,
  reopenProject,
  uploadProjectCover,
  type ProjectCreatePayload,
} from "../../api/client";
import { AnchoredPanel } from "../../components/AnchoredPanel";
import { Combobox } from "../../components/Combobox";
import { LoadingTransition } from "../../components/LoadingTransition";
import { SearchInput } from "../../components/SearchInput";
import { Skeleton } from "../../components/Skeleton";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import { useProjectFavorites } from "../../hooks/useProjectFavorites";
import { PROJECT_PHASE_OPTIONS, priorityRank, projectPhaseIcon } from "../../lib/badges";
import type { Project, Team } from "../../types/watodo";
import { ProjectCreateDialog, type ProjectCreateFormValues } from "./ProjectCreateDialog";
import { ProjectGalleryCard, ProjectRow } from "./ProjectListItems";
import { ProjectsRoadmap } from "./ProjectsRoadmap";
import { projectProgress } from "./projectDisplay";
import "../../components/SortableColumnHeader.css";
import "./ProjectsGrid.css";

interface ProjectsGridProps {
  onSelectProject: (project: Project) => void;
  createTrigger?: number;
}

type Lifecycle = "actif" | "cloture" | "tous";
type SortKey = "recent" | "name" | "phase" | "priority" | "progress" | "deadline" | "members";
type SortDirection = "asc" | "desc";
type ViewMode = "list" | "gallery";

const INDIVIDUAL_TEAM = "__individuel";
const VIEW_STORAGE_KEY = "awtodo:projects-view";

const LIFECYCLE_OPTIONS = [
  { value: "actif", label: "Actifs" },
  { value: "cloture", label: "Clôturés" },
  { value: "tous", label: "Tous" },
];

const SORT_OPTIONS = [
  { value: "recent", label: "Derniers ajoutés" },
  { value: "name", label: "Nom du projet" },
  { value: "phase", label: "Phase" },
  { value: "priority", label: "Priorité" },
  { value: "progress", label: "Avancement" },
  { value: "deadline", label: "Échéance proche" },
  { value: "members", label: "Taille de l'équipe" },
];

// Sens appliqué au premier clic sur une colonne (puis inversé à chaque clic) :
// le plus utile d'abord — récents, plus avancés, priorités hautes, grosses
// équipes en tête ; nom, phase et échéance dans l'ordre naturel.
const DEFAULT_DIRECTION: Record<SortKey, SortDirection> = {
  recent: "desc",
  name: "asc",
  phase: "asc",
  priority: "desc",
  progress: "desc",
  deadline: "asc",
  members: "desc",
};

const LIST_COLUMNS: { key: SortKey; label: string }[] = [
  { key: "name", label: "Projet" },
  { key: "phase", label: "Phase" },
  { key: "priority", label: "Priorité" },
  { key: "progress", label: "Avancement" },
  { key: "deadline", label: "Échéance" },
  { key: "members", label: "Équipe" },
];

const PHASE_ORDER: string[] = PROJECT_PHASE_OPTIONS.map((option) => option.value);

function statusesFor(lifecycle: Lifecycle): string[] {
  return lifecycle === "tous" ? ["actif", "cloture"] : [lifecycle];
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
  if (values.phase) payload.phase = values.phase;
  // « upload » n'est pas un choix direct : l'image est envoyée après création.
  if (values.cover_image && values.cover_image !== "upload") payload.cover_image = values.cover_image;
  if (values.team) payload.team = values.team;
  if (values.member_ids.length > 0) payload.member_ids = values.member_ids;
  return payload;
}

/** Valeur de tri d'un projet ; `null` = non renseigné, toujours en dernier. */
function sortValue(project: Project, key: SortKey): string | number | null {
  switch (key) {
    case "recent":
      return project.created_at;
    case "name":
      return project.name;
    case "phase":
      return project.phase ? PHASE_ORDER.indexOf(project.phase) : null;
    case "priority":
      return project.priority ? priorityRank(project.priority) : null;
    case "progress":
      return project.tasks_total > 0 ? projectProgress(project) : null;
    case "deadline":
      return project.deadline;
    case "members":
      return project.members.length;
  }
}

function compareProjects(a: Project, b: Project, key: SortKey, direction: SortDirection): number {
  const left = sortValue(a, key);
  const right = sortValue(b, key);
  if (left === null || right === null) {
    if (left !== right) return left === null ? 1 : -1;
  } else {
    const diff =
      typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left).localeCompare(String(right), "fr", { sensitivity: "base" });
    if (diff !== 0) return direction === "asc" ? diff : -diff;
  }
  // Égalité : ordre alphabétique, pour un affichage stable.
  return a.name.localeCompare(b.name, "fr", { sensitivity: "base" });
}

function readViewMode(): ViewMode {
  try {
    return window.localStorage.getItem(VIEW_STORAGE_KEY) === "gallery" ? "gallery" : "list";
  } catch {
    return "list";
  }
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

  const [lifecycle, setLifecycle] = useState<Lifecycle>("actif");
  const [query, setQuery] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [phaseFilter, setPhaseFilter] = useState("");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: "recent",
    direction: DEFAULT_DIRECTION.recent,
  });

  function sortBy(key: SortKey) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: DEFAULT_DIRECTION[key] },
    );
  }
  const [viewMode, setViewMode] = useState<ViewMode>(readViewMode);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filtersRef = useRef<HTMLButtonElement>(null);
  const [favorites, toggleFavorite] = useProjectFavorites();

  useEffect(() => {
    if (createTrigger > 0) setCreating(true);
  }, [createTrigger]);

  useEffect(() => {
    let cancelled = false;
    setProjects(null);
    setError(null);

    getProjects({ status: statusesFor(lifecycle) })
      .then((data) => {
        if (!cancelled) setProjects(data);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger les projets. Vérifiez que l'API est démarrée.");
      });

    return () => {
      cancelled = true;
    };
  }, [lifecycle]);

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(VIEW_STORAGE_KEY, viewMode);
    } catch {
      // ignore — la vue choisie ne persistera pas au rechargement.
    }
  }, [viewMode]);

  async function handleCreate(values: ProjectCreateFormValues) {
    setCreateSubmitting(true);
    setCreateError(null);

    try {
      let created = await createProject(buildCreatePayload(values));
      if (values.cover_image === "upload" && values.cover_file) {
        try {
          created = await uploadProjectCover(created.id, values.cover_file);
        } catch (err) {
          showToast(err instanceof Error ? `Projet créé, mais image refusée : ${err.message}` : "Image refusée.");
        }
      }
      setCreating(false);
      setProjects((current) => (current ? [created, ...current] : current));
      showToast("Projet créé.");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "La création a échoué.");
    } finally {
      setCreateSubmitting(false);
    }
  }

  // Après clôture/réouverture : remplacé en place, ou retiré si le filtre
  // de statut courant ne le montre plus.
  function applyLifecycleChange(updated: Project) {
    const visible = statusesFor(lifecycle).includes(updated.status);
    setProjects((current) =>
      current
        ? visible
          ? current.map((p) => (p.id === updated.id ? updated : p))
          : current.filter((p) => p.id !== updated.id)
        : current,
    );
  }

  async function handleClose(project: Project) {
    try {
      applyLifecycleChange(await closeProject(project.id));
      showToast("Projet clôturé.");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "La clôture a échoué.");
    }
  }

  async function handleReopen(project: Project) {
    try {
      applyLifecycleChange(await reopenProject(project.id));
      showToast("Projet réouvert.");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "La réouverture a échoué.");
    }
  }

  function resetFilters() {
    setQuery("");
    setTeamFilter("");
    setPhaseFilter("");
    setFavoritesOnly(false);
  }

  const loaded = useMemo(() => projects ?? [], [projects]);

  const teamOptions = useMemo(() => {
    const byId = new Map<string, string>();
    for (const project of loaded) if (project.team && project.team_name) byId.set(project.team, project.team_name);
    const options = [...byId.entries()]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));
    if (loaded.some((project) => project.team === null)) {
      options.push({ value: INDIVIDUAL_TEAM, label: "Projets individuels" });
    }
    return options;
  }, [loaded]);

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return loaded
      .filter((project) => {
        if (favoritesOnly && !favorites.has(project.id)) return false;
        if (teamFilter === INDIVIDUAL_TEAM ? project.team !== null : teamFilter && project.team !== teamFilter) {
          return false;
        }
        if (phaseFilter && project.phase !== phaseFilter) {
          return false;
        }
        if (needle && !`${project.name} ${project.description}`.toLowerCase().includes(needle)) return false;
        return true;
      })
      .sort((a, b) => compareProjects(a, b, sort.key, sort.direction));
  }, [loaded, query, teamFilter, phaseFilter, favoritesOnly, favorites, sort]);

  const favoriteCount = loaded.filter((project) => favorites.has(project.id)).length;
  const phaseCounts = PROJECT_PHASE_OPTIONS.map((option) => ({
    ...option,
    count: loaded.filter((project) => project.phase === option.value).length,
  }));
  const hasFilters = Boolean(query || teamFilter || phaseFilter || favoritesOnly);
  const myTeams = teams.filter((team) => currentUser?.teams.includes(team.id));
  const teamFilterLabel = teamOptions.find((option) => option.value === teamFilter)?.label;
  const phaseFilterLabel = PROJECT_PHASE_OPTIONS.find((option) => option.value === phaseFilter)?.label;

  function itemProps(project: Project) {
    return {
      project,
      favorite: favorites.has(project.id),
      onOpen: () => onSelectProject(project),
      onToggleFavorite: () => toggleFavorite(project.id),
      onClose: () => handleClose(project),
      onReopen: () => handleReopen(project),
    };
  }

  return (
    <div className="projects-page">
      <div className="projects-page__heading">
        <div>
          <h1>
            Vos projets<span className="projects-page__dot">.</span>
          </h1>
          <p>Repérez, filtrez et suivez chaque projet.</p>
        </div>
        <button type="button" className="projects-page__new" onClick={() => setCreating(true)}>
          <Plus size={17} strokeWidth={2} aria-hidden="true" />
          Nouveau projet
        </button>
      </div>

      <section className="projects-stats" aria-label="Synthèse par phase">
        <button
          type="button"
          className={`projects-stat${phaseFilter === "" ? " projects-stat--active" : ""}`}
          onClick={() => setPhaseFilter("")}
          aria-pressed={phaseFilter === ""}
        >
          <FolderKanban size={15} strokeWidth={1.75} aria-hidden="true" />
          <strong>{String(loaded.length).padStart(2, "0")}</strong>
          <span>{lifecycle === "cloture" ? "Clôturés" : lifecycle === "tous" ? "Projets" : "Actifs"}</span>
        </button>
        {phaseCounts.map((phase) => {
          const Icon = projectPhaseIcon(phase.value);
          return (
            <button
              key={phase.value}
              type="button"
              className={`projects-stat${phaseFilter === phase.value ? " projects-stat--active" : ""}`}
              onClick={() => setPhaseFilter(phaseFilter === phase.value ? "" : phase.value)}
              aria-pressed={phaseFilter === phase.value}
            >
              {Icon && <Icon size={15} strokeWidth={1.75} aria-hidden="true" />}
              <strong>{String(phase.count).padStart(2, "0")}</strong>
              <span>{phase.label}</span>
            </button>
          );
        })}
      </section>

      <section className="projects-directory" aria-labelledby="projects-directory-title">
        <div className="projects-directory__heading">
          <h2 id="projects-directory-title">Répertoire des projets</h2>
          <span>
            {shown.length} projet{shown.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="projects-toolbar">
          <SearchInput value={query} onChange={setQuery} placeholder="Rechercher un projet…" />
          <div className="projects-toolbar__actions">
            <div className="projects-view-switch" role="group" aria-label="Mode d'affichage">
              <button
                type="button"
                className={viewMode === "list" ? "is-active" : ""}
                aria-pressed={viewMode === "list"}
                aria-label="Vue liste"
                onClick={() => setViewMode("list")}
              >
                <ListIcon size={16} strokeWidth={1.75} aria-hidden="true" />
              </button>
              <button
                type="button"
                className={viewMode === "gallery" ? "is-active" : ""}
                aria-pressed={viewMode === "gallery"}
                aria-label="Vue galerie"
                onClick={() => setViewMode("gallery")}
              >
                <LayoutGrid size={16} strokeWidth={1.75} aria-hidden="true" />
              </button>
            </div>

            <button
              type="button"
              className={`projects-toolbar__button${favoritesOnly ? " is-active" : ""}`}
              aria-pressed={favoritesOnly}
              onClick={() => setFavoritesOnly((value) => !value)}
            >
              <Star size={15} strokeWidth={1.75} fill={favoritesOnly ? "currentColor" : "none"} aria-hidden="true" />
              Favoris
              <span className="projects-toolbar__count">{favoriteCount}</span>
            </button>

            <button
              ref={filtersRef}
              type="button"
              className={`projects-toolbar__button${teamFilter || lifecycle !== "actif" ? " is-active" : ""}`}
              aria-expanded={filtersOpen}
              onClick={() => setFiltersOpen((value) => !value)}
            >
              <SlidersHorizontal size={15} strokeWidth={1.75} aria-hidden="true" />
              Filtres
            </button>
            {filtersOpen && (
              <AnchoredPanel
                anchorRef={filtersRef}
                onClose={() => setFiltersOpen(false)}
                width="auto"
                className="projects-filters"
              >
                <div className="projects-filters__heading">
                  <strong>Affiner les projets</strong>
                  <button
                    type="button"
                    className="projects-filters__close"
                    aria-label="Fermer les filtres"
                    onClick={() => setFiltersOpen(false)}
                  >
                    <X size={15} strokeWidth={1.75} aria-hidden="true" />
                  </button>
                </div>
                <label className="projects-filters__field">
                  <span>Statut</span>
                  <Combobox
                    options={LIFECYCLE_OPTIONS}
                    value={lifecycle}
                    onChange={(value) => setLifecycle(value as Lifecycle)}
                    clearable={false}
                  />
                </label>
                <label className="projects-filters__field">
                  <span>Groupe</span>
                  <Combobox
                    options={[{ value: "", label: "Tous les groupes" }, ...teamOptions]}
                    value={teamFilter}
                    onChange={setTeamFilter}
                    placeholder="Tous les groupes"
                  />
                </label>
                <button
                  type="button"
                  className="projects-filters__reset"
                  onClick={() => {
                    resetFilters();
                    setLifecycle("actif");
                  }}
                >
                  Réinitialiser les filtres
                </button>
              </AnchoredPanel>
            )}

            <span className="projects-toolbar__sort">
              <Combobox
                options={SORT_OPTIONS}
                value={sort.key}
                onChange={(value) => setSort({ key: value as SortKey, direction: DEFAULT_DIRECTION[value as SortKey] })}
                clearable={false}
              />
            </span>
            <button
              type="button"
              className="projects-toolbar__button projects-toolbar__direction"
              onClick={() => sortBy(sort.key)}
              aria-label={sort.direction === "asc" ? "Ordre croissant — inverser" : "Ordre décroissant — inverser"}
              title={sort.direction === "asc" ? "Croissant" : "Décroissant"}
            >
              {sort.direction === "asc" ? (
                <ArrowUp size={15} strokeWidth={1.75} aria-hidden="true" />
              ) : (
                <ArrowDown size={15} strokeWidth={1.75} aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {hasFilters && (
          <div className="projects-active-filters">
            {teamFilterLabel && (
              <button type="button" onClick={() => setTeamFilter("")}>
                {teamFilterLabel}
                <X size={12} strokeWidth={2} aria-label="Retirer" />
              </button>
            )}
            {phaseFilterLabel && (
              <button type="button" onClick={() => setPhaseFilter("")}>
                {phaseFilterLabel}
                <X size={12} strokeWidth={2} aria-label="Retirer" />
              </button>
            )}
            {favoritesOnly && (
              <button type="button" onClick={() => setFavoritesOnly(false)}>
                Favoris
                <X size={12} strokeWidth={2} aria-label="Retirer" />
              </button>
            )}
            <span>
              {shown.length} résultat{shown.length !== 1 ? "s" : ""}
            </span>
          </div>
        )}

        {error && <p className="projects-page__message projects-page__message--error">{error}</p>}

        {!error && (
          <LoadingTransition
            loading={projects === null}
            skeleton={
              <div className="projects-list">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="project-row project-row--skeleton">
                    <Skeleton width="72px" height="52px" />
                    <div className="project-row__skeleton-copy">
                      <Skeleton width="40%" height="16px" />
                      <Skeleton width="70%" />
                    </div>
                  </div>
                ))}
              </div>
            }
          >
            {shown.length > 0 ? (
              viewMode === "list" ? (
                <>
                  <div className="projects-list__head" role="group" aria-label="Trier par colonne">
                    {LIST_COLUMNS.map((column) => {
                      const active = sort.key === column.key;
                      return (
                        <button
                          key={column.key}
                          type="button"
                          className={`sortable-header${active ? " sortable-header--active" : ""}`}
                          onClick={() => sortBy(column.key)}
                          aria-pressed={active}
                          aria-label={`Trier par ${column.label.toLowerCase()}${active ? (sort.direction === "asc" ? ", croissant" : ", décroissant") : ""}`}
                        >
                          {column.label}
                          {active ? (
                            sort.direction === "asc" ? (
                              <ArrowUp size={12} strokeWidth={1.75} aria-hidden="true" />
                            ) : (
                              <ArrowDown size={12} strokeWidth={1.75} aria-hidden="true" />
                            )
                          ) : (
                            <ArrowUpDown
                              size={12}
                              strokeWidth={1.75}
                              aria-hidden="true"
                              className="sortable-header__idle"
                            />
                          )}
                        </button>
                      );
                    })}
                    <span />
                  </div>
                  <div className="projects-list">
                    {shown.map((project) => (
                      <ProjectRow key={project.id} {...itemProps(project)} />
                    ))}
                  </div>
                </>
              ) : (
                <div className="projects-gallery">
                  {shown.map((project) => (
                    <ProjectGalleryCard key={project.id} {...itemProps(project)} />
                  ))}
                </div>
              )
            ) : (
              <div className="projects-empty">
                <FolderKanban size={28} strokeWidth={1.5} aria-hidden="true" />
                <h3>{hasFilters ? "Aucun projet ne correspond" : "Aucun projet pour l'instant"}</h3>
                <p>{hasFilters ? "Essayez un autre mot-clé ou élargissez vos filtres." : "Créez le premier."}</p>
                <button type="button" onClick={hasFilters ? resetFilters : () => setCreating(true)}>
                  {hasFilters ? "Réinitialiser les filtres" : "Créer un projet"}
                </button>
              </div>
            )}
          </LoadingTransition>
        )}
      </section>

      {projects !== null && <ProjectsRoadmap projects={loaded} onOpen={onSelectProject} />}

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

