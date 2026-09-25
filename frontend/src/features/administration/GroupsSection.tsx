import { Check, Copy, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  addTeamMember,
  changeTeamMemberRole,
  createTeam,
  getTeams,
  getUsers,
  removeTeamMember,
  renameTeam,
} from "../../api/client";
import { Combobox } from "../../components/Combobox";
import { CreationCard } from "../../components/CreationCard";
import { InlineEditableText } from "../../components/InlineEditableText";
import { SkeletonCards } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type { Team, TeamMembershipRole, User } from "../../types/watodo";
import "./GroupsSection.css";

const ROLE_OPTIONS: { value: TeamMembershipRole; label: string }[] = [
  { value: "membre", label: "Membre" },
  { value: "administrateur", label: "Administrateur" },
];

interface GroupsSectionProps {
  currentUser: User;
}

export function GroupsSection({ currentUser }: GroupsSectionProps) {
  const { showToast } = useToast();
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [pendingTeamId, setPendingTeamId] = useState<string | null>(null);
  const [addSelection, setAddSelection] = useState<Record<string, string>>({});
  const [copiedTeamId, setCopiedTeamId] = useState<string | null>(null);

  async function handleCopyId(teamId: string) {
    try {
      await navigator.clipboard.writeText(teamId);
      setCopiedTeamId(teamId);
      window.setTimeout(() => setCopiedTeamId((current) => (current === teamId ? null : current)), 2000);
    } catch {
      showToast("Impossible de copier automatiquement — sélectionnez l'identifiant manuellement.");
    }
  }

  function loadTeams() {
    getTeams()
      .then(setTeams)
      .catch(() => setError("Impossible de charger les groupes."));
  }

  useEffect(loadTeams, []);
  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(() => undefined);
  }, []);

  function updateTeamLocally(updated: Team) {
    setTeams((current) => (current ? current.map((team) => (team.id === updated.id ? updated : team)) : current));
  }

  const orgTeams = (teams ?? []).filter((team) => team.organisation === currentUser.organisation);
  // Comptes externes exclus du picker "membres de l'organisation" — voir
  // CLAUDE.md > "Comptes et invitations" (restriction de visibilité,
  // "pickers de groupe" explicitement cité).
  const orgUsers = users.filter(
    (user) => user.organisation === currentUser.organisation && user.account_type === "interne",
  );

  async function handleCreate() {
    if (!newTeamName.trim()) return;
    setCreateSubmitting(true);
    setError(null);
    try {
      const created = await createTeam(newTeamName.trim());
      setTeams((current) => (current ? [...current, created] : current));
      setCreating(false);
      setNewTeamName("");
      showToast("Groupe créé.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "La création a échoué.");
    } finally {
      setCreateSubmitting(false);
    }
  }

  async function handleAddMember(team: Team) {
    const userId = addSelection[team.id];
    if (!userId) return;
    setPendingTeamId(team.id);
    setError(null);
    try {
      updateTeamLocally(await addTeamMember(team.id, userId));
      setAddSelection((current) => ({ ...current, [team.id]: "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'ajout a échoué.");
    } finally {
      setPendingTeamId(null);
    }
  }

  async function handleChangeRole(team: Team, membershipId: string, role: TeamMembershipRole) {
    setPendingTeamId(team.id);
    setError(null);
    try {
      updateTeamLocally(await changeTeamMemberRole(team.id, membershipId, role));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le changement de rôle a échoué.");
    } finally {
      setPendingTeamId(null);
    }
  }

  async function handleRemoveMember(team: Team, userId: string) {
    setPendingTeamId(team.id);
    setError(null);
    try {
      updateTeamLocally(await removeTeamMember(team.id, userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le retrait a échoué.");
    } finally {
      setPendingTeamId(null);
    }
  }

  async function handleRename(team: Team, name: string) {
    setPendingTeamId(team.id);
    setError(null);
    try {
      updateTeamLocally(await renameTeam(team.id, name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le renommage a échoué.");
    } finally {
      setPendingTeamId(null);
    }
  }

  return (
    <div className="groups-section">
      {error && <p className="groups-section__message groups-section__message--error">{error}</p>}
      {teams === null && !error && <SkeletonCards count={2} />}

      {teams !== null && (
        <div className="groups-section__grid">
          {orgTeams.map((team) => {
            // Créateur du groupe OU admin d'organisation/de plateforme —
            // flag calculé côté backend (voir CLAUDE.md > "Permissions API"),
            // remplace l'ancien calcul client `team.created_by === currentUser.id`
            // qui ne voyait pas les overrides admin.
            const isManager = team.can_manage;
            const memberIds = new Set(team.members.map((m) => m.id));
            const addableUsers = orgUsers.filter((user) => !memberIds.has(user.id));

            return (
              <div key={team.id} className="groups-section__card">
                <h3 className="groups-section__card-title">
                  <InlineEditableText
                    value={team.name}
                    onSave={(name) => handleRename(team, name)}
                    ariaLabel="Nom du groupe"
                    disabled={!isManager || pendingTeamId === team.id}
                  />
                </h3>
                <button
                  type="button"
                  className="groups-section__card-id"
                  onClick={() => void handleCopyId(team.id)}
                  title="Copier l'identifiant du groupe"
                >
                  <code>{team.id}</code>
                  {copiedTeamId === team.id ? (
                    <Check size={12} strokeWidth={2} aria-hidden="true" />
                  ) : (
                    <Copy size={12} strokeWidth={1.75} aria-hidden="true" />
                  )}
                </button>
                <ul className="groups-section__members">
                  {team.memberships.map((membership) => {
                    const member = membership.user;
                    const name = `${member.first_name} ${member.last_name}`.trim() || member.username;
                    return (
                      <li key={membership.id}>
                        <span>{name}</span>
                        {isManager ? (
                          <span className="groups-section__member-actions">
                            <Combobox
                              options={ROLE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                              value={membership.role}
                              onChange={(role) =>
                                handleChangeRole(team, membership.id, role as TeamMembershipRole)
                              }
                              disabled={pendingTeamId === team.id}
                              clearable={false}
                            />
                            <button
                              type="button"
                              className="groups-section__remove"
                              onClick={() => handleRemoveMember(team, member.id)}
                              disabled={pendingTeamId === team.id}
                              aria-label="Retirer du groupe"
                              title="Retirer du groupe"
                            >
                              <X size={13} strokeWidth={1.75} aria-hidden="true" />
                            </button>
                          </span>
                        ) : (
                          membership.role === "administrateur" && (
                            <span className="groups-section__role-badge">Administrateur</span>
                          )
                        )}
                      </li>
                    );
                  })}
                  {team.memberships.length === 0 && <li className="groups-section__empty">Aucun membre.</li>}
                </ul>

                {isManager && addableUsers.length > 0 && (
                  <div className="groups-section__add">
                    <Combobox
                      options={addableUsers.map((user) => ({
                        value: user.id,
                        label: `${user.first_name} ${user.last_name}`.trim() || user.username,
                      }))}
                      value={addSelection[team.id] ?? ""}
                      onChange={(value) =>
                        setAddSelection((current) => ({ ...current, [team.id]: value }))
                      }
                      disabled={pendingTeamId === team.id}
                      placeholder="Ajouter un membre…"
                      searchPlaceholder="Rechercher un nom…"
                    />
                    <button
                      type="button"
                      onClick={() => handleAddMember(team)}
                      disabled={pendingTeamId === team.id || !addSelection[team.id]}
                    >
                      Ajouter
                    </button>
                  </div>
                )}
              </div>
            );
          })}

          {creating ? (
            <div className="groups-section__card groups-section__card--creating">
              <input
                type="text"
                className="groups-section__name-input"
                placeholder="Nom du groupe"
                value={newTeamName}
                onChange={(event) => setNewTeamName(event.target.value)}
                autoFocus
              />
              <div className="groups-section__create-actions">
                <button
                  type="button"
                  onClick={() => {
                    setCreating(false);
                    setNewTeamName("");
                  }}
                  disabled={createSubmitting}
                >
                  Annuler
                </button>
                <button type="button" onClick={handleCreate} disabled={createSubmitting || !newTeamName.trim()}>
                  {createSubmitting ? "Création…" : "Créer"}
                </button>
              </div>
            </div>
          ) : (
            <CreationCard label="Nouveau groupe" onClick={() => setCreating(true)} />
          )}
        </div>
      )}
    </div>
  );
}
