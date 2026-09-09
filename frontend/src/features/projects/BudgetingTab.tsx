import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { addBudgetLine, getBudgetLines, removeBudgetLine } from "../../api/client";
import { BudgetTrendWidget } from "../../components/BudgetTrendWidget";
import { DonutChart, type DonutSlice } from "../../components/DonutChart";
import type { BudgetCategory, BudgetLine, Project } from "../../types/watodo";
import "./BudgetingTab.css";

interface BudgetingTabProps {
  project: Project;
}

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

function formatAmount(value: number): string {
  return currencyFormatter.format(value);
}

// Rampe monochrome sur --color-accent (une seule famille de teinte, pas un
// arc-en-ciel arbitraire) — cohérent avec la règle "une couleur = un seul
// axe de sens" du CLAUDE.md : ce graphique porte un seul axe (part de
// budget par ligne), pas de collision avec la palette sémantique
// priorité/statut/type déjà figée ailleurs dans l'app.
const SLICE_COLORS = [
  "var(--color-accent)",
  "color-mix(in srgb, var(--color-accent) 78%, var(--color-surface))",
  "color-mix(in srgb, var(--color-accent) 58%, var(--color-surface))",
  "color-mix(in srgb, var(--color-accent) 40%, var(--color-surface))",
  "color-mix(in srgb, var(--color-accent) 26%, var(--color-surface))",
  "var(--tone-neutral-text)",
];

function buildSlices(lines: BudgetLine[]): DonutSlice[] {
  const sorted = [...lines].sort((a, b) => Number(b.amount) - Number(a.amount));
  const top = sorted.slice(0, 5);
  const rest = sorted.slice(5);
  const slices: DonutSlice[] = top.map((line, index) => ({
    label: line.label,
    value: Number(line.amount),
    color: SLICE_COLORS[index],
  }));
  if (rest.length > 0) {
    slices.push({
      label: `Autres (${rest.length})`,
      value: rest.reduce((sum, line) => sum + Number(line.amount), 0),
      color: SLICE_COLORS[5],
    });
  }
  return slices;
}

interface BudgetCategorySectionProps {
  projectId: string;
  category: BudgetCategory;
  title: string;
  lines: BudgetLine[];
  canManage: boolean;
  onLineAdded: (line: BudgetLine) => void;
  onLineRemoved: (lineId: string) => void;
}

