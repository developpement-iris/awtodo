import { useEffect, useState } from "react";
import { createInvitation, getInvitations, getTeams, resendInvitation } from "../../api/client";
import { SkeletonTable } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../context/ToastContext";
import type { Invitation, Team, User } from "../../types/watodo";
import "./InvitationsSection.css";

interface InvitationsSectionProps {
  currentUser: User;
}

function invitationTone(status: Invitation["status"]) {
  if (status === "accepted") return "positive" as const;
  if (status === "pending") return "neutral" as const;
  return "neutral" as const;
}

export function InvitationsSection({ currentUser }: InvitationsSectionProps) {
  const { showToast } = useToast();
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingToken, setPendingToken] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [teamId, setTeamId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function loadInvitations() {
    getInvitations()
      .then(setInvitations)
      .catch(() => setError("Impossible de charger les invitations."));
  }

  useEffect(loadInvitations, []);
  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch(() => undefined);
  }, []);

  const invitableTeams =
    currentUser.organisation_role === "admin"
      ? teams.filter((team) => team.organisation === currentUser.organisation)
      : teams.filter((team) => team.created_by === currentUser.id);

  async function handleCreate() {
    if (!email.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await createInvitation({
        email: email.trim(),
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
        team: teamId || undefined,
      });
      setInvitations((current) => (current ? [created, ...current] : current));
      setEmail("");
      setFirstName("");
      setLastName("");
      setTeamId("");
      showToast("Invitation envoyée.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'envoi a échoué.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend(invitation: Invitation) {
    setPendingToken(invitation.token);
    setError(null);
    try {
      const created = await resendInvitation(invitation.token);
      setInvitations((current) =>
        current
          ? [created, ...current.map((item) => (item.token === invitation.token ? { ...item, status: "expired" as const } : item))]
          : current,
      );
      showToast("Invitation renvoyée.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le renvoi a échoué.");
    } finally {
      setPendingToken(null);
    }
  }

  return (
    <div className="invitations-section">
      {error && <p className="invitations-section__message invitations-section__message--error">{error}</p>}

      <div className="invitations-section__form">
        <h3>Inviter un compte interne</h3>
        <div className="invitations-section__form-row">
          <input type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} />
          <input
            type="text"
            placeholder="Prénom (optionnel)"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
          />
          <input
            type="text"
            placeholder="Nom (optionnel)"
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
          />
          {invitableTeams.length > 0 && (
            <select value={teamId} onChange={(event) => setTeamId(event.target.value)}>
              <option value="">Aucun groupe</option>
              {invitableTeams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
          )}
          <button type="button" onClick={handleCreate} disabled={submitting || !email.trim()}>
            {submitting ? "Envoi…" : "Inviter"}
          </button>
        </div>
      </div>

      {invitations === null && !error && <SkeletonTable columns={4} rows={3} />}

      {invitations !== null && invitations.length === 0 && (
        <p className="invitations-section__message">Aucune invitation pour l'instant.</p>
      )}

      {invitations !== null && invitations.length > 0 && (
        <table className="invitations-section__table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Groupe</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {invitations.map((invitation) => (
              <tr key={invitation.id}>
                <td>{invitation.email}</td>
                <td>{teams.find((team) => team.id === invitation.team)?.name ?? "—"}</td>
                <td>
                  <StatusBadge label={invitation.status_display} tone={invitationTone(invitation.status)} />
                </td>
                <td className="invitations-section__actions">
                  {invitation.status === "pending" && (
                    <button
                      type="button"
                      onClick={() => handleResend(invitation)}
                      disabled={pendingToken === invitation.token}
                    >
                      Renvoyer
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
