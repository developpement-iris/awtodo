import { TrendingUp } from "lucide-react";
import { BarChart } from "./BarChart";
import type { CompletionTrendPoint } from "../types/watodo";
import "./CompletionTrendWidget.css";

function formatWeekLabel(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
}

interface CompletionTrendWidgetProps {
  trend: CompletionTrendPoint[];
}

export function CompletionTrendWidget({ trend }: CompletionTrendWidgetProps) {
  const total = trend.reduce((sum, point) => sum + point.count, 0);

  return (
    <div className="completion-trend">
      <div className="completion-trend__header">
        <TrendingUp size={16} strokeWidth={1.75} aria-hidden="true" />
        <h3>Tâches terminées par semaine</h3>
      </div>
      {total === 0 ? (
        <p className="completion-trend__message">Aucune tâche terminée sur les dernières semaines.</p>
      ) : (
        <BarChart data={trend.map((point) => ({ label: formatWeekLabel(point.week_start), value: point.count }))} />
      )}
    </div>
  );
}
