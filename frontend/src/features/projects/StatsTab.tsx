import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  createProjectDashboardWidget,
  getDashboardCatalog,
  getProjectDashboard,
} from "../../api/client";
import { AddWidgetPanel } from "../dashboards/AddWidgetPanel";
import { DashboardGrid } from "../dashboards/DashboardGrid";
import type { CustomWidgetConfig, DashboardCatalog, DashboardWidgetDTO, Project } from "../../types/watodo";
import "./StatsTab.css";

interface StatsTabProps {
  project: Project;
}

export function StatsTab({ project }: StatsTabProps) {
  const [widgets, setWidgets] = useState<DashboardWidgetDTO[] | null>(null);
  const [catalog, setCatalog] = useState<DashboardCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getProjectDashboard(project.id)
      .then((bundle) => {
        if (!cancelled) setWidgets(bundle.widgets);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Le chargement du tableau de bord a échoué.");
      });
    getDashboardCatalog("projet", project.id)
      .then((data) => {
        if (!cancelled) setCatalog(data);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [project.id]);

  function handleWidgetRemoved(widgetId: string) {
    setWidgets((current) => current?.filter((widget) => widget.id !== widgetId) ?? current);
  }

  async function handleCreateDefault(metricKey: string) {
    const widget = await createProjectDashboardWidget(project.id, { widget_type: "defaut", metric_key: metricKey });
    setWidgets((current) => [...(current ?? []), widget]);
    return widget;
  }

  async function handleCreateCustom(config: CustomWidgetConfig, title: string) {
    const widget = await createProjectDashboardWidget(project.id, { widget_type: "personnalise", config, title });
    setWidgets((current) => [...(current ?? []), widget]);
    return widget;
  }

  return (
    <div className="stats-tab">
      <div className="stats-tab__toolbar">
        <h2 className="stats-tab__title">Tableau de bord</h2>
        <button type="button" className="stats-tab__toggle" onClick={() => setPanelOpen((value) => !value)}>
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

      {error && <p className="stats-tab__message stats-tab__message--error">{error}</p>}

      {panelOpen && catalog && (
        <AddWidgetPanel catalog={catalog} onCreateDefault={handleCreateDefault} onCreateCustom={handleCreateCustom} />
      )}

      {widgets === null ? (
        <p className="stats-tab__message">Chargement…</p>
      ) : (
        <DashboardGrid widgets={widgets} onWidgetRemoved={handleWidgetRemoved} />
      )}
    </div>
  );
}
