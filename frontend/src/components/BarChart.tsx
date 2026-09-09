import "./BarChart.css";

export interface BarChartDatum {
  label: string;
  value: number;
}

interface BarChartProps {
  data: BarChartDatum[];
  height?: number;
}

// Barres faites main (divs, pas de SVG/dépendance graphique) — même choix
// que DonutChart/ProgressBar/Roadmap : positionnement CSS pur, cohérent
// avec le reste du projet plutôt que d'ajouter une librairie de graphiques
// pour un seul widget.
export function BarChart({ data, height = 140 }: BarChartProps) {
  const max = Math.max(...data.map((point) => point.value), 1);

  return (
    <div className="bar-chart" style={{ height }} role="img" aria-label="Graphique en barres">
      {data.map((point, index) => {
        // Plancher de 4% pour toute valeur non nulle — sans lui, une petite
        // valeur face à un pic élevé rendrait sa barre quasi invisible.
        const percent = point.value > 0 ? Math.max((point.value / max) * 100, 4) : 0;
        return (
          <div className="bar-chart__col" key={`${point.label}-${index}`}>
            <span className="bar-chart__value">{point.value > 0 ? point.value : ""}</span>
            <div className="bar-chart__track">
              <div className="bar-chart__bar" style={{ transform: `scaleY(${percent / 100})` }} />
            </div>
            <span className="bar-chart__label">{point.label}</span>
          </div>
        );
      })}
    </div>
  );
}
