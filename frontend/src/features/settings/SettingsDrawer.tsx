import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { changePassword, getMe, updateAppearancePreferences, updateNotificationPreferences } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import type { Me } from "../../types/watodo";
import "./SettingsDrawer.css";

interface SettingsDrawerProps {
  onClose: () => void;
}

function displayName(me: Me): string {
  return `${me.first_name} ${me.last_name}`.trim() || me.username;
}

export function SettingsDrawer({ onClose }: SettingsDrawerProps) {
  const { showToast } = useToast();
  const [me, setMe] = useState<Me | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);

  const [prefSubmitting, setPrefSubmitting] = useState(false);
  const [appearanceSubmitting, setAppearanceSubmitting] = useState(false);
  const { refreshCurrentUser } = useCurrentUser();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => setLoadError("Impossible de charger votre profil."));
  }, []);

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
      showToast("Mot de passe mis à jour.");
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Le changement a échoué.");
    } finally {
      setPasswordSubmitting(false);
    }
  }

  async function handleToggleEmailNotifications(checked: boolean) {
    if (!me) return;
    setPrefSubmitting(true);
    try {
      setMe(await updateNotificationPreferences(checked));
    } catch (err) {
      showToast(err instanceof Error ? err.message : "La mise à jour a échoué.");
    } finally {
      setPrefSubmitting(false);
    }
  }

  async function handleChangeAccentColor(color: string) {
    if (!me) return;
    setAppearanceSubmitting(true);
    try {
      setMe(await updateAppearancePreferences(color));
      await refreshCurrentUser();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "La mise à jour a échoué.");
    } finally {
      setAppearanceSubmitting(false);
    }
  }

  return (
    <div className="settings-drawer__overlay" onClick={onClose}>
      <div className="settings-drawer" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true">
        <div className="settings-drawer__header">
          <h2 className="settings-drawer__title">Paramètres</h2>
          <button type="button" className="settings-drawer__close" onClick={onClose} aria-label="Fermer">
            <X size={18} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {loadError && <p className="settings-drawer__message settings-drawer__message--error">{loadError}</p>}
        {!me && !loadError && <p className="settings-drawer__message">Chargement…</p>}

        {me && (
          <>
            <section className="settings-drawer__section">
              <h3 className="settings-drawer__section-title">Mon compte</h3>
              <dl className="settings-drawer__facts">
                <div>
                  <dt>Nom</dt>
                  <dd>{displayName(me)}</dd>
                </div>
                <div>
                  <dt>Identifiant</dt>
                  <dd>@{me.username}</dd>
                </div>
                <div>
                  <dt>Email</dt>
                  <dd>{me.email || "Non renseigné"}</dd>
                </div>
                <div>
                  <dt>Rôle</dt>
                  <dd>
                    {me.organisation_role_display}
                    {me.is_platform_admin && " · Admin plateforme"}
                  </dd>
                </div>
              </dl>
            </section>

            <section className="settings-drawer__section">
              <h3 className="settings-drawer__section-title">Mot de passe</h3>
              <form className="settings-drawer__form" onSubmit={handleChangePassword}>
                {passwordError && (
                  <p className="settings-drawer__message settings-drawer__message--error">{passwordError}</p>
                )}
                <label className="settings-drawer__field">
                  <span>Mot de passe actuel</span>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    autoComplete="current-password"
                    required
                  />
                </label>
                <label className="settings-drawer__field">
                  <span>Nouveau mot de passe</span>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    autoComplete="new-password"
                    required
                  />
                </label>
                <label className="settings-drawer__field">
                  <span>Confirmer le nouveau mot de passe</span>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    autoComplete="new-password"
                    required
                  />
                </label>
                <button
                  type="submit"
                  className="settings-drawer__submit"
                  disabled={passwordSubmitting || !currentPassword || !newPassword}
                >
                  {passwordSubmitting ? "Mise à jour…" : "Mettre à jour le mot de passe"}
                </button>
              </form>
            </section>

            <section className="settings-drawer__section">
              <h3 className="settings-drawer__section-title">Apparence</h3>
              <div className="settings-drawer__toggle-row">
                <label className="settings-drawer__color-label">
                  <input
                    type="color"
                    value={me.accent_color || "#753030"}
                    onChange={(event) => void handleChangeAccentColor(event.target.value)}
                    disabled={appearanceSubmitting}
                    aria-label="Couleur d'accent de l'interface"
                    className="settings-drawer__color-input"
                  />
                </label>
                <span>
                  Couleur de l'interface
                  <span className="settings-drawer__hint">
                    Remplace la couleur de marque dans toute l'application (boutons, barre de
                    navigation, statut « en cours »…), pour vous seul. Les couleurs qui ont un sens
                    propre (priorité, statut d'incident…) restent inchangées.
                  </span>
                </span>
                {me.accent_color && (
                  <button
                    type="button"
                    className="settings-drawer__ghost-btn"
                    onClick={() => void handleChangeAccentColor("")}
                    disabled={appearanceSubmitting}
                  >
                    Par défaut
                  </button>
                )}
              </div>
            </section>

            <section className="settings-drawer__section">
              <h3 className="settings-drawer__section-title">Notifications</h3>
              <label className="settings-drawer__toggle-row">
                <Checkbox
                  checked={me.email_notifications_enabled}
                  onCheckedChange={handleToggleEmailNotifications}
                  disabled={prefSubmitting}
                  aria-label="Recevoir les notifications par email"
                />
                <span>
                  Recevoir les notifications par email
                  <span className="settings-drawer__hint">
                    La cloche reste dans tous les cas active — ce réglage ne concerne que l'email.
                  </span>
                </span>
              </label>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