function BudgetCategorySection({
  projectId,
  category,
  title,
  lines,
  canManage,
  onLineAdded,
  onLineRemoved,
}: BudgetCategorySectionProps) {
  const [label, setLabel] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [unitPrice, setUnitPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const total = lines.reduce((sum, line) => sum + Number(line.amount), 0);
  const slices = buildSlices(lines);

  async function handleAdd() {
    if (!label.trim() || !unitPrice.trim() || !quantity) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await addBudgetLine(projectId, {
        category,
        label: label.trim(),
        quantity: Number(quantity),
        unit_price: unitPrice,
      });
      onLineAdded(created);
      setLabel("");
      setQuantity("1");
      setUnitPrice("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'ajout de la ligne a échoué.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemove(lineId: string) {
    setRemovingId(lineId);
    setError(null);
    try {
      await removeBudgetLine(lineId);
      onLineRemoved(lineId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le retrait a échoué.");
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="budgeting-tab__section">
      <div className="budgeting-tab__donut-card">
        <div className="budgeting-tab__donut-card-header">
          <h3>{title}</h3>
          <span className="budgeting-tab__total">{formatAmount(total)}</span>
        </div>
        {lines.length === 0 ? (
          <p className="budgeting-tab__message">Aucune ligne pour l'instant.</p>
        ) : (
          <div className="budgeting-tab__donut-row">
            <DonutChart slices={slices} centerLabel={title} centerValue={formatAmount(total)} size={140} />
            <ul className="budgeting-tab__legend">
              {slices.map((slice) => (
                <li key={slice.label} className="budgeting-tab__legend-item">
                  <span className="budgeting-tab__legend-swatch" style={{ background: slice.color }} />
                  <span className="budgeting-tab__legend-label">{slice.label}</span>
                  <span className="budgeting-tab__legend-value">
                    {total > 0 ? Math.round((slice.value / total) * 100) : 0} %
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="budgeting-tab__table-card">
        {error && <p className="budgeting-tab__message budgeting-tab__message--error">{error}</p>}
        <table className="budgeting-tab__table">
          <thead>
            <tr>
              <th>Ligne</th>
              <th>Quantité</th>
              <th>Prix unitaire</th>
              <th>Montant</th>
              {canManage && <th></th>}
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.id}>
                <td>{line.label}</td>
                <td className="budgeting-tab__num">{line.quantity}</td>
                <td className="budgeting-tab__num">{formatAmount(Number(line.unit_price))}</td>
                <td className="budgeting-tab__num">{formatAmount(Number(line.amount))}</td>
                {canManage && (
                  <td className="budgeting-tab__actions">
                    <button
                      type="button"
                      className="budgeting-tab__remove"
                      onClick={() => handleRemove(line.id)}
                      disabled={removingId === line.id}
                      aria-label={`Retirer la ligne ${line.label}`}
                    >
                      <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {canManage && (
              <tr className="budgeting-tab__add-row">
                <td>
                  <input
                    type="text"
                    placeholder="Nouvelle ligne"
                    value={label}
                    onChange={(event) => setLabel(event.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    inputMode="numeric"
                    value={quantity}
                    onChange={(event) => setQuantity(event.target.value.replace(/[^0-9]/g, ""))}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0,00"
                    value={unitPrice}
                    onChange={(event) => setUnitPrice(event.target.value)}
                  />
                </td>
                <td className="budgeting-tab__num">
                  {quantity && unitPrice ? formatAmount(Number(quantity) * Number(unitPrice)) : "—"}
                </td>
                <td>
                  <button
                    type="button"
                    className="budgeting-tab__add"
                    onClick={handleAdd}
                    disabled={submitting || !label.trim() || !unitPrice.trim() || !quantity}
                  >
                    Ajouter
                  </button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BudgetingTab({ project }: BudgetingTabProps) {
  const [lines, setLines] = useState<BudgetLine[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canManage = project.permissions.can_manage_budget;

  useEffect(() => {
    let cancelled = false;
    getBudgetLines(project.id)
      .then((data) => {
        if (!cancelled) setLines(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Le chargement du budget a échoué.");
      });
    return () => {
      cancelled = true;
    };
  }, [project.id]);

  function handleLineAdded(line: BudgetLine) {
    setLines((current) => [...(current ?? []), line]);
  }

  function handleLineRemoved(lineId: string) {
    setLines((current) => (current ?? []).filter((line) => line.id !== lineId));
  }

  if (error) {
    return <p className="budgeting-tab__message budgeting-tab__message--error">{error}</p>;
  }

  if (lines === null) {
    return <p className="budgeting-tab__message">Chargement…</p>;
  }

  const opexLines = lines.filter((line) => line.category === "opex");
  const capexLines = lines.filter((line) => line.category === "capex");
  const opexTotal = opexLines.reduce((sum, line) => sum + Number(line.amount), 0);
  const capexTotal = capexLines.reduce((sum, line) => sum + Number(line.amount), 0);
  const splitTotal = opexTotal + capexTotal;
  const splitSlices: DonutSlice[] = [
    { label: "OPEX", value: opexTotal, color: "var(--color-accent)" },
    { label: "CAPEX", value: capexTotal, color: "color-mix(in srgb, var(--color-accent) 45%, var(--color-surface))" },
  ];

  return (
    <div className="budgeting-tab">
      {lines.length > 0 && (
        <div className="budgeting-tab__overview">
          <BudgetTrendWidget lines={lines} />

          <div className="budgeting-tab__split-card">
            <h3>Répartition OPEX / CAPEX</h3>
            {splitTotal === 0 ? (
              <p className="budgeting-tab__message">Aucun montant pour l'instant.</p>
            ) : (
              <div className="budgeting-tab__donut-row">
                <DonutChart slices={splitSlices} centerLabel="Total" centerValue={formatAmount(splitTotal)} size={140} />
                <ul className="budgeting-tab__legend">
                  {splitSlices.map((slice) => (
                    <li key={slice.label} className="budgeting-tab__legend-item">
                      <span className="budgeting-tab__legend-swatch" style={{ background: slice.color }} />
                      <span className="budgeting-tab__legend-label">{slice.label}</span>
                      <span className="budgeting-tab__legend-value">
                        {splitTotal > 0 ? Math.round((slice.value / splitTotal) * 100) : 0} %
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      <BudgetCategorySection
        projectId={project.id}
        category="opex"
        title="OPEX"
        lines={opexLines}
        canManage={canManage}
        onLineAdded={handleLineAdded}
        onLineRemoved={handleLineRemoved}
      />
      <BudgetCategorySection
        projectId={project.id}
        category="capex"
        title="CAPEX"
        lines={capexLines}
        canManage={canManage}
        onLineAdded={handleLineAdded}
        onLineRemoved={handleLineRemoved}
      />
    </div>
  );
}
