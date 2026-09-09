import { ArrowDown, ArrowUp, ArrowUpDown, CheckCircle2, Clock3, ListTodo, Timer, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { getProjectStats, getProjectTaskInsights } from "../../api/client";
import { CompletionTrendWidget } from "../../components/CompletionTrendWidget";
import { DeadlineComplianceWidget } from "../../components/DeadlineComplianceWidget";
import { EstimateComplianceWidget } from "../../components/EstimateComplianceWidget";
import { PriorityBreakdownWidget } from "../../components/PriorityBreakdownWidget";
import { SkeletonTable } from "../../components/Skeleton";
import { StatCard } from "../../components/StatCard";
import type { Project, ProjectUserStats, TaskInsights } from "../../types/watodo";
import "./StatsTab.css";

interface StatsTabProps {
  project: Project;
}

function displayName(user: { username: string; first_name: string; last_name: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function formatHours(value: string | number): string {
  const hours = Number(value);
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} h`;
}

type SortKey = "tasks_done" | "tasks_in_progress" | "hours_spent";

function sortRows(rows: ProjectUserStats[], key: SortKey, reversed: boolean): ProjectUserStats[] {
  const sorted = [...rows].sort((a, b) => {
    const valueA = key === "hours_spent" ? Number(a.hours_spent) : a[key];
    const valueB = key === "hours_spent" ? Number(b.hours_spent) : b[key];
    return valueB - valueA;
  });
  return reversed ? sorted.reverse() : sorted;
}

export function StatsTab({ project }: StatsTabProps) {
  const [rows, setRows] = useState<ProjectUserStats[] | null>(null);
  const [insights, setInsights] = useState<TaskInsights | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("tasks_done");
  const [sortReversed, setSortReversed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getProjectStats(project.id)
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Le chargement des statistiques a échoué.");
      });
    getProjectTaskInsights(project.id)
      .then((data) => {
        if (!cancelled) setInsights(data);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [project.id]);

  function handleSortClick(key: SortKey) {
    if (sortKey === key) {
      setSortReversed((value) => !value);
    } else {
      setSortKey(key);
      setSortReversed(false);
    }
  }

  function sortIcon(key: SortKey) {
    if (sortKey !== key) return <ArrowUpDown size={12} strokeWidth={1.75} aria-hidden="true" />;
    return sortReversed ? (
      <ArrowUp size={12} strokeWidth={1.75} aria-hidden="true" />
    ) : (
      <ArrowDown size={12} strokeWidth={1.75} aria-hidden="true" />
    );
  }

  const completionRate = project.tasks_total > 0 ? Math.round((project.tasks_done / project.tasks_total) * 100) : null;
  const displayedRows = rows ? sortRows(rows, sortKey, sortReversed) : null;
  const isProjectView = rows !== null && rows.length > 1;

  return (
    <div className="stats-tab">
      <div className="stats-tab__cards">
        <StatCard icon={ListTodo} tone="neutral" value={project.tasks_total} label="Tâches totales" />
        <StatCard
          icon={CheckCircle2}
          tone="positive"
          value={project.tasks_done}
          suffix={completionRate !== null ? `(${completionRate} %)` : undefined}
          label="Tâches réalisées"
        />
        <StatCard
          icon={Clock3}
          tone="neutral"
          value={insights ? formatHours(insights.hours_total) : "—"}
          label="Heures passées"
        />
        <StatCard
          icon={Timer}
          tone="neutral"
          value={insights ? formatHours(insights.estimated_hours_total) : "—"}
          label="Temps estimé total"
        />
        <StatCard
          icon={Timer}
          tone="neutral"
          value={insights?.avg_lead_time_days != null ? `${insights.avg_lead_time_days} j` : "—"}
          label="Délai moyen de traitement"
        />
        <StatCard
          icon={Users}
          tone="neutral"
          value={insights ? insights.contributors_count : "—"}
          label="Personnes sollicitées"
        />
      </div>

      {error && <p className="stats-tab__message stats-tab__message--error">{error}</p>}

      {insights && (
        <div className="stats-tab__widgets">
          <CompletionTrendWidget trend={insights.completion_trend} />
          <DeadlineComplianceWidget onTime={insights.tasks_on_time} late={insights.tasks_late} />
          <EstimateComplianceWidget onTarget={insights.tasks_under_estimate} overEstimate={insights.tasks_over_estimate} />
          <PriorityBreakdownWidget breakdown={insights.priority_breakdown} />
        </div>
      )}

      <h3 className="stats-tab__section-title">
        {isProjectView ? "Statistiques par membre" : "Mes statistiques sur ce projet"}
      </h3>

      {displayedRows === null ? (
        <SkeletonTable columns={4} rows={3} />
      ) : displayedRows.length === 0 ? (
        <p className="stats-tab__message">Aucune donnée pour l'instant.</p>
      ) : (
        <div className="stats-tab__table-wrapper">
          <table className="stats-tab__table">
            <thead>
              <tr>
                <th>Membre</th>
                <th>
                  <button type="button" className="stats-tab__sort" onClick={() => handleSortClick("tasks_done")}>
                    Réalisées {sortIcon("tasks_done")}
                  </button>
                </th>
                <th>
                  <button type="button" className="stats-tab__sort" onClick={() => handleSortClick("tasks_in_progress")}>
                    En cours {sortIcon("tasks_in_progress")}
                  </button>
                </th>
                <th>
                  <button type="button" className="stats-tab__sort" onClick={() => handleSortClick("hours_spent")}>
                    Heures passées {sortIcon("hours_spent")}
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {displayedRows.map((row) => (
                <tr key={row.user.id}>
                  <td>
                    <div className="stats-tab__user">
                      <span className="stats-tab__avatar">{initials(displayName(row.user))}</span>
                      {displayName(row.user)}
                    </div>
                  </td>
                  <td className="stats-tab__num">{row.tasks_done}</td>
                  <td className="stats-tab__num">{row.tasks_in_progress}</td>
                  <td className="stats-tab__num">{formatHours(row.hours_spent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
