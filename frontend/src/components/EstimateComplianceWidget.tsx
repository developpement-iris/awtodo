import { Timer } from "lucide-react";
import { DonutChart } from "./DonutChart";
import "./EstimateComplianceWidget.css";

interface EstimateComplianceWidgetProps {
  onTarget: number;
  overEstimate: number;
}

export function EstimateComplianceWidget({ onTarget, overEstimate }: EstimateComplianceWidgetProps) {
  const total = onTarget + overEstimate;
  const rate = total > 0 ? Math.round((onTarget / total) * 100) : null;

  return (
    <div className="estimate-compliance">
      <div className="estimate-compliance__header">
        <Timer size={16} strokeWidth={1.75} aria-hidden="true" />
        <h3>Respect des estimations</h3>
      </div>
      {total === 0 ? (
        <p className="estimate-compliance__message">Aucune tâche estimée et clôturée pour l'instant.</p>
      ) : (
        <div className="estimate-compliance__body">
          <DonutChart
            slices={[
              { label: "Dans les temps", value: onTarget, color: "var(--tone-positive-text)" },
              { label: "Dépassement", value: overEstimate, color: "var(--priority-critique-text)" },
            ]}
            centerLabel="dans les temps"
            centerValue={`${rate} %`}
            size={130}
            emphasis
          />
          <ul className="estimate-compliance__legend">
            <li className="estimate-compliance__legend-item">
              <span className="estimate-compliance__swatch estimate-compliance__swatch--on-target" />
              <span>Dans les temps</span>
              <strong>{onTarget}</strong>
            </li>
            <li className="estimate-compliance__legend-item">
              <span className="estimate-compliance__swatch estimate-compliance__swatch--over" />
              <span>Dépassement</span>
              <strong>{overEstimate}</strong>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
