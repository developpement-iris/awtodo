import { AlertTriangle, BarChart3, CalendarDays, FolderKanban, ListChecks, ShieldCheck } from "lucide-react";
import type { ViewName } from "../types/navigation";
import "./BinderTabs.css";

interface BinderTabsProps {
  activeView: ViewName | null;
  onNavigate: (view: ViewName) => void;
  showAdministration: boolean;
}

const NAV_ITEMS: { view: ViewName; label: string; Icon: typeof FolderKanban }[] = [
  { view: "projects", label: "Projets", Icon: FolderKanban },
  { view: "tasks", label: "Tâches", Icon: ListChecks },
  { view: "incidents", label: "Incidents", Icon: AlertTriangle },
  { view: "planning", label: "Planning", Icon: CalendarDays },
  { view: "stats", label: "Statistiques", Icon: BarChart3 },
];

export function BinderTabs({ activeView, onNavigate, showAdministration }: BinderTabsProps) {
  const items = showAdministration
    ? [...NAV_ITEMS, { view: "administration" as ViewName, label: "Administration", Icon: ShieldCheck }]
    : NAV_ITEMS;

  return (
    <div className="binder-tabs" role="tablist" aria-label="Navigation principale">
      {items.map(({ view, label, Icon }) => (
        <button
          key={view}
          type="button"
          role="tab"
          aria-selected={activeView === view}
          className={`binder-tab${activeView === view ? " binder-tab--active" : ""}`}
          onClick={() => onNavigate(view)}
        >
          <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
