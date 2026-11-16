import { ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { Combobox } from "../../components/Combobox";
import { PRIORITY_ORDER, PROJECT_PHASE_OPTIONS } from "../../lib/badges";
import { categoryKey } from "../../lib/categoryKey";
import type { Project } from "../../types/watodo";
import { ProjectCover } from "./ProjectCover";
import { ProjectsWorkload } from "./ProjectsWorkload";
import { coverTone, memberName, parseIsoDate, projectProgress, teamLabel } from "./projectDisplay";
import "./ProjectCover.css";
import { projectPhaseLabel } from "./projectDisplay";

const DAY_MS = 24 * 60 * 60 * 1000;
const ZOOM_STORAGE_KEY = "awtodo:projects-gantt-zoom";
const GROUP_STORAGE_KEY = "awtodo:projects-gantt-group";
const START_FORMAT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });
const INDIVIDUAL_TEAM = "__individuel__";
const NONE = "__aucun__";

type Unit = "day" | "week" | "month" | "quarter" | "year";
type Zoom = "week" | "month" | "quarter" | "year";
type GroupBy = "none" | "domain" | "service" | "team" | "phase";
type View = "gantt" | "workload";

// Chaque échelle affiche UNE période qui occupe toute la largeur du
// diagramme (on navigue de période en période), découpée en graduations.
const ZOOMS: Record<Zoom, { label: string; minor: Unit }> = {
  week: { label: "Semaine", minor: "day" },
  month: { label: "Mois", minor: "day" },
  quarter: { label: "Trimestre", minor: "week" },
  year: { label: "Année", minor: "month" },
};
const ZOOM_ORDER: Zoom[] = ["week", "month", "quarter", "year"];

const GROUP_OPTIONS: { value: GroupBy; label: string }[] = [
  { value: "none", label: "Sans regroupement" },
  { value: "domain", label: "Par domaine" },
  { value: "service", label: "Par service" },
  { value: "team", label: "Par groupe" },
  { value: "phase", label: "Par phase" },
];

const PRIORITY_LABELS: Record<string, string> = {
  basse: "Basse",
  moyenne: "Moyenne",
  haute: "Haute",
  critique: "Critique",
};

interface Filters {
  domain: string;
  service: string;
  team: string;
  phase: string;
  priority: string;
  person: string;
}

const EMPTY_FILTERS: Filters = { domain: "", service: "", team: "", phase: "", priority: "", person: "" };

interface GanttItem {
  project: Project;
  start: Date;
  /** `null` : projet déjà en production, barre ouverte vers la droite. */
  end: Date | null;
  late: boolean;
}

interface Segment {
  key: string;
  label: string;
  /** Position et largeur en % de la période affichée. */
  offset: number;
  width: number;
  weekend?: boolean;
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function daysBetween(a: Date, b: Date): number {
  return Math.round((startOfDay(b).getTime() - startOfDay(a).getTime()) / DAY_MS);
}

function unitStart(date: Date, unit: Unit): Date {
  const d = startOfDay(date);
  switch (unit) {
    case "day":
      return d;
    case "week": {
      const weekday = d.getDay();
      d.setDate(d.getDate() - (weekday === 0 ? 6 : weekday - 1));
      return d;
    }
    case "month":
      return new Date(d.getFullYear(), d.getMonth(), 1);
    case "quarter":
      return new Date(d.getFullYear(), Math.floor(d.getMonth() / 3) * 3, 1);
    case "year":
      return new Date(d.getFullYear(), 0, 1);
  }
}

function shiftUnit(date: Date, unit: Unit, step: number): Date {
  const d = new Date(date);
  if (unit === "day") d.setDate(d.getDate() + step);
  else if (unit === "week") d.setDate(d.getDate() + 7 * step);
  else if (unit === "month") d.setMonth(d.getMonth() + step);
  else if (unit === "quarter") d.setMonth(d.getMonth() + 3 * step);
  else d.setFullYear(d.getFullYear() + step);
  return d;
}

function isoWeek(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / DAY_MS + 1) / 7);
}

