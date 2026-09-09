import { LineChart } from "lucide-react";
import { AreaChart } from "./AreaChart";
import type { BudgetLine } from "../types/watodo";
import "./BudgetTrendWidget.css";

interface BudgetTrendWidgetProps {
  lines: BudgetLine[];
}

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

function formatDateLabel(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
}

// Évolution du montant total engagé (OPEX + CAPEX confondus) au fil des
// lignes ajoutées, dans l'ordre chronologique réel (`created_at`) — pas de
// découpage 7j/14j/30j comme le modèle de référence (Watermelon UI
// `widget-5`) : une ligne budgétaire est un événement ponctuel et
// irrégulier, pas une série quotidienne, un tel découpage n'aurait pas de
// sens ici.
export function BudgetTrendWidget({ lines }: BudgetTrendWidgetProps) {
  const sorted = [...lines].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  let cumulative = 0;
  const points = sorted.map((line) => {
    cumulative += Number(line.amount);
    return { label: formatDateLabel(line.created_at), value: cumulative };
  });
  const total = cumulative;

  return (
    <div className="budget-trend">
      <div className="budget-trend__header">
        <LineChart size={16} strokeWidth={1.75} aria-hidden="true" />
        <h3>Évolution du budget engagé</h3>
      </div>
      {lines.length === 0 ? (
        <p className="budget-trend__message">Aucune ligne budgétaire pour l'instant.</p>
      ) : (
        <>
          <div className="budget-trend__total">{currencyFormatter.format(total)}</div>
          <AreaChart data={points} />
          <p className="budget-trend__stat">
            {lines.length} ligne{lines.length > 1 ? "s" : ""} budgétaire{lines.length > 1 ? "s" : ""} au total
          </p>
        </>
      )}
    </div>
  );
}
