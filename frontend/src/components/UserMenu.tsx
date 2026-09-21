import { ChevronDown, LogIn, LogOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useCurrentUser } from "../context/CurrentUserContext";
import "./UserMenu.css";

function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function displayName(user: { username: string; first_name: string; last_name: string }): string {
  const fullName = `${user.first_name} ${user.last_name}`.trim();
  return fullName || user.username;
}

interface UserMenuProps {
  onLoginClick: () => void;
}

export function UserMenu({ onLoginClick }: UserMenuProps) {
  const { currentUser, isAuthenticated, logout } = useCurrentUser();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const label = currentUser ? displayName(currentUser) : "Aucun utilisateur";

  return (
    <div className="user-menu" ref={menuRef}>
      <button type="button" className="user-menu__trigger" onClick={() => setOpen((value) => !value)}>
        <span className="user-menu__avatar">{currentUser ? initials(label) : "?"}</span>
        <span className="user-menu__name">{label}</span>
        <ChevronDown size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>

      {open && (
        <div className="user-menu__panel">
          {isAuthenticated ? (
            <button
              type="button"
              className="user-menu__logout"
              onClick={() => {
                logout();
                setOpen(false);
              }}
            >
              <LogOut size={14} strokeWidth={1.75} aria-hidden="true" />
              Déconnexion
            </button>
          ) : (
            <button
              type="button"
              className="user-menu__logout"
              onClick={() => {
                onLoginClick();
                setOpen(false);
              }}
            >
              <LogIn size={14} strokeWidth={1.75} aria-hidden="true" />
              Se connecter
            </button>
          )}
        </div>
      )}
    </div>
  );
}