const MONTH_LONG = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
const MONTH_SHORT = new Intl.DateTimeFormat("fr-FR", { month: "short" });
const WEEKDAY_SHORT = new Intl.DateTimeFormat("fr-FR", { weekday: "short" });
const DAY_MONTH = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

function periodLabel(start: Date, zoom: Zoom): string {
  switch (zoom) {
    case "week": {
      const end = shiftUnit(start, "day", 6);
      return `Semaine ${isoWeek(start)} · ${DAY_MONTH.format(start)} – ${DAY_MONTH.format(end)} ${end.getFullYear()}`;
    }
    case "month":
      return MONTH_LONG.format(start);
    case "quarter":
      return `T${Math.floor(start.getMonth() / 3) + 1} ${start.getFullYear()}`;
    case "year":
      return String(start.getFullYear());
  }
}

function minorLabel(date: Date, zoom: Zoom): string {
  if (zoom === "week") return `${WEEKDAY_SHORT.format(date)} ${date.getDate()}`;
  if (zoom === "month") return String(date.getDate());
  if (zoom === "quarter") return `S${isoWeek(date)}`;
  return MONTH_SHORT.format(date);
}

function buildSegments(periodStart: Date, periodEnd: Date, zoom: Zoom): Segment[] {
  const unit = ZOOMS[zoom].minor;
  const total = daysBetween(periodStart, periodEnd);
  const segments: Segment[] = [];
  let cursor = unitStart(periodStart, unit);
  while (cursor < periodEnd) {
    const next = shiftUnit(cursor, unit, 1);
    // Une semaine peut chevaucher le début/la fin du trimestre : rognée.
    const from = cursor < periodStart ? periodStart : cursor;
    const to = next > periodEnd ? periodEnd : next;
    segments.push({
      key: cursor.toISOString(),
      label: minorLabel(cursor, zoom),
      offset: (daysBetween(periodStart, from) / total) * 100,
      width: (daysBetween(from, to) / total) * 100,
      weekend: unit === "day" && (cursor.getDay() === 0 || cursor.getDay() === 6),
    });
    cursor = next;
  }
  return segments;
}

function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const saved = window.localStorage.getItem(key);
    if (saved && (allowed as readonly string[]).includes(saved)) return saved as T;
  } catch {
    // ignore — valeur par défaut.
  }
  return fallback;
}

function store(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // ignore — le choix ne persistera pas au rechargement.
  }
}

/** Personnes qui travaillent sur le projet : membres et chefs de projet, jamais les lecteurs. */
function contributors(project: Project) {
  return project.members.filter((membership) => membership.role !== "lecteur");
}

function matches(project: Project, filters: Filters): boolean {
  if (filters.domain && categoryKey(project.domain) !== filters.domain) return false;
  if (filters.service && !project.services.some((service) => categoryKey(service) === filters.service)) return false;
  if (filters.team === INDIVIDUAL_TEAM ? project.team !== null : filters.team && project.team !== filters.team) {
    return false;
  }
  if (filters.phase && phaseKey(project) !== filters.phase) return false;
  if (filters.priority && (project.priority ?? NONE) !== filters.priority) return false;
  if (filters.person && !contributors(project).some((membership) => membership.user.id === filters.person)) {
    return false;
  }
  return true;
}

/** Clé de la phase actuelle d'un projet (personnalisée ou fixe), `NONE` sans phase. */
function phaseKey(project: Project): string {
  const label = projectPhaseLabel(project);
  return label ? categoryKey(label) : NONE;
}

/** Rang d'affichage d'une phase : les 4 phases fixes dans l'ordre d'avancement, puis les autres. */
function phaseRank(label: string): number {
  const index = PROJECT_PHASE_OPTIONS.findIndex((option) => categoryKey(option.label) === categoryKey(label));
  return index === -1 ? PROJECT_PHASE_OPTIONS.length : index;
}

