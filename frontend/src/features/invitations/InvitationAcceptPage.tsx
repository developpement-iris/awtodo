import { CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { acceptInvitation, getInvitationByToken } from "../../api/client";
import type { Invitation } from "../../types/watodo";
import "./InvitationAcceptPage.css";

interface InvitationAcceptPageProps {
  token: string;
}

export function InvitationAcceptPage({ token }: InvitationAcceptPageProps) {
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");

  useEffect(() => {
    getInvitationByToken(token)
      .then(setInvitation)
      .catch(() => setError("Cette invitation est introuvable ou a expiré."));
  }, [token]);

  async function handleAccept() {
    if (password !== passwordConfirm) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setAccepting(true);
    setError(null);
    try {
      const updated = await acceptInvitation(token, password);
      setInvitation(updated);
      setAccepted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'acceptation a échoué.");
    } finally {
      setAccepting(false);
    }
  }

  return (
    <div className="invitation-accept-page">
      <div className="invitation-accept-page__card">
        <h1 className="invitation-accept-page__title">Awtodo</h1>

        {!invitation && !error && <p className="invitation-accept-page__message">Chargement…</p>}
        {error && <p className="invitation-accept-page__message invitation-accept-page__message--error">{error}</p>}

        {invitation && !accepted && invitation.status === "pending" && (
          <>
            <p className="invitation-accept-page__message">
              Vous êtes invité·e à rejoindre <strong>{invitation.organisation_name}</strong> sur Awtodo, avec l'adresse{" "}
              <strong>{invitation.email}</strong>. Choisissez un mot de passe pour activer votre compte.
            </p>
            <label className="invitation-accept-page__field">
              <span>Mot de passe</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={accepting}
              />
            </label>
            <label className="invitation-accept-page__field">
              <span>Confirmer le mot de passe</span>
              <input
                type="password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                disabled={accepting}
              />
            </label>
            <button
              type="button"
              className="invitation-accept-page__button"
              onClick={handleAccept}
              disabled={accepting || !password || !passwordConfirm}
            >
              {accepting ? "Activation…" : "Accepter l'invitation"}
            </button>
          </>
        )}

        {invitation && invitation.status !== "pending" && !accepted && (
          <p className="invitation-accept-page__message">Cette invitation n'est plus valide.</p>
        )}

        {accepted && (
          <div className="invitation-accept-page__success">
            <CheckCircle2 size={32} strokeWidth={1.75} aria-hidden="true" />
            <p className="invitation-accept-page__message">
              Compte activé. Vous pouvez maintenant vous connecter avec votre identifiant et le mot de passe choisi.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
