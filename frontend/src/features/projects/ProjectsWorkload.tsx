import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getWorkload, type Workload, type WorkloadCell, type WorkloadGranularity } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import type { Project } from "../../types/watodo";

const MONTHS_SHOWN = 6;
const WEEKS_SHOWN = 8;
const HIDE_EMPTY_KEY = "awtodo:workload-hide-empty";

const MONTH_LABEL = new Intl.DateTimeFormat("fr-FR", { month: "short", year: "numeric" });
const MONTH_LONG = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
const DAY_MONTH = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function parseDay(value: string): Date {
  return new Date(`${value}T12:00:00`);
}

function firstOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function monday(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const weekday = d.getDay();
  d.setDate(d.getDate() - (weekday === 0 ? 6 : weekday - 1));
  return d;
}

/** Fenêtre affichée : 6 mois ou 8 semaines à partir de `anchor`. */
function windowFor(anchor: Date, granularity: WorkloadGranularity): { from: string; to: string } {
  if (granularity === "month") {
    const last = new Date(anchor.getFullYear(), anchor.getMonth() + MONTHS_SHOWN, 0);
    return { from: isoDate(anchor), to: isoDate(last) };
  }
  const last = new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate() + WEEKS_SHOWN * 7 - 1);
  return { from: isoDate(anchor), to: isoDate(last) };
}

function shift(anchor: Date, granularity: WorkloadGranularity, step: number): Date {
  if (granularity === "month") return new Date(anchor.getFullYear(), anchor.getMonth() + step, 1);
  return new Date(anchor.getFullYear(), anchor.getMonth(), anchor.getDate() + 7 * step);
}

function periodHeading(key: string, start: string, granularity: WorkloadGranularity): string {
  if (granularity === "month") return MONTH_LABEL.format(parseDay(start));
  return `S${key.split("-W")[1]}`;
}

function periodLong(start: string, end: string, granularity: WorkloadGranularity): string {
  if (granularity === "month") return MONTH_LONG.format(parseDay(start));
  return `semaine du ${DAY_MONTH.format(parseDay(start))} au ${DAY_MONTH.format(parseDay(end))}`;
}

function personName(user: Workload["people"][number]["user"]): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

/** Intensité de 0 à 4, rapportée à la capacité (2 demi-journées par jour ouvré). */
function level(cell: WorkloadCell | undefined, capacity: number): number {
  if (!cell || cell.half_days === 0 || capacity === 0) return 0;
  const ratio = cell.half_days / capacity;
  if (ratio <= 0.25) return 1;
  if (ratio <= 0.5) return 2;
  if (ratio <= 0.75) return 3;
  return 4;
}

function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
  return `${count} ${count > 1 ? pluralForm : singular}`;
}

function readHideEmpty(): boolean {
  try {
    return window.localStorage.getItem(HIDE_EMPTY_KEY) !== "0";
  } catch {
    return true;
  }
}

interface ProjectsWorkloadProps {
  /** `null` = tous les projets ; sinon, ne compter que ceux-là (filtres de la feuille de route). */
  projectIds: string[] | null;
  /** Filtre « Personne » de la feuille de route. */
  personId: string;
  projects: Project[];
  onOpen: (project: Project) => void;
}

/**
 * Charge par personne (session du 2026-11-14). Deux chiffres par case :
 * les demi-journées réellement planifiées (planning projet et créneaux posés
 * sur des tâches ou incidents), et le nombre de projets en cours dont la
 * personne est membre ou chef de projet. Chacun voit sa propre charge, un
 * chef de projet celle des membres de ses projets, un admin d'organisation
 * tout le monde (règle portée par le serveur).
 */
