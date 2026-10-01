import { Lock, Plus } from "lucide-react";
import { useState } from "react";
import { Combobox } from "../../components/Combobox";
import type {
  CustomWidgetConfig,
  DashboardAggregation,
  DashboardCatalog,
  DashboardWidgetDTO,
} from "../../types/watodo";
import "./AddWidgetPanel.css";

interface AddWidgetPanelProps {
  catalog: DashboardCatalog;
  onCreateDefault: (metricKey: string) => Promise<DashboardWidgetDTO | void>;
  onCreateCustom: (config: CustomWidgetConfig, title: string) => Promise<DashboardWidgetDTO | void>;
}

const GROUP_BY_LABELS: Record<string, string> = { none: "Aucun (valeur unique)" };

function defaultTitleFor(config: CustomWidgetConfig, catalog: DashboardCatalog): string {
  const source = catalog.custom_sources[config.source];
  const aggLabel = catalog.aggregations[config.aggregation];
  const fieldLabel = config.field ? source?.aggregatable_fields[config.field] ?? config.field : "";
  const groupLabel = config.group_by === "none" ? "" : ` par ${(source?.group_by[config.group_by] ?? config.group_by).toLowerCase()}`;
  return `${aggLabel}${fieldLabel ? ` — ${fieldLabel}` : ""}${groupLabel} (${source?.label ?? config.source})`;
}

export function AddWidgetPanel({ catalog, onCreateDefault, onCreateCustom }: AddWidgetPanelProps) {
  const [mode, setMode] = useState<"defaut" | "personnalise">("defaut");
  const [source, setSource] = useState("");
  const [aggregation, setAggregation] = useState<DashboardAggregation | "">("");
  const [field, setField] = useState("");
  const [groupBy, setGroupBy] = useState("none");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const defaultEntries = Object.entries(catalog.default_metrics);
  const sourceOptions = Object.entries(catalog.custom_sources).map(([key, value]) => ({ value: key, label: value.label }));
  const sourceDef = source ? catalog.custom_sources[source] : null;
  const fieldOptions = sourceDef
    ? Object.entries(sourceDef.aggregatable_fields).map(([key, label]) => ({ value: key, label }))
    : [];
  const groupByOptions = sourceDef
    ? Object.entries(sourceDef.group_by).map(([key, label]) => ({ value: key, label: GROUP_BY_LABELS[key] ?? label }))
    : [];
  const aggregationOptions = Object.entries(catalog.aggregations).map(([key, label]) => ({ value: key, label }));

  const needsField = aggregation !== "" && aggregation !== "count";
  const canSubmitCustom = source !== "" && aggregation !== "" && (!needsField || field !== "") && title.trim() !== "";

  async function handleAddDefault(metricKey: string) {
    setBusy(true);
    setError(null);
    try {
      await onCreateDefault(metricKey);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'ajout du widget.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitCustom() {
    if (!canSubmitCustom) return;
    const config: CustomWidgetConfig = {
      source,
      aggregation,
      field: needsField ? field : null,
      group_by: groupBy,
    };
    setBusy(true);
    setError(null);
    try {
      await onCreateCustom(config, title.trim());
      setSource("");
      setAggregation("");
      setField("");
      setGroupBy("none");
      setTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de la création du widget.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="add-widget-panel">
      <div className="add-widget-panel__tabs">
        <button
          type="button"
          className={`add-widget-panel__tab${mode === "defaut" ? " add-widget-panel__tab--active" : ""}`}
          onClick={() => setMode("defaut")}
        >
          Widgets disponibles
        </button>
        <button
          type="button"
          className={`add-widget-panel__tab${mode === "personnalise" ? " add-widget-panel__tab--active" : ""}`}
          onClick={() => setMode("personnalise")}
        >
          Créer un widget personnalisé
        </button>
      </div>

      {error && <p className="add-widget-panel__error">{error}</p>}

      {mode === "defaut" ? (
        <ul className="add-widget-panel__list">
          {defaultEntries.map(([key, metric]) => (
            <li key={key}>
              <button type="button" className="add-widget-panel__item" disabled={busy} onClick={() => handleAddDefault(key)}>
                <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
                <span>{metric.label}</span>
                {metric.visibility === "groupe" && (
                  <span title="Widget « groupe »">
                    <Lock size={12} strokeWidth={1.75} aria-hidden="true" />
                  </span>
                )}
              </button>
            </li>
          ))}
          {defaultEntries.length === 0 && <p className="add-widget-panel__empty">Aucun widget disponible sur cette portée.</p>}
        </ul>
      ) : (
        <div className="add-widget-panel__builder">
          <label className="add-widget-panel__field">
            <span>Source</span>
            <Combobox options={sourceOptions} value={source} onChange={(value) => { setSource(value); setField(""); setGroupBy("none"); }} placeholder="Choisir une source…" />
          </label>
          <label className="add-widget-panel__field">
            <span>Agrégation</span>
            <Combobox
              options={aggregationOptions}
              value={aggregation}
              onChange={(value) => setAggregation(value as DashboardAggregation)}
              placeholder="Choisir une agrégation…"
              disabled={!source}
            />
          </label>
          {needsField && (
            <label className="add-widget-panel__field">
              <span>Champ</span>
              <Combobox options={fieldOptions} value={field} onChange={setField} placeholder="Choisir un champ…" disabled={!source} />
            </label>
          )}
          <label className="add-widget-panel__field">
            <span>Regroupement</span>
            <Combobox options={groupByOptions} value={groupBy} onChange={setGroupBy} disabled={!source} clearable={false} />
          </label>
          <label className="add-widget-panel__field">
            <span>Titre du widget</span>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={
                source && aggregation && (!needsField || field)
                  ? defaultTitleFor({ source, aggregation, field: needsField ? field : null, group_by: groupBy }, catalog)
                  : "Ex. Temps moyen par utilisateur"
              }
            />
          </label>
          <button type="button" className="add-widget-panel__submit" disabled={!canSubmitCustom || busy} onClick={handleSubmitCustom}>
            <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
            Ajouter ce widget
          </button>
        </div>
      )}
    </div>
  );
}
