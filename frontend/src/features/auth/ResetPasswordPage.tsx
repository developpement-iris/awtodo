import { CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { confirmPasswordReset, getPasswordResetToken } from "../../api/client";
import type { PasswordResetToken } from "../../types/watodo";
import "./ResetPasswordPage.css";

interface ResetPasswordPageProps {
  token: string;
}

// Miroir direct de `InvitationAcceptPage.tsx` (même structure à trois états :
// chargement / formulaire / succès, plus un état "lien invalide" propre à
// cet écran) — voir docs/organisation-et-comptes.md > "Réinitialisation de
// mot de passe". CSS dupliqué plutôt que partagé (convention déjà en place
// dans ce projet pour ce genre de petit bloc, voir CLAUDE.md).
export function ResetPasswordPage({ token }: ResetPasswordPageProps) {
  const [reset, setReset] = useState<PasswordResetToken | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  useEffect(() => {
    getPasswordResetToken(token)
      .then(setReset)
      .catch(() => setError("Ce lien de réinitialisation est introuvable ou a expiré."));
  }, [token]);

  const isUsable = reset !== null && reset.status === "pending" && !reset.is_expired;

  async function handleConfirm() {
    if (password !== passwordConfirm) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "La réinitialisation a échoué.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="reset-password-page">
      <div className="reset-password-page__card">
        <h1 className="reset-password-page__title">Awtodo</h1>

        {!reset && !error && <p className="reset-password-page__message">Vérification du lien…</p>}
        {error && <p className="reset-password-page__message reset-password-page__message--error">{error}</p>}

        {isUsable && !done && (
          <>
            <p className="reset-password-page__message">Choisissez votre nouveau mot de passe.</p>
            <label className="reset-password-page__field">
              <span>Nouveau mot de passe</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoFocus
                disabled={submitting}
              />
            </label>
            <label className="reset-password-page__field">
              <span>Confirmer le mot de passe</span>
              <input
                type="password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                disabled={submitting}
              />
            </label>
            <button
              type="button"
              className="reset-password-page__button"
              onClick={handleConfirm}
              disabled={submitting || !password || !passwordConfirm}
            >
              {submitting ? "Mise à jour…" : "Réinitialiser le mot de passe"}
            </button>
          </>
        )}

        {reset && !isUsable && !done && (
          <p className="reset-password-page__message">
            Ce lien de réinitialisation n'est plus valide — demandez-en un nouveau depuis l'écran de connexion.
          </p>
        )}

        {done && (
          <div className="reset-password-page__success">
            <CheckCircle2 size={32} strokeWidth={1.75} aria-hidden="true" />
            <p className="reset-password-page__message">
              Mot de passe mis à jour. Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