/** Libellés distincts (casse et accents ignorés), triés. */
function distinctOptions(values: string[]): { value: string; label: string }[] {
  const byKey = new Map<string, string>();
  for (const value of values) if (value && !byKey.has(categoryKey(value))) byKey.set(categoryKey(value), value);
  return [...byKey.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label, "fr"));
}

interface Group {
  key: string;
  label: string;
  items: GanttItem[];
}

function groupItems(items: GanttItem[], groupBy: GroupBy): Group[] {
  if (groupBy === "none") return [{ key: "all", label: "", items }];
  const groups = new Map<string, Group>();
  const push = (key: string, label: string, item: GanttItem) => {
    if (!groups.has(key)) groups.set(key, { key, label, items: [] });
    groups.get(key)!.items.push(item);
  };
  for (const item of items) {
    const { project } = item;
    if (groupBy === "domain") {
      push(project.domain ? categoryKey(project.domain) : NONE, project.domain || "Sans domaine", item);
    } else if (groupBy === "service") {
      // Un projet à plusieurs services apparaît dans chacun.
      if (project.services.length === 0) push(NONE, "Sans service", item);
      for (const service of project.services) push(categoryKey(service), service, item);
    } else if (groupBy === "team") {
      push(project.team ?? NONE, project.team_name ?? "Projets individuels", item);
    } else {
      push(phaseKey(project), projectPhaseLabel(project) ?? "Phase non définie", item);
    }
  }
  return [...groups.values()].sort((a, b) => {
    if (a.key === NONE || b.key === NONE) return a.key === NONE ? 1 : -1;
    if (groupBy === "phase" && phaseRank(a.label) !== phaseRank(b.label)) return phaseRank(a.label) - phaseRank(b.label);
    return a.label.localeCompare(b.label, "fr");
  });
}

interface ProjectsRoadmapProps {
  projects: Project[];
  onOpen: (project: Project) => void;
}

/**
 * Feuille de route de l'écran Projets. Deux vues sur les mêmes filtres :
 * - le Gantt (session du 2026-11-03) : une ligne par projet, la durée de vie
 *   du projet (création → échéance) et, depuis le 2026-11-16, ses phases
 *   personnalisées saisies dans l'onglet Administration ;
 * - la charge par personne (session du 2026-11-14), voir `ProjectsWorkload`.
 */
