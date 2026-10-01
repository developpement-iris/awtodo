import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createGlobalDashboardWidget, getDashboardCatalog, getGlobalDashboard } from "../../api/client";
import { AddWidgetPanel } from "../dashboards/AddWidgetPanel";
import { DashboardGrid } from "../dashboards/DashboardGrid";
import type { CustomWidgetConfig, DashboardCatalog, DashboardWidgetDTO } from "../../types/watodo";
import "./GlobalStatsPage.css";

export function GlobalStatsPage() {
  const [widgets, setWidgets] = useState<DashboardWidgetDTO[] | null>(null);
  const [catalog, setCatalog] = useState<DashboardCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  useEffect(() => {
    getGlobalDashboard()
      .then((bundle) => setWidgets(bundle.widgets))
      .catch((err) => setError(err instanceof Error ? err.message : "Le chargement du tableau de bord a échoué."));
    getDashboardCatalog("global").then(setCatalog).catch(() => undefined);
  }, []);

  function handleWidgetRemoved(widgetId: string) {
    setWidgets((current) => current?.filter((widget) => widget.id !== widgetId) ?? current);
  }

  async function handleCreateDefault(metricKey: string) {
    const widget = await createGlobalDashboardWidget({ widget_type: "defaut", metric_key: metricKey });
    setWidgets((current) => [...(current ?? []), widget]);
    return widget;
  }

  async function handleCreateCustom(config: CustomWidgetConfig, title: string) {
    const widget = await createGlobalDashboardWidget({ widget_type: "personnalise", config, title });
    setWidgets((current) => [...(current ?? []), widget]);
    return widget;
  }

  return (
    <div className="global-stats-page">
      <div className="global-stats-page__toolbar">
        <h2 className="global-stats-page__section-title">Tableau de bord</h2>
        <button type="button" className="global-stats-page__toggle" onClick={() => setPanelOpen((value) => !value)}>
          {panelOpen ? (
            <>
              <X size={14} strokeWidth={1.75} aria-hidden="true" />
              Fermer
            </>
          ) : (
            <>
              <Plus size={14} strokeWidth={1.75} aria-hidden="true" />
              Ajouter un widget
            </>
          )}
        </button>
      </div>

      {error && <p className="global-stats-page__message global-stats-page__message--error">{error}</p>}

      {panelOpen && catalog && (
        <AddWidgetPanel catalog={catalog} onCreateDefault={handleCreateDefault} onCreateCustom={handleCreateCustom} />
      )}

      {widgets === null ? (
        <p className="global-stats-page__message">Chargement…</p>
      ) : (
        <DashboardGrid widgets={widgets} onWidgetRemoved={handleWidgetRemoved} />
      )}
    </div>
  );
}
