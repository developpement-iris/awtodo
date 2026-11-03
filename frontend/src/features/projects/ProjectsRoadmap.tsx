import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import type { Project } from "../../types/watodo";
import { ProjectCover } from "./ProjectCover";
import { coverTone, formatProjectDate, parseIsoDate, projectProgress, teamLabel } from "./projectDisplay";
import "./ProjectCover.css";

const DAY_MS = 24 * 60 * 60 * 1000;
const ZOOM_STORAGE_KEY = "awtodo:projects-gantt-zoom";
const START_FORMAT = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });

type Unit = "day" | "week" | "month" | "quarter" | "year";
type Zoom = "week" | "month" | "quarter" | "year";

// Chaque échelle affiche UNE période qui occupe toute la largeur du
// diagramme (on navigue de période en période), découpée en graduations.
const ZOOMS: Record<Zoom, { label: string; minor: Unit }> = {
  week: { label: "Semaine", minor: "day" },
  month: { label: "Mois", minor: "day" },
  quarter: { label: "Trimestre", minor: "week" },
  year: { label: "Année", minor: "month" },
};
const ZOOM_ORDER: Zoom[] = ["week", "month", "quarter", "year"];

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

function readZoom(): Zoom {
  try {
    const saved = window.localStorage.getItem(ZOOM_STORAGE_KEY);
    if (saved && saved in ZOOMS) return saved as Zoom;
  } catch {
    // ignore — échelle par défaut.
  }
  return "quarter";
}

interface ProjectsRoadmapProps {
  projects: Project[];
  onOpen: (project: Project) => void;
}

/**
 * Diagramme de Gantt des projets actifs (session du 2026-11-03) : une barre
 * par projet, de sa date de création à son échéance, remplie selon
 * l'avancement des tâches. La période affichée (semaine/mois/trimestre/
 * année) occupe toute la largeur ; on se déplace d'une période à l'autre.
 * Un projet « déjà en production » n'a pas de fin ; un projet sans échéance
 * n'est pas placé.
 */