export function ProjectsRoadmap({ projects, onOpen }: ProjectsRoadmapProps) {
  const [view, setView] = useState<View>("gantt");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [groupBy, setGroupBy] = useState<GroupBy>(() =>
    readStored(GROUP_STORAGE_KEY, ["none", "domain", "service", "team", "phase"] as const, "none"),
  );

  const active = useMemo(() => projects.filter((project) => project.status === "actif"), [projects]);
  const shown = useMemo(() => active.filter((project) => matches(project, filters)), [active, filters]);
  const filtered = Object.values(filters).some(Boolean);

  const options = useMemo(() => {
    const teams = new Map<string, string>();
    const people = new Map<string, string>();
    for (const project of active) {
      if (project.team && project.team_name) teams.set(project.team, project.team_name);
      for (const membership of contributors(project)) people.set(membership.user.id, memberName(membership));
    }
    const teamOptions = [...teams.entries()]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));
    if (active.some((project) => project.team === null)) {
      teamOptions.push({ value: INDIVIDUAL_TEAM, label: "Projets individuels" });
    }
    return {
      domains: distinctOptions(active.map((project) => project.domain)),
      phases: [
        ...distinctOptions(active.map((project) => projectPhaseLabel(project) ?? "")).sort(
          (a, b) => phaseRank(a.label) - phaseRank(b.label) || a.label.localeCompare(b.label, "fr"),
        ),
        ...(active.some((project) => !projectPhaseLabel(project)) ? [{ value: NONE, label: "Non définie" }] : []),
      ],
      services: distinctOptions(active.flatMap((project) => project.services)),
      teams: teamOptions,
      people: [...people.entries()]
        .map(([value, label]) => ({ value, label }))
        .sort((a, b) => a.label.localeCompare(b.label, "fr")),
    };
  }, [active]);

  function setFilter(key: keyof Filters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function changeGroup(value: GroupBy) {
    setGroupBy(value);
    store(GROUP_STORAGE_KEY, value);
  }

  return (
    <section className="projects-roadmap" aria-labelledby="projects-roadmap-title">
      <header className="projects-roadmap__header">
        <div>
          <h2 id="projects-roadmap-title">Feuille de route</h2>
          <p>
            {view === "gantt"
              ? "Projets actifs et leurs phases, saisies dans l'onglet Administration de chaque projet."
              : "Projets en cours et demi-journées planifiées, par personne."}
          </p>
        </div>
        <div className="gantt-zoom" role="tablist" aria-label="Vue de la feuille de route">
          <button
            type="button"
            role="tab"
            aria-selected={view === "gantt"}
            className={view === "gantt" ? "is-active" : ""}
            onClick={() => setView("gantt")}
          >
            Calendrier
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === "workload"}
            className={view === "workload" ? "is-active" : ""}
            onClick={() => setView("workload")}
          >
            Charge
          </button>
        </div>
      </header>

      <div className="roadmap-filters" role="group" aria-label="Filtrer la feuille de route">
        <RoadmapFilter
          label="Domaine"
          all="Tous les domaines"
          options={options.domains}
          value={filters.domain}
          onChange={(value) => setFilter("domain", value)}
        />
        <RoadmapFilter
          label="Service"
          all="Tous les services"
          options={options.services}
          value={filters.service}
          onChange={(value) => setFilter("service", value)}
        />
        <RoadmapFilter
          label="Groupe"
          all="Tous les groupes"
          options={options.teams}
          value={filters.team}
          onChange={(value) => setFilter("team", value)}
        />
        <RoadmapFilter
          label="Phase"
          all="Toutes les phases"
          options={options.phases}
          value={filters.phase}
          onChange={(value) => setFilter("phase", value)}
        />
        <RoadmapFilter
          label="Priorité"
          all="Toutes les priorités"
          options={[
            ...[...PRIORITY_ORDER].reverse().map((value) => ({ value, label: PRIORITY_LABELS[value] })),
            { value: NONE, label: "Non définie" },
          ]}
          value={filters.priority}
          onChange={(value) => setFilter("priority", value)}
        />
        <RoadmapFilter
          label="Personne"
          all="Tout le monde"
          options={options.people}
          value={filters.person}
          onChange={(value) => setFilter("person", value)}
        />
        {view === "gantt" && (
          <label className="roadmap-filters__field">
            <span>Regrouper</span>
            <Combobox
              options={GROUP_OPTIONS}
              value={groupBy}
              onChange={(value) => changeGroup(value as GroupBy)}
              clearable={false}
            />
          </label>
        )}
        {filtered && (
          <button type="button" className="roadmap-filters__reset" onClick={() => setFilters(EMPTY_FILTERS)}>
            <RotateCcw size={13} strokeWidth={1.75} aria-hidden="true" />
            Réinitialiser
          </button>
        )}
      </div>

      {view === "gantt" ? (
        <GanttView projects={shown} groupBy={groupBy} filtered={filtered} onOpen={onOpen} />
      ) : (
        <ProjectsWorkload
          projectIds={filtered ? shown.map((project) => project.id) : null}
          personId={filters.person}
          projects={active}
          onOpen={onOpen}
        />
      )}
    </section>
  );
}

interface RoadmapFilterProps {
  label: string;
  all: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}

function RoadmapFilter({ label, all, options, value, onChange }: RoadmapFilterProps) {
  return (
    <label className="roadmap-filters__field">
      <span>{label}</span>
      <Combobox options={[{ value: "", label: all }, ...options]} value={value} onChange={onChange} placeholder={all} />
    </label>
  );
}

