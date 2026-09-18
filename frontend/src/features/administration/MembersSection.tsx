import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { deactivateUser, getTeams, getUsers, reactivateUser, setOrganisationRole } from "../../api/client";
import { Combobox } from "../../components/Combobox";
import { SkeletonTable } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type { OrganisationRole, Team, User } from "../../types/watodo";
import { UserProfileDrawer } from "./UserProfileDrawer";
import "./MembersSection.css";

const ROLE_OPTIONS: { value: OrganisationRole; label: string }[] = [
  { value: "admin", label: "Administrateur" },
  { value: "chef_de_projet", label: "Chef de projet" },
  { value: "membre", label: "Membre" },
];

interface MembersSectionProps {
  currentUser: User;
}

export function MembersSection({ currentUser }: MembersSectionProps) {
  const { showToast } = useToast();
  const [users, setUsers] = useState<User[] | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingUserId, setPendingUserId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [openUser, setOpenUser] = useState<User | null>(null);

  useEffect(() => {
    getUsers()
      .then(setUsers)
      .catch(() => setError("Impossible de charger les membres."));
    getTeams()
      .then(setTeams)
      .catch(() => undefined);
  }, []);

  // Comptes externes exclus de l'annuaire "Membres" de l'organisation — voir
  // CLAUDE.md > "Comptes et invitations" (restriction de visibilité) :
  // n'ont pas de organisation_role pertinent, ne doivent pas apparaître
  // mêlés aux membres internes ici.
  const orgUsers = (users ?? []).filter(
    (user) => user.organisation === currentUser.organisation && user.account_type === "interne",
  );

  const normalizedSearch = search.trim().toLowerCase();
  const visibleUsers = normalizedSearch
    ? orgUsers.filter((user) =>
        `${user.first_name} ${user.last_name} ${user.username}`.toLowerCase().includes(normalizedSearch),
      )
    : orgUsers;

  async function handleRoleChange(user: User, role: OrganisationRole) {
    setPendingUserId(user.id);
    setError(null);
    try {
      const updated = await setOrganisationRole(user.id, role);
      setUsers((current) => (current ? current.map((u) => (u.id === updated.id ? updated : u)) : current));
      showToast("Rôle mis à jour.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "La mise à jour a échoué.");
    } finally {
      setPendingUserId(null);
    }
  }

  async function handleToggleAccess(user: User) {
    setPendingUserId(user.id);
    setError(null);
    try {
      const updated = user.account_status === "desactive" ? await reactivateUser(user.id) : await deactivateUser(user.id);
      setUsers((current) => (current ? current.map((u) => (u.id === updated.id ? updated : u)) : current));
      showToast(updated.account_status === "desactive" ? "Accès coupé." : "Accès rétabli.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'opération a échoué.");
    } finally {
      setPendingUserId(null);
    }
  }

  return (
    <div className="members-section">
      <div className="members-section__toolbar">
        <div className="members-section__search">
          <Search size={14} strokeWidth={1.75} aria-hidden="true" />
          <input
            type="text"
            placeholder="Rechercher un membre par nom…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      {error && <p className="members-section__message members-section__message--error">{error}</p>}
      {users === null && !error && <SkeletonTable columns={3} rows={4} />}

      {users !== null && visibleUsers.length === 0 && (
        <p className="members-section__message">Aucun membre ne correspond à cette recherche.</p>
      )}

      {users !== null && visibleUsers.length > 0 && (
        <table className="members-section__table">
          <thead>
            <tr>
              <th>Utilisateur</th>
              <th>Rôle dans l'organisation</th>
              <th>Accès</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visibleUsers.map((user) => (
              <tr key={user.id} className="members-section__row" onClick={() => setOpenUser(user)}>
                <td>
                  {`${user.first_name} ${user.last_name}`.trim() || user.username}
                  {user.is_platform_admin && (
                    <span className="members-section__platform-badge">Admin plateforme</span>
                  )}
                </td>
                <td>
                  <span
                    className="members-section__role-select"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <Combobox
                      options={ROLE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                      value={user.organisation_role}
                      disabled={pendingUserId === user.id}
                      clearable={false}
                      onChange={(value) => handleRoleChange(user, value as OrganisationRole)}
                    />
                  </span>
                </td>
                <td>
                  <span
                    className={`members-section__access-dot members-section__access-dot--${user.account_status}`}
                  />
                  {user.account_status_display}
                </td>
                <td onClick={(event) => event.stopPropagation()}>
                  {/* Un compte "en attente" (jamais activé via invitation) n'a
                      rien à désactiver — voir `deactivate_account`, réservé
                      aux comptes actifs — et personne ne peut couper son
                      propre accès (protection contre l'auto-verrouillage). */}
                  {user.account_status !== "pending" && user.id !== currentUser.id && (
                    <button
                      type="button"
                      className={
                        user.account_status === "desactive"
                          ? "members-section__access-action"
                          : "members-section__access-action members-section__access-action--danger"
                      }
                      onClick={() => handleToggleAccess(user)}
                      disabled={pendingUserId === user.id}
                    >
                      {user.account_status === "desactive" ? "Réactiver" : "Désactiver"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {openUser && <UserProfileDrawer user={openUser} teams={teams} onClose={() => setOpenUser(null)} />}
    </div>
  );
}