export function ProjectsWorkload({ projectIds, personId, projects, onOpen }: ProjectsWorkloadProps) {
  const [granularity, setGranularity] = useState<WorkloadGranularity>("month");
  const [anchor, setAnchor] = useState(() => firstOfMonth(new Date()));
  const [data, setData] = useState<Workload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ userId: string; key: string } | null>(null);
  const [hideEmpty, setHideEmpty] = useState(readHideEmpty);

  const { from, to } = windowFor(anchor, granularity);
  const projectsKey = projectIds ? projectIds.join(",") : "*";

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getWorkload({
      from,
      to,
      granularity,
      // Filtre actif sans aucun projet : on demande un identifiant qui ne
      // correspond à rien, plutôt que de compter tous les projets.
      projects: projectsKey === "*" ? undefined : projectsKey ? projectsKey.split(",") : ["aucun"],
    })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Impossible de charger la charge.");
      });
    return () => {
      cancelled = true;
    };
  }, [from, to, granularity, projectsKey]);

  function changeGranularity(next: WorkloadGranularity) {
    setGranularity(next);
    setAnchor(next === "month" ? firstOfMonth(new Date()) : monday(new Date()));
    setSelected(null);
  }

  function toggleHideEmpty(value: boolean) {
    setHideEmpty(value);
    try {
      window.localStorage.setItem(HIDE_EMPTY_KEY, value ? "1" : "0");
    } catch {
      // ignore
    }
  }

  const rows = useMemo(() => {
    if (!data) return [];
    return data.people.filter((row) => {
      if (personId && row.user.id !== personId) return false;
      if (!hideEmpty) return true;
      return Object.values(row.periods).some((cell) => cell.half_days > 0 || cell.projects_count > 0);
    });
  }, [data, personId, hideEmpty]);

  const projectsById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects]);
  const selectedRow = selected && data ? data.people.find((row) => row.user.id === selected.userId) : undefined;
  const selectedPeriod = selected && data ? data.periods.find((period) => period.key === selected.key) : undefined;
  const selectedCell = selectedRow && selected ? selectedRow.periods[selected.key] : undefined;
  const todayAnchor = granularity === "month" ? firstOfMonth(new Date()) : monday(new Date());
  const atToday = anchor.getTime() === todayAnchor.getTime();

  return (
    <div className="workload">
      <div className="projects-roadmap__controls">
        <div className="gantt-zoom" role="group" aria-label="Découpage">
          {(["month", "week"] as const).map((value) => (
            <button
              key={value}
              type="button"
              className={granularity === value ? "is-active" : ""}
              aria-pressed={granularity === value}
              onClick={() => changeGranularity(value)}
            >
              {value === "month" ? "Mois" : "Semaine"}
            </button>
          ))}
        </div>
        <div className="workload__nav">
          <button
            type="button"
            className="gantt__nav"
            onClick={() => setAnchor(shift(anchor, granularity, -1))}
            aria-label="Période précédente"
          >
            <ChevronLeft size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="gantt__nav"
            onClick={() => setAnchor(shift(anchor, granularity, 1))}
            aria-label="Période suivante"
          >
            <ChevronRight size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
          {!atToday && (
            <button type="button" className="gantt__today-button" onClick={() => setAnchor(todayAnchor)}>
              Aujourd'hui
            </button>
          )}
        </div>
        <label className="workload__toggle">
          <Checkbox checked={hideEmpty} onCheckedChange={toggleHideEmpty} aria-label="Masquer les personnes sans activité" />
          <span>Masquer les personnes sans activité</span>
        </label>
        <ul className="gantt-legend" aria-label="Légende">
          <li>
            <span className="workload-legend workload-legend--l1" />
            <span className="workload-legend workload-legend--l2" />
            <span className="workload-legend workload-legend--l3" />
            <span className="workload-legend workload-legend--l4" />
            Part du temps ouvré planifiée
          </li>
        </ul>
      </div>

      {error && <p className="projects-roadmap__empty">{error}</p>}
      {!error && data === null && <p className="projects-roadmap__empty">Chargement de la charge…</p>}
      {!error && data && rows.length === 0 && (
        <p className="projects-roadmap__empty">Aucune activité sur cette période.</p>
      )}

      {!error && data && rows.length > 0 && (
        <div className="workload__scroll">
          <table className="workload__table">
            <thead>
              <tr>
                <th scope="col">Personne</th>
                {data.periods.map((period) => (
                  <th key={period.key} scope="col">
                    {periodHeading(period.key, period.start, granularity)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.user.id}>
                  <th scope="row">{personName(row.user)}</th>
                  {data.periods.map((period) => {
                    const cell = row.periods[period.key];
                    const isSelected = selected?.userId === row.user.id && selected.key === period.key;
                    return (
                      <td key={period.key}>
                        <button
                          type="button"
                          className={`workload__cell workload__cell--l${level(cell, period.capacity_half_days)}${isSelected ? " is-selected" : ""}`}
                          aria-pressed={isSelected}
                          aria-label={`${personName(row.user)}, ${periodLong(period.start, period.end, granularity)} : ${plural(cell?.half_days ?? 0, "demi-journée planifiée", "demi-journées planifiées")}, ${plural(cell?.projects_count ?? 0, "projet en cours", "projets en cours")}`}
                          onClick={() => setSelected(isSelected ? null : { userId: row.user.id, key: period.key })}
                        >
                          <strong>{cell?.half_days ?? 0}</strong>
                          <small>{plural(cell?.projects_count ?? 0, "projet")}</small>
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && <p className="projects-roadmap__footnote">Le grand chiffre compte les demi-journées planifiées, le petit les projets en cours. Une demi-journée va jusqu'à 13 h ou commence à 13 h.</p>}

      {selectedRow && selectedPeriod && selectedCell && (
        <section className="workload__detail" aria-live="polite">
          <h3>
            {personName(selectedRow.user)} · {periodLong(selectedPeriod.start, selectedPeriod.end, granularity)}
          </h3>
          <p>
            {plural(selectedCell.half_days, "demi-journée planifiée", "demi-journées planifiées")} sur{" "}
            {selectedPeriod.capacity_half_days} ouvrées, {plural(selectedCell.projects_count, "projet en cours", "projets en cours")}.
          </p>
          {selectedCell.projects.length > 0 && (
            <ul>
              {selectedCell.projects.map((line) => {
                const project = projectsById.get(line.id);
                const parts = [
                  line.afternoons ? plural(line.afternoons, "après-midi", "après-midi") : "",
                  line.mornings ? plural(line.mornings, "matinée") : "",
                ].filter(Boolean);
                return (
                  <li key={line.id}>
                    {project ? (
                      <button type="button" onClick={() => onOpen(project)}>
                        {line.name}
                      </button>
                    ) : (
                      <span>{line.name}</span>
                    )}
                    <span>{parts.length ? parts.join(", ") : "aucun temps planifié"}</span>
                    {!line.engaged && <small>hors période du projet</small>}
                  </li>
                );
              })}
            </ul>
          )}
          {selectedCell.hidden_projects > 0 && (
            <p className="workload__hidden">
              Et {plural(selectedCell.hidden_projects, "autre projet")} que vous ne voyez pas
              {selectedCell.hidden_half_days > 0
                ? ` : ${plural(selectedCell.hidden_half_days, "demi-journée", "demi-journées")}`
                : ""}
              .
            </p>
          )}
        </section>
      )}
    </div>
  );
}
