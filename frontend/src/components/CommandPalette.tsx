import { Command } from "cmdk";
import {
  AlertTriangle,
  BarChart3,
  CalendarDays,
  FolderKanban,
  ListChecks,
  LogOut,
  Moon,
  Plus,
  Search,
  Sun,
  User as UserIcon,
} from "lucide-react";
import { useEffect } from "react";
import { useCurrentUser } from "../context/CurrentUserContext";
import type { ViewName } from "../types/navigation";
import "./CommandPalette.css";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onNavigate: (view: ViewName) => void;
  onNavigateHome: () => void;
  onCreateProject: () => void;
  onCreateIncident: () => void;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

function displayName(user: { username: string; first_name: string; last_name: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function CommandPalette({
  open,
  onClose,
  onNavigate,
  onNavigateHome,
  onCreateProject,
  onCreateIncident,
  theme,
  onToggleTheme,
}: CommandPaletteProps) {
  const { users, currentUser, setCurrentUserId, clearCurrentUser } = useCurrentUser();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && open) onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  function run(action: () => void) {
    onClose();
    action();
  }

  return (
    <div className="command-palette__overlay" onClick={onClose}>
      <div className="command-palette__panel" onClick={(event) => event.stopPropagation()}>
        <Command label="Palette de commandes" shouldFilter>
          <div className="command-palette__input-wrapper">
            <Search size={16} strokeWidth={1.75} className="command-palette__search-icon" aria-hidden="true" />
            <Command.Input autoFocus placeholder="Rechercher une action…" className="command-palette__input" />
          </div>
          <Command.List className="command-palette__list">
            <Command.Empty className="command-palette__empty">Aucun résultat.</Command.Empty>

            <Command.Group heading="Navigation" className="command-palette__group">
              <Command.Item className="command-palette__item" onSelect={() => run(onNavigateHome)}>
                <ListChecks size={15} strokeWidth={1.75} aria-hidden="true" />
                Aller à l'accueil
              </Command.Item>
              <Command.Item className="command-palette__item" onSelect={() => run(() => onNavigate("projects"))}>
                <FolderKanban size={15} strokeWidth={1.75} aria-hidden="true" />
                Aller aux projets
              </Command.Item>
              <Command.Item className="command-palette__item" onSelect={() => run(() => onNavigate("tasks"))}>
                <ListChecks size={15} strokeWidth={1.75} aria-hidden="true" />
                Aller aux tâches
              </Command.Item>
              <Command.Item className="command-palette__item" onSelect={() => run(() => onNavigate("incidents"))}>
                <AlertTriangle size={15} strokeWidth={1.75} aria-hidden="true" />
                Aller aux incidents
              </Command.Item>
              <Command.Item className="command-palette__item" onSelect={() => run(() => onNavigate("planning"))}>
                <CalendarDays size={15} strokeWidth={1.75} aria-hidden="true" />
                Aller au planning
              </Command.Item>
              <Command.Item className="command-palette__item" onSelect={() => run(() => onNavigate("stats"))}>
                <BarChart3 size={15} strokeWidth={1.75} aria-hidden="true" />
                Aller aux statistiques
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Créer" className="command-palette__group">
              <Command.Item className="command-palette__item" onSelect={() => run(onCreateProject)}>
                <Plus size={15} strokeWidth={1.75} aria-hidden="true" />
                Nouveau projet
              </Command.Item>
              <Command.Item className="command-palette__item" onSelect={() => run(onCreateIncident)}>
                <Plus size={15} strokeWidth={1.75} aria-hidden="true" />
                Signaler un incident
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Apparence" className="command-palette__group">
              <Command.Item className="command-palette__item" onSelect={() => run(onToggleTheme)}>
                {theme === "dark" ? (
                  <Sun size={15} strokeWidth={1.75} aria-hidden="true" />
                ) : (
                  <Moon size={15} strokeWidth={1.75} aria-hidden="true" />
                )}
                Basculer en thème {theme === "dark" ? "clair" : "sombre"}
              </Command.Item>
            </Command.Group>

            <Command.Group heading="Utilisateur (mode démo)" className="command-palette__group">
              {users
                .filter((user) => user.id !== currentUser?.id)
                .map((user) => (
                  <Command.Item
                    key={user.id}
                    className="command-palette__item"
                    onSelect={() => run(() => setCurrentUserId(user.id))}
                  >
                    <UserIcon size={15} strokeWidth={1.75} aria-hidden="true" />
                    Se connecter en tant que {displayName(user)}
                  </Command.Item>
                ))}
              {currentUser && (
                <Command.Item className="command-palette__item" onSelect={() => run(clearCurrentUser)}>
                  <LogOut size={15} strokeWidth={1.75} aria-hidden="true" />
                  Déconnexion
                </Command.Item>
              )}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
