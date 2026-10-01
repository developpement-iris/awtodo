import { Gauge, Lock, X } from "lucide-react";
import { AreaChart } from "../../components/AreaChart";
import { BarChart } from "../../components/BarChart";
import { DonutChart } from "../../components/DonutChart";
import { StatCard } from "../../components/StatCard";
import type { DashboardWidgetDTO } from "../../types/watodo";
import { paletteColor } from "./dashboardPalette";
import "./WidgetRenderer.css";

interface WidgetRendererProps {
  widget: DashboardWidgetDTO;
  onRemove: () => void;
}

function formatScalar(value: number): string {
  if (Number.isInteger(value)) return String(value);
  // Les taux (ex. cancellation_rate) sont de petits décimaux 0-1 — affichés
  // en pourcentage, plus lisible qu'un "0.333" brut.
  if (Math.abs(value) <= 1) return `${Math.round(value * 100)} %`;
  return value.toFixed(1);
}

function WidgetBody({ widget }: { widget: DashboardWidgetDTO }) {
  const { data } = widget;

  if ("restricted" in data && data.restricted) {
    return (
      <p className="widget-renderer__restricted">
        <Lock size={14} strokeWidth={1.75} aria-hidden="true" />
        Vous n'avez plus les droits pour voir ce widget.
      </p>
    );
  }

  switch (data.type) {
    case "scalar":
      return <StatCard icon={Gauge} tone="neutral" value={formatScalar(data.value)} label={widget.title} />;

    case "series": {
      if (widget.render_hint === "donut") {
        const total = data.data.reduce((sum, point) => sum + point.value, 0);
        return (
          <div className="widget-renderer__donut">
            <DonutChart
              slices={data.data.map((point, index) => ({
                label: point.label,
                value: point.value,
                color: paletteColor(index),
              }))}
              centerLabel={widget.title}
              centerValue={String(total)}
            />
            <ul className="widget-renderer__legend">
              {data.data.map((point, index) => (
                <li key={point.label}>
                  <span className="widget-renderer__legend-dot" style={{ background: paletteColor(index) }} />
                  {point.label} — {point.value}
                </li>
              ))}
            </ul>
          </div>
        );
      }
      if (widget.render_hint === "area") {
        return <AreaChart data={data.data} />;
      }
      return <BarChart data={data.data} />;
    }

    case "table":
      if (data.rows.length === 0) {
        return <p className="widget-renderer__empty">Aucune donnée pour l'instant.</p>;
      }
      return (
        <table className="widget-renderer__table">
          <thead>
            <tr>
              {Object.keys(data.rows[0]).map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, index) => (
              <tr key={index}>
                {Object.values(row).map((value, cellIndex) => (
                  <td key={cellIndex}>{String(value)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );

    case "feed":
      if (data.items.length === 0) {
        return <p className="widget-renderer__empty">Aucune activité récente.</p>;
      }
      return (
        <ul className="widget-renderer__feed">
          {data.items.map((item, index) => (
            <li key={index}>
              <span className="widget-renderer__feed-actor">{item.actor}</span>
              <span className="widget-renderer__feed-description">{item.description || item.verb}</span>
              <time className="widget-renderer__feed-time">{new Date(item.created_at).toLocaleString("fr-FR")}</time>
            </li>
          ))}
        </ul>
      );

    default:
      return null;
  }
}

export function WidgetRenderer({ widget, onRemove }: WidgetRendererProps) {
  return (
    <div className="widget-renderer">
      <div className="widget-renderer__header">
        <h4 className="widget-renderer__title">{widget.title}</h4>
        <button
          type="button"
          className="widget-renderer__remove"
          onClick={onRemove}
          aria-label="Retirer ce widget"
          title="Retirer ce widget"
        >
          <X size={14} strokeWidth={1.75} aria-hidden="true" />
        </button>
      </div>
      <div className="widget-renderer__body">
        <WidgetBody widget={widget} />
      </div>
    </div>
  );
}