export function ProjectsRoadmap({ projects, onOpen }: ProjectsRoadmapProps) {
  const today = useMemo(() => startOfDay(new Date()), []);
  const [zoom, setZoom] = useState<Zoom>(readZoom);
  const [periodStart, setPeriodStart] = useState(() => unitStart(today, readZoom()));
  const periodEnd = shiftUnit(periodStart, zoom, 1);
  const totalDays = daysBetween(periodStart, periodEnd);
  const showsToday = today >= periodStart && today < periodEnd;

  function changeZoom(next: Zoom) {
    // Reste autour d'aujourd'hui s'il est visible, sinon autour de la
    // période actuellement consultée.
    setPeriodStart(unitStart(showsToday ? today : periodStart, next));
    setZoom(next);
    try {
      window.localStorage.setItem(ZOOM_STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }

  const { items, unplaced } = useMemo(() => {
    const active = projects.filter((project) => project.status === "actif");
    const placed: GanttItem[] = [];
    for (const project of active) {
      if (!project.deadline && !project.already_in_production) continue;
      const start = startOfDay(new Date(project.created_at));
      const end = project.deadline ? parseIsoDate(project.deadline) : null;
      placed.push({ project, start: end && end < start ? end : start, end, late: end !== null && end < today });
    }
    placed.sort((a, b) => {
      if (!a.end) return b.end ? 1 : 0;
      if (!b.end) return -1;
      return a.end.getTime() - b.end.getTime();
    });
    return { items: placed, unplaced: active.length - placed.length };
  }, [projects, today]);

  const segments = useMemo(() => buildSegments(periodStart, periodEnd, zoom), [periodStart, periodEnd, zoom]);
  const percent = (date: Date) => (daysBetween(periodStart, date) / totalDays) * 100;

  return (
    <section className="projects-roadmap" aria-labelledby="projects-roadmap-title">
      <header className="projects-roadmap__header">
        <div>
          <h2 id="projects-roadmap-title">Feuille de route</h2>
          <p>Projets actifs, de leur création à leur échéance.</p>
        </div>
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
              <span className="gantt-legend__swatch gantt-legend__swatch--today" />
              Aujourd'hui
            </li>
            <li>
              <span className="gantt-legend__swatch gantt-legend__swatch--late" />
              En retard
            </li>
          </ul>
        </div>
      </header>

      {items.length === 0 ? (
        <p className="projects-roadmap__empty">Aucun projet actif n'a d'échéance pour l'instant.</p>
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

            {items.map(({ project, start, end, late }) => {
              const progress = projectProgress(project);
              const startLabel = START_FORMAT.format(start);
              const period = end
                ? `du ${startLabel} au ${formatProjectDate(project.deadline!)}`
                : `en production depuis le ${startLabel}`;
              // Barre rognée aux bords de la période ; hors période, un repère
              // indique de quel côté se trouve le projet.
              const endExclusive = end ? shiftUnit(end, "day", 1) : null;
              const before = endExclusive !== null && endExclusive <= periodStart;
              const after = start >= periodEnd;
              const clipStart = start < periodStart;
              const clipEnd = endExclusive === null || endExclusive > periodEnd;
              const left = clipStart ? 0 : percent(start);
              const right = clipEnd ? 100 : percent(endExclusive!);
              const width = right - left;
              // Avancement placé sur toute la durée du projet, puis rapporté à
              // la portion visible (sinon une barre rognée mentirait).
              let fill = progress;
              if (endExclusive && width > 0) {
                const span = daysBetween(start, endExclusive);
                const reached = percent(shiftUnit(start, "day", Math.round((span * progress) / 100)));
                fill = Math.min(100, Math.max(0, ((reached - left) / width) * 100));
              }

              return (
                <div key={project.id} className="gantt__row">
                  <button type="button" className="gantt__label" onClick={() => onOpen(project)}>
                    <ProjectCover project={project} size="mini" />
                    <span className="gantt__label-copy">
                      <strong>{project.name}</strong>
                      <small>
                        {teamLabel(project)}
                        {project.phase_display && ` · ${project.phase_display}`}
                      </small>
                    </span>
                  </button>
                  <div className="gantt__track">
                    {before && (
                      <span className="gantt__offscreen gantt__offscreen--before">
                        <ChevronLeft size={13} strokeWidth={1.75} aria-hidden="true" />
                        Échéance {formatProjectDate(project.deadline!)}
                      </span>
                    )}
                    {after && (
                      <span className="gantt__offscreen gantt__offscreen--after">
                        Début {startLabel}
                        <ChevronRight size={13} strokeWidth={1.75} aria-hidden="true" />
                      </span>
                    )}
                    {!before && !after && (
                      <button
                        type="button"
                        className={[
                          "gantt__bar",
                          `project-cover--tone-${coverTone(project.id)}`,
                          end ? "" : "gantt__bar--open",
                          clipStart ? "gantt__bar--clip-start" : "",
                          clipEnd ? "gantt__bar--clip-end" : "",
                          late ? "gantt__bar--late" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        style={{ left: `${left}%`, width: `max(8px, ${width}%)` }}
                        onClick={() => onOpen(project)}
                        title={`${project.name} — ${period} · ${progress} %${late ? " · échéance dépassée" : ""}`}
                        aria-label={`${project.name}, ${period}, ${progress} % des tâches terminées${late ? ", échéance dépassée" : ""}`}
                      >
                        <span className="gantt__bar-progress" style={{ width: `${fill}%` }} />
                        {width >= 8 && <span className="gantt__bar-label">{progress} %</span>}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {unplaced > 0 && (
        <p className="projects-roadmap__footnote">
          {unplaced} projet{unplaced > 1 ? "s" : ""} actif{unplaced > 1 ? "s" : ""} sans échéance non placé
          {unplaced > 1 ? "s" : ""}.
        </p>
      )}
    </section>
  );
}
