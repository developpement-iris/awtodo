import "./AreaChart.css";

export interface AreaChartPoint {
  label: string;
  value: number;
}

interface AreaChartProps {
  data: AreaChartPoint[];
  height?: number;
}

// Aire remplie faite main (SVG, pas de dépendance graphique) — même choix que
// BarChart/DonutChart : rendu maison plutôt qu'une librairie pour un seul
// graphique (voir docs/charte-graphique.md). Le dégradé de remplissage est
// une affordance de donnée standard (fondu vers transparent sous la ligne),
// pas un fond décoratif — ne contrevient pas à la règle "pas de dégradé
// décoratif" de la charte, qui vise le chrome UI, pas la dataviz.
export function AreaChart({ data, height = 140 }: AreaChartProps) {
  const width = 100;
  const chartHeight = 100;
  const values = data.map((point) => point.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;

  const points = data.map((point, index) => {
    const x = data.length > 1 ? (index / (data.length - 1)) * width : width / 2;
    const y = chartHeight - ((point.value - min) / range) * chartHeight;
    return { x, y };
  });

  const linePath = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const areaPath = `${linePath} L ${width} ${chartHeight} L 0 ${chartHeight} Z`;

  return (
    <div className="area-chart" style={{ height }}>
      <svg
        className="area-chart__svg"
        viewBox={`0 0 ${width} ${chartHeight}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Graphique d'évolution"
      >
        <defs>
          <linearGradient id="area-chart-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#area-chart-fill)" stroke="none" />
        <path
          d={linePath}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="area-chart__labels">
        {data.map((point, index) => (
          <span key={`${point.label}-${index}`} className="area-chart__label">
            {point.label}
          </span>
        ))}
      </div>
    </div>
  );
}
