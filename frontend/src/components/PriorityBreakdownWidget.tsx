import { SlidersHorizontal } from "lucide-react";
import "./PriorityBreakdownWidget.css";

const PRIORITY_ORDER = ["critique", "haute", "moyenne", "basse"] as const;

const PRIORITY_LABELS: Record<string, string> = {
  basse: "Basse",
  moyenne: "Moyenne",
  haute: "Haute",
  critique: "Critique",
};

interface PriorityBreakdownWidgetProps {
  breakdown: Record<string, number>;
}

export function PriorityBreakdownWidget({ breakdown }: PriorityBreakdownWidgetProps) {
  const total = PRIORITY_ORDER.reduce((sum, key) => sum + (breakdown[key] ?? 0), 0);

  return (
    <div className="priority-breakdown">
      <div className="priority-breakdown__header">
        <SlidersHorizontal size={16} strokeWidth={1.75} aria-hidden="true" />
        <h3>Répartition par priorité</h3>
      </div>
      {total === 0 ? (
        <p className="priority-breakdown__message">Aucune tâche pour l'instant.</p>
      ) : (
        <ul className="priority-breakdown__list">
          {PRIORITY_ORDER.map((key) => {
            const count = breakdown[key] ?? 0;
            const percent = total > 0 ? Math.round((count / total) * 100) : 0;
            return (
              <li key={key} className="priority-breakdown__row">
                <span className="priority-breakdown__label">{PRIORITY_LABELS[key]}</span>
                <span className="priority-breakdown__bar-track">
                  <span
                    className={`priority-breakdown__bar-fill priority-breakdown__bar-fill--${key}`}
                    style={{ transform: `scaleX(${percent / 100})` }}
                  />
                </span>
                <span className="priority-breakdown__count">{count}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
