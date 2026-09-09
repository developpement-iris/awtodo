import type { ReactNode } from "react";
import type { ViewName } from "../types/navigation";
import { BinderTabs } from "./BinderTabs";
import { Breadcrumb, type BreadcrumbItem } from "./Breadcrumb";
import { Topbar } from "./Topbar";
import "./AppShell.css";

interface AppShellProps {
  activeView: ViewName | null;
  onNavigate: (view: ViewName, options?: { taskId?: string; incidentId?: string }) => void;
  onNavigateHome: () => void;
  /** Vide sur l'accueil (voir App.tsx > breadcrumbItemsFor) — Breadcrumb se
   * masque alors de lui-même, pas besoin de le conditionner ici aussi. */
  breadcrumbItems: BreadcrumbItem[];
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onOpenCommandPalette: () => void;
  onLoginClick: () => void;
  showAdministration: boolean;
  children: ReactNode;
}

export function AppShell({
  activeView,
  onNavigate,
  onNavigateHome,
  breadcrumbItems,
  theme,
  onToggleTheme,
  onOpenCommandPalette,
  onLoginClick,
  showAdministration,
  children,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <Topbar
        theme={theme}
        onToggleTheme={onToggleTheme}
        onOpenCommandPalette={onOpenCommandPalette}
        onLoginClick={onLoginClick}
        onNavigateHome={onNavigateHome}
        onNavigate={onNavigate}
      />
      <Breadcrumb items={breadcrumbItems} />
      <BinderTabs activeView={activeView} onNavigate={onNavigate} showAdministration={showAdministration} />
      <main className="app-shell__content">{children}</main>
    </div>
  );
}
