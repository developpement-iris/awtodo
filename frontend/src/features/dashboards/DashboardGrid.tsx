import { useCallback, useRef } from "react";
import { GridLayout, useContainerWidth, type Layout } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { removeDashboardWidget, updateDashboardWidgetPosition } from "../../api/client";
import type { DashboardWidgetDTO } from "../../types/watodo";
import { WidgetRenderer } from "./WidgetRenderer";
import "./DashboardGrid.css";

interface DashboardGridProps {
  widgets: DashboardWidgetDTO[];
  onWidgetRemoved: (widgetId: string) => void;
}

const GRID_CONFIG = { cols: 12, rowHeight: 80, margin: [16, 16] as const };
// La lib appelle `onLayoutChange` à chaque pixel de glisser/redimensionner —
// un PATCH par appel saturerait l'API. Un seul envoi par widget déplacé,
// une fois le geste terminé plutôt qu'au milieu.
const POSITION_SAVE_DEBOUNCE_MS = 500;

export function DashboardGrid({ widgets, onWidgetRemoved }: DashboardGridProps) {
  const { width, containerRef } = useContainerWidth();
  const pendingLayoutRef = useRef<Layout | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const handleLayoutChange = useCallback((layout: Layout) => {
    pendingLayoutRef.current = layout;
    window.clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      const toSend = pendingLayoutRef.current;
      if (!toSend) return;
      for (const item of toSend) {
        updateDashboardWidgetPosition(item.i, { x: item.x, y: item.y, w: item.w, h: item.h }).catch(() => undefined);
      }
    }, POSITION_SAVE_DEBOUNCE_MS);
  }, []);

  async function handleRemove(widgetId: string) {
    await removeDashboardWidget(widgetId);
    onWidgetRemoved(widgetId);
  }

  if (widgets.length === 0) {
    return (
      <div className="dashboard-grid__empty">
        <p>Ce tableau de bord est vide — ajoutez un widget pour commencer.</p>
      </div>
    );
  }

  const layout: Layout = widgets.map((widget) => ({ i: widget.id, x: widget.x, y: widget.y, w: widget.w, h: widget.h }));

  return (
    <div className="dashboard-grid" ref={containerRef}>
      {width > 0 && (
        <GridLayout width={width} gridConfig={GRID_CONFIG} layout={layout} onLayoutChange={handleLayoutChange} autoSize>
          {widgets.map((widget) => (
            <div key={widget.id}>
              <WidgetRenderer widget={widget} onRemove={() => handleRemove(widget.id)} />
            </div>
          ))}
        </GridLayout>
      )}
    </div>
  );
}
