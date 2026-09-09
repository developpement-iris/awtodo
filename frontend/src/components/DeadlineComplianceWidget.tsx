import { CalendarCheck } from "lucide-react";
import { DonutChart } from "./DonutChart";
import "./DeadlineComplianceWidget.css";

interface DeadlineComplianceWidgetProps {
  onTime: number;
  late: number;
}

export function DeadlineComplianceWidget({ onTime, late }: DeadlineComplianceWidgetProps) {
  const total = onTime + late;
  const rate = total > 0 ? Math.round((onTime / total) * 100) : null;

  return (
    <div className="deadline-compliance">
      <div className="deadline-compliance__header">
        <CalendarCheck size={16} strokeWidth={1.75} aria-hidden="true" />
        <h3>Respect des échéances</h3>
      </div>
      {total === 0 ? (
        <p className="deadline-compliance__message">Aucune tâche à échéance clôturée pour l'instant.</p>
      ) : (
        <div className="deadline-compliance__body">
          <DonutChart
            slices={[
              { label: "À temps", value: onTime, color: "var(--tone-positive-text)" },
              { label: "En retard", value: late, color: "var(--priority-critique-text)" },
            ]}
            centerLabel="à temps"
            centerValue={`${rate} %`}
            size={130}
            emphasis
          />
          <ul className="deadline-compliance__legend">
            <li className="deadline-compliance__legend-item">
              <span className="deadline-compliance__swatch deadline-compliance__swatch--on-time" />
              <span>À temps</span>
              <strong>{onTime}</strong>
            </li>
            <li className="deadline-compliance__legend-item">
              <span className="deadline-compliance__swatch deadline-compliance__swatch--late" />
              <span>En retard</span>
              <strong>{late}</strong>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
