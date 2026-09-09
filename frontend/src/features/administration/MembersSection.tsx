import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { getTeams, getUsers, setOrganisationRole } from "../../api/client";
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
                  <select
                    className="members-section__role-select"
                    value={user.organisation_role}
                    disabled={pendingUserId === user.id}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => handleRoleChange(user, event.target.value as OrganisationRole)}
                  >
                    {ROLE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </td>
                <td></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {openUser && <UserProfileDrawer user={openUser} teams={teams} onClose={() => setOpenUser(null)} />}
    </div>
  );
}
