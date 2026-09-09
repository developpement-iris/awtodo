import { Search, Settings } from "lucide-react";
import awtodoLogo from "../assets/awtodo-logo.png";
import { NotificationsDropdown } from "../components/NotificationsDropdown";
import { ThemeToggle } from "../components/ThemeToggle";
import { UserMenu } from "../components/UserMenu";
import { useToast } from "../context/ToastContext";
import type { ViewName } from "../types/navigation";
import "./Topbar.css";

const isMac = typeof navigator !== "undefined" && /Mac/.test(navigator.platform);

interface TopbarProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onOpenCommandPalette: () => void;
  onLoginClick: () => void;
  onNavigateHome: () => void;
  onNavigate: (view: ViewName, options?: { taskId?: string; incidentId?: string }) => void;
}

export function Topbar({
  theme,
  onToggleTheme,
  onOpenCommandPalette,
  onLoginClick,
  onNavigateHome,
  onNavigate,
}: TopbarProps) {
  const { showToast } = useToast();

  // Notifications/Paramètres : hors périmètre v1 (voir CLAUDE.md), pas de
  // fonctionnalité réelle derrière — un placeholder inerte serait trompeur,
  // donc un accusé de réception explicite plutôt qu'un clic sans effet.
  function handlePlaceholderAction() {
    showToast("Pas encore disponible.");
  }

  return (
    <header className="topbar">
      <button
        type="button"
        className="topbar__brand"
        onClick={onNavigateHome}
        aria-label="Awtodo — retour à l'accueil"
      >
        <img src={awtodoLogo} alt="" className="topbar__brand-logo" />
      </button>

      <div className="topbar__search-zone">
        <button type="button" className="topbar__search" onClick={onOpenCommandPalette}>
          <Search size={15} strokeWidth={1.75} aria-hidden="true" />
          <span className="topbar__search-placeholder">Rechercher un projet, une tâche, un incident…</span>
          <kbd className="topbar__search-kbd">{isMac ? "⌘K" : "Ctrl K"}</kbd>
        </button>
      </div>

      <div className="topbar__actions">
        <NotificationsDropdown
          onNotificationClick={(notification) => {
            if (notification.task) {
              onNavigate("tasks", { taskId: notification.task });
            } else if (notification.incident) {
              onNavigate("incidents", { incidentId: notification.incident });
            } else if (notification.event) {
              onNavigate("planning");
            }
          }}
        />
        <button
          type="button"
          className="topbar__icon-btn"
          onClick={handlePlaceholderAction}
          aria-label="Paramètres"
          title="Paramètres"
        >
          <Settings size={17} strokeWidth={1.75} aria-hidden="true" />
        </button>
        <UserMenu onLoginClick={onLoginClick} />
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  );
}
