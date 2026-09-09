import { CheckCircle2, Clock3, FolderKanban, Lock, Timer, Unlock, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { getBudgetSummary, getGlobalTaskStats } from "../../api/client";
import { CompletionTrendWidget } from "../../components/CompletionTrendWidget";
import { DeadlineComplianceWidget } from "../../components/DeadlineComplianceWidget";
import { EstimateComplianceWidget } from "../../components/EstimateComplianceWidget";
import { PriorityBreakdownWidget } from "../../components/PriorityBreakdownWidget";
import { SkeletonTable } from "../../components/Skeleton";
import { StatCard } from "../../components/StatCard";
import type { BudgetSummaryRow, GlobalTaskStats } from "../../types/watodo";
import "./GlobalStatsPage.css";

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

function formatAmount(value: string): string {
  return currencyFormatter.format(Number(value));
}

function formatHours(value: string): string {
  const hours = Number(value);
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} h`;
}

export function GlobalStatsPage() {
  const [stats, setStats] = useState<GlobalTaskStats | null>(null);
  const [budgets, setBudgets] = useState<BudgetSummaryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getGlobalTaskStats()
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "Le chargement des statistiques a échoué."));
    getBudgetSummary()
      .then(setBudgets)
      .catch(() => setBudgets([]));
  }, []);

  return (
    <div className="global-stats-page">
      <h2 className="global-stats-page__section-title">Vue globale</h2>

      {error && <p className="global-stats-page__message global-stats-page__message--error">{error}</p>}

      {stats === null ? (
        <div className="global-stats-page__cards">
          <SkeletonTable columns={1} rows={5} />
        </div>
      ) : (
        <>
          <div className="global-stats-page__cards">
            <StatCard icon={FolderKanban} tone="neutral" value={stats.projects_total} label="Projets accessibles" />
            <StatCard icon={Unlock} tone="positive" value={stats.projects_active} label="Projets actifs" />
            <StatCard icon={Lock} tone="neutral" value={stats.projects_closed} label="Projets clôturés" />
            <StatCard icon={CheckCircle2} tone="positive" value={stats.tasks_done} label="Tâches réalisées" />
            <StatCard icon={Clock3} tone="neutral" value={stats.tasks_in_progress} label="Tâches en cours" />
            <StatCard icon={Clock3} tone="neutral" value={formatHours(stats.hours_total)} label="Heures passées" />
            <StatCard
              icon={Timer}
              tone="neutral"
              value={formatHours(stats.estimated_hours_total)}
              label="Temps estimé total"
            />
            <StatCard
              icon={Timer}
              tone="neutral"
              value={stats.avg_lead_time_days != null ? `${stats.avg_lead_time_days} j` : "—"}
              label="Délai moyen de traitement"
            />
            <StatCard icon={Users} tone="neutral" value={stats.contributors_count} label="Personnes sollicitées" />
          </div>

          <div className="global-stats-page__widgets">
            <CompletionTrendWidget trend={stats.completion_trend} />
            <DeadlineComplianceWidget onTime={stats.tasks_on_time} late={stats.tasks_late} />
            <EstimateComplianceWidget onTarget={stats.tasks_under_estimate} overEstimate={stats.tasks_over_estimate} />
            <PriorityBreakdownWidget breakdown={stats.priority_breakdown} />
          </div>
        </>
      )}

      <h2 className="global-stats-page__section-title">Budgets des projets que vous dirigez</h2>

      {budgets === null ? (
        <SkeletonTable columns={4} rows={2} />
      ) : budgets.length === 0 ? (
        <p className="global-stats-page__message">
          Vous n'êtes chef de projet sur aucun projet — aucun budget à afficher ici.
        </p>
      ) : (
        <div className="global-stats-page__table-wrapper">
          <table className="global-stats-page__table">
            <thead>
              <tr>
                <th>Projet</th>
                <th>OPEX</th>
                <th>CAPEX</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {budgets.map((row) => (
                <tr key={row.project_id}>
                  <td>{row.project_name}</td>
                  <td className="global-stats-page__num">{formatAmount(row.opex_total)}</td>
                  <td className="global-stats-page__num">{formatAmount(row.capex_total)}</td>
                  <td className="global-stats-page__num global-stats-page__num--total">
                    {formatAmount(String(Number(row.opex_total) + Number(row.capex_total)))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
