import "./DonutChart.css";

export interface DonutSlice {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  slices: DonutSlice[];
  centerLabel: string;
  centerValue: string;
  size?: number;
  /** Chiffre central agrandi — pour les donuts "hero" (ex. taux de respect
   * des échéances), pas le rendu par défaut (légende budgétisation). */
  emphasis?: boolean;
}

// Donut fait main (SVG, pas de dépendance graphique) — voir
// docs/charte-graphique.md : anneau avec espacement entre parts et
// extrémités arrondies, libellé au centre, légende séparée. Inspiré du vrai
// composant PieChart/PieCenter de Bklit UI (consulté via WebFetch : props
// `padAngle`/`cornerRadius`/`innerRadius`, `PieCenter` pour le centre,
// composant `Legend` séparé) — reproduit à la main plutôt que d'ajouter une
// dépendance de graphique pour un seul donut, cohérent avec le reste du
// projet (Roadmap, ProgressBar). La légende n'est pas décorative : un
// camembert échoue au WCAG pour les daltoniens (couleur seule) — la légende
// texte + pourcentage sert de solution de repli obligatoire.
export function DonutChart({ slices, centerLabel, centerValue, size = 160, emphasis = false }: DonutChartProps) {
  const strokeWidth = size * 0.16;
  const radius = size / 2 - strokeWidth / 2;
  const circumference = 2 * Math.PI * radius;
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);
  const gapFraction = slices.length > 1 ? 0.014 : 0;

  let cumulative = 0;

  return (
    <div className="donut-chart">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${centerLabel} : ${centerValue}`}>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--color-border)"
            strokeWidth={strokeWidth}
            opacity={total > 0 ? 0.35 : 1}
          />
          {total > 0 &&
            slices.map((slice, index) => {
              const fraction = slice.value / total;
              const length = Math.max(fraction * circumference - circumference * gapFraction, 0);
              const offset = -cumulative * circumference;
              cumulative += fraction;
              return (
                <circle
                  key={index}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={slice.color}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                  strokeDasharray={`${length} ${circumference - length}`}
                  strokeDashoffset={offset}
                />
              );
            })}
        </g>
      </svg>
      <div className="donut-chart__center" style={{ width: size, height: size }}>
        <span className={`donut-chart__center-value${emphasis ? " donut-chart__center-value--emphasis" : ""}`}>
          {centerValue}
        </span>
        <span className="donut-chart__center-label">{centerLabel}</span>
      </div>
    </div>
  );
}