interface GanttViewProps {
  projects: Project[];
  groupBy: GroupBy;
  filtered: boolean;
  onOpen: (project: Project) => void;
}

function GanttView({ projects, groupBy, filtered, onOpen }: GanttViewProps) {
  const today = useMemo(() => startOfDay(new Date()), []);
  const [zoom, setZoom] = useState<Zoom>(() => readStored(ZOOM_STORAGE_KEY, ZOOM_ORDER, "quarter"));
  const [periodStart, setPeriodStart] = useState(() => unitStart(today, zoom));
  const periodEnd = shiftUnit(periodStart, zoom, 1);
  const totalDays = daysBetween(periodStart, periodEnd);
  const showsToday = today >= periodStart && today < periodEnd;
  function changeZoom(next: Zoom) {
    // Reste autour d'aujourd'hui s'il est visible, sinon autour de la
    // période actuellement consultée.
    setPeriodStart(unitStart(showsToday ? today : periodStart, next));
    setZoom(next);
    store(ZOOM_STORAGE_KEY, next);
  }

  const { items, unplaced } = useMemo(() => {
    const placed: GanttItem[] = [];
    for (const project of projects) {
      const lastPhase = project.phases[project.phases.length - 1];
      if (!project.deadline && !project.already_in_production && !lastPhase) continue;
      const start = startOfDay(new Date(project.created_at));
      // Sans échéance de projet, la dernière phase en tient lieu.
      const endIso = project.deadline ?? (project.already_in_production ? null : lastPhase?.due_date ?? null);
      const end = endIso ? parseIsoDate(endIso) : null;
      placed.push({ project, start: end && end < start ? end : start, end, late: end !== null && end < today });
    }
    placed.sort((a, b) => {
      if (!a.end) return b.end ? 1 : 0;
      if (!b.end) return -1;
      return a.end.getTime() - b.end.getTime();
    });
    return { items: placed, unplaced: projects.length - placed.length };
  }, [projects, today]);

  const groups = useMemo(() => groupItems(items, groupBy), [items, groupBy]);
  const segments = useMemo(() => buildSegments(periodStart, periodEnd, zoom), [periodStart, periodEnd, zoom]);
  const percent = (date: Date) => (daysBetween(periodStart, date) / totalDays) * 100;

  /** Position d'un intervalle [start, endExclusive[ rogné à la période, ou `null` s'il est hors période. */
  function place(start: Date, endExclusive: Date | null) {
    if (endExclusive !== null && endExclusive <= periodStart) return null;
    if (start >= periodEnd) return null;
    const clipStart = start < periodStart;
    const clipEnd = endExclusive === null || endExclusive > periodEnd;
    const left = clipStart ? 0 : percent(start);
    const right = clipEnd ? 100 : percent(endExclusive!);
    return { left, width: right - left, clipStart, clipEnd };
  }

  return (
    <>
      <div className="projects-roadmap__controls">
        <div className="gantt-zoom" role="group" aria-label="Échelle du diagramme">
          {ZOOM_ORDER.map((value) => (
            <button
              key={value}
              type="button"
              className={zoom === value ? "is-active" : ""}
              aria-pressed={zoom === value}
              onClick={() => changeZoom(value)}
            >
              {ZOOMS[value].label}
            </button>
          ))}
        </div>
        <ul className="gantt-legend" aria-label="Légende">
          <li>
            <span className="gantt-legend__swatch gantt-legend__swatch--progress" />
            Avancement
          </li>
          <li>
            <span className="gantt-legend__swatch gantt-legend__swatch--phase" />
            Phase
          </li>
          <li>
            <span className="gantt-legend__swatch gantt-legend__swatch--current" />
            Phase en cours
          </li>
          <li>
            <span className="gantt-legend__swatch gantt-legend__swatch--today" />
            Aujourd'hui
          </li>
          <li>
            <span className="gantt-legend__swatch gantt-legend__swatch--late" />
            En retard
          </li>
        </ul>
      </div>

      {items.length === 0 ? (
        <p className="projects-roadmap__empty">
          {filtered
            ? "Aucun projet ne correspond à ces filtres."
            : "Aucun projet actif n'a d'échéance pour l'instant."}
        </p>
      ) : (
        <div className="gantt">
          <div className="gantt__row gantt__row--head">
            <div className="gantt__label gantt__label--head">Projet</div>
            <div className="gantt__scale">
              <div className="gantt__period">
                <button
                  type="button"
                  className="gantt__nav"
                  onClick={() => setPeriodStart(shiftUnit(periodStart, zoom, -1))}
                  aria-label="Période précédente"
                >
                  <ChevronLeft size={16} strokeWidth={1.75} aria-hidden="true" />
                </button>
                <strong>{periodLabel(periodStart, zoom)}</strong>
                <button
                  type="button"
                  className="gantt__nav"
                  onClick={() => setPeriodStart(shiftUnit(periodStart, zoom, 1))}
                  aria-label="Période suivante"
                >
                  <ChevronRight size={16} strokeWidth={1.75} aria-hidden="true" />
                </button>
                {!showsToday && (
                  <button type="button" className="gantt__today-button" onClick={() => setPeriodStart(unitStart(today, zoom))}>
                    Aujourd'hui
                  </button>
                )}
              </div>
              <div className="gantt__ticks">
                {segments.map((segment) => (
                  <span
                    key={segment.key}
                    className={segment.weekend ? "is-weekend" : undefined}
                    style={{ left: `${segment.offset}%`, width: `${segment.width}%` }}
                  >
                    {segment.label}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="gantt__body">
            <div className="gantt__grid" aria-hidden="true">
              {segments.map((segment) => (
                <span
                  key={segment.key}
                  className={`gantt__cell${segment.weekend ? " gantt__cell--weekend" : ""}`}
                  style={{ left: `${segment.offset}%`, width: `${segment.width}%` }}
                />
              ))}
              {showsToday && (
                <span
                  className="gantt__today"
                  style={{ left: `${((daysBetween(periodStart, today) + 0.5) / totalDays) * 100}%` }}
                />
              )}
            </div>

            {groups.map((group) => (
              <div key={group.key} role="group" aria-label={group.label || undefined}>
                {group.label && (
                  <div className="gantt__group">
                    <span>{group.label}</span>
                    <small>{group.items.length}</small>
                  </div>
                )}
                {group.items.map((item) => (
                  <GanttRow
                    key={`${group.key}-${item.project.id}`}
                    item={item}
                    place={place}
                    percent={percent}
                    periodEnd={periodEnd}
                    onOpen={onOpen}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {unplaced > 0 && (
        <p className="projects-roadmap__footnote">
          {unplaced} projet{unplaced > 1 ? "s" : ""} actif{unplaced > 1 ? "s" : ""} sans échéance non placé
          {unplaced > 1 ? "s" : ""}.
        </p>
      )}
    </>
  );
}

interface GanttRowProps {
  item: GanttItem;
  place: (start: Date, endExclusive: Date | null) => { left: number; width: number; clipStart: boolean; clipEnd: boolean } | null;
  percent: (date: Date) => number;
  periodEnd: Date;
  onOpen: (project: Project) => void;
}

const ENTRY_FORMAT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

function GanttRow({ item, place, percent, periodEnd, onOpen }: GanttRowProps) {
  const { project, start, end, late } = item;
  const progress = projectProgress(project);
  const startLabel = START_FORMAT.format(start);
  // `end` vient de l'échéance du projet, ou à défaut de la dernière phase :
  // jamais `project.deadline` directement, qui peut être vide.
  const endLabel = end ? START_FORMAT.format(end) : null;
  const period = endLabel ? `du ${startLabel} au ${endLabel}` : `en production depuis le ${startLabel}`;
  const endExclusive = end ? new Date(end.getFullYear(), end.getMonth(), end.getDate() + 1) : null;
  const lifespan = place(start, endExclusive);
  // Hors période : un repère indique de quel côté se trouve le projet.
  const offscreen = lifespan ? null : start >= periodEnd ? "after" : "before";
  const phases = project.phases;
  const currentPhaseId = project.current_phase?.id;
  const detailed = phases.length > 0;
  const tone = `project-cover--tone-${coverTone(project.id)}`;

  // Avancement placé sur toute la durée du projet, puis rapporté à la
  // portion visible (sinon une barre rognée mentirait).
  let fill = progress;
  if (lifespan && endExclusive && lifespan.width > 0) {
    const span = daysBetween(start, endExclusive);
    const reachedDay = new Date(start.getFullYear(), start.getMonth(), start.getDate() + Math.round((span * progress) / 100));
    fill = Math.min(100, Math.max(0, ((percent(reachedDay) - lifespan.left) / lifespan.width) * 100));
  }

  return (
    <div className="gantt__row">
      <button type="button" className="gantt__label" onClick={() => onOpen(project)}>
        <ProjectCover project={project} size="mini" />
        <span className="gantt__label-copy">
          <strong>{project.name}</strong>
          <small>
            {teamLabel(project)}
            {projectPhaseLabel(project) && ` · ${projectPhaseLabel(project)}`}
            {detailed && ` · ${progress} %`}
          </small>
        </span>
      </button>
      <div className="gantt__track">
        {!lifespan && offscreen === "before" && (
          <span className="gantt__offscreen gantt__offscreen--before">
            <ChevronLeft size={13} strokeWidth={1.75} aria-hidden="true" />
            Échéance {endLabel}
          </span>
        )}
        {!lifespan && offscreen === "after" && (
          <span className="gantt__offscreen gantt__offscreen--after">
            Début {startLabel}
            <ChevronRight size={13} strokeWidth={1.75} aria-hidden="true" />
          </span>
        )}
        {lifespan && (
          <button
            type="button"
            className={[
              detailed ? "gantt__lifespan" : "gantt__bar",
              tone,
              end ? "" : "gantt__bar--open",
              lifespan.clipStart ? "gantt__bar--clip-start" : "",
              lifespan.clipEnd ? "gantt__bar--clip-end" : "",
              late ? "gantt__bar--late" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{ left: `${lifespan.left}%`, width: `max(8px, ${lifespan.width}%)` }}
            onClick={() => onOpen(project)}
            title={`${project.name} — ${period} · ${progress} %${late ? " · échéance dépassée" : ""}`}
            aria-label={`${project.name}, ${period}, ${progress} % des tâches terminées${late ? ", échéance dépassée" : ""}`}
          >
            {!detailed && (
              <>
                <span className="gantt__bar-progress" style={{ width: `${fill}%` }} />
                {lifespan.width >= 8 && <span className="gantt__bar-label">{progress} %</span>}
              </>
            )}
          </button>
        )}
        {phases.map((phase) => {
          const phaseStart = parseIsoDate(phase.start_date);
          const due = parseIsoDate(phase.due_date);
          const position = place(startOfDay(phaseStart), new Date(due.getFullYear(), due.getMonth(), due.getDate() + 1));
          if (!position) return null;
          const dates = `${ENTRY_FORMAT.format(phaseStart)} → ${ENTRY_FORMAT.format(due)}`;
          const current = phase.id === currentPhaseId;
          return (
            <button
              key={phase.id}
              type="button"
              className={`gantt__phase ${tone}${current ? " gantt__phase--current" : ""}${position.clipStart ? " gantt__bar--clip-start" : ""}${position.clipEnd ? " gantt__bar--clip-end" : ""}`}
              style={{ left: `${position.left}%`, width: `max(6px, ${position.width}%)` }}
              onClick={() => onOpen(project)}
              title={`${phase.name} · ${dates}${current ? " · phase en cours" : ""}`}
              aria-label={`${project.name}, phase ${phase.name}, ${dates}${current ? ", en cours" : ""}`}
            >
              {position.width >= 6 && <span>{phase.name}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
