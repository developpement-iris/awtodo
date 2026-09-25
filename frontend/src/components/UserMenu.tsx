import { ChevronDown, KeyRound, LogIn, LogOut, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { changePassword, updateAppearancePreferences, updateNotificationPreferences } from "../api/client";
import { useCurrentUser } from "../context/CurrentUserContext";
import { Checkbox } from "./Checkbox";
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

// Carte de compte dépliée depuis le nom/prénom (session du 2026-09-25,
// inspirée d'une "ProfileCard" fournie en référence) — remplace à la fois
// l'ancien menu (déconnexion seule) et le tiroir plein écran `SettingsDrawer`
// (supprimé) : un seul point d'entrée, sous l'identité de la personne
// connectée, plutôt qu'un bouton engrenage séparé dans la topbar.
export function UserMenu({ onLoginClick }: UserMenuProps) {
  const { currentUser, isAuthenticated, logout, refreshCurrentUser } = useCurrentUser();
  const [open, setOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [prefSubmitting, setPrefSubmitting] = useState(false);
  const [appearanceSubmitting, setAppearanceSubmitting] = useState(false);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!open) {
      setPasswordOpen(false);
      setPasswordError(null);
    }
  }, [open]);

  const label = currentUser ? displayName(currentUser) : "Aucun utilisateur";

  async function handleChangePassword(event: React.FormEvent) {
    event.preventDefault();
    setPasswordError(null);
    if (newPassword !== confirmPassword) {
      setPasswordError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setPasswordSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordOpen(false);
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Le changement a échoué.");
    } finally {
      setPasswordSubmitting(false);
    }
  }

  async function handleToggleEmailNotifications(checked: boolean) {
    setPrefSubmitting(true);
    try {
      await updateNotificationPreferences(checked);
      await refreshCurrentUser();
    } finally {
      setPrefSubmitting(false);
    }
  }

  async function handleChangeAccentColor(color: string) {
    setAppearanceSubmitting(true);
    try {
      await updateAppearancePreferences(color);
      await refreshCurrentUser();
    } finally {
      setAppearanceSubmitting(false);
    }
  }

  return (
    <div className="user-menu" ref={menuRef}>
      <button type="button" className="user-menu__trigger" onClick={() => setOpen((value) => !value)}>
        <span className="user-menu__avatar">{currentUser ? initials(label) : "?"}</span>
        <span className="user-menu__name">{label}</span>
        <ChevronDown size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>

      {open && !isAuthenticated && (
        <div className="user-menu__panel">
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
        </div>
      )}

      {open && isAuthenticated && currentUser && (
        <div className="account-card">
          <div className="account-card__profile">
            <div className="account-card__header">
              <span className="account-card__avatar">{initials(label)}</span>
              <div className="account-card__identity">
                <span className="account-card__name">{label}</span>
                <span className="account-card__handle">@{currentUser.username}</span>
              </div>
            </div>

            <div className="account-card__tags">
              <span className="account-card__tag">{currentUser.organisation_role_display}</span>
              {currentUser.is_platform_admin && (
                <span className="account-card__tag account-card__tag--accent">
                  <ShieldCheck size={11} strokeWidth={2} aria-hidden="true" />
                  Admin plateforme
                </span>
              )}
            </div>
          </div>

          <div className="account-card__section">
            <span className="account-card__section-title">Apparence</span>
            <div className="account-card__row">
              <label className="account-card__color-label">
                <input
                  type="color"
                  value={currentUser.accent_color || "#753030"}
                  onChange={(event) => void handleChangeAccentColor(event.target.value)}
                  disabled={appearanceSubmitting}
                  aria-label="Couleur d'accent de l'interface"
                  className="account-card__color-input"
                />
              </label>
              <span className="account-card__row-label">
                Couleur de l'interface
                <span className="account-card__hint">Remplace la charte graphique pour vous seul.</span>
              </span>
              {currentUser.accent_color && (
                <button
                  type="button"
                  className="account-card__ghost-btn"
                  onClick={() => void handleChangeAccentColor("")}
                  disabled={appearanceSubmitting}
                >
                  Par défaut
                </button>
              )}
            </div>
          </div>

          <div className="account-card__section">
            <span className="account-card__section-title">Notifications</span>
            <label className="account-card__row">
              <Checkbox
                checked={currentUser.email_notifications_enabled}
                onCheckedChange={handleToggleEmailNotifications}
                disabled={prefSubmitting}
                aria-label="Recevoir les notifications par email"
              />
              <span className="account-card__row-label">Recevoir les notifications par email</span>
            </label>
          </div>

          <div className="account-card__section">
            <button
              type="button"
              className="account-card__disclosure"
              onClick={() => setPasswordOpen((current) => !current)}
              aria-expanded={passwordOpen}
            >
              <KeyRound size={14} strokeWidth={1.75} aria-hidden="true" />
              Changer de mot de passe
              <ChevronDown
                size={13}
                strokeWidth={1.75}
                aria-hidden="true"
                className={passwordOpen ? "account-card__disclosure-icon account-card__disclosure-icon--open" : "account-card__disclosure-icon"}
              />
            </button>
            {passwordOpen && (
              <form className="account-card__form" onSubmit={handleChangePassword}>
                {passwordError && <p className="account-card__error">{passwordError}</p>}
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  placeholder="Mot de passe actuel"
                  autoComplete="current-password"
                  required
                />
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="Nouveau mot de passe"
                  autoComplete="new-password"
                  required
                />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Confirmer le nouveau mot de passe"
                  autoComplete="new-password"
                  required
                />
                <button
                  type="submit"
                  className="account-card__submit"
                  disabled={passwordSubmitting || !currentPassword || !newPassword}
                >
                  {passwordSubmitting ? "Mise à jour…" : "Mettre à jour"}
                </button>
              </form>
            )}
          </div>

          <button
            type="button"
            className="account-card__logout"
            onClick={() => {
              logout();
              setOpen(false);
            }}
          >
            <LogOut size={14} strokeWidth={1.75} aria-hidden="true" />
            Déconnexion
          </button>
        </div>
      )}
    </div>
  );
}
