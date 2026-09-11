import { useEffect, useState } from "react";
import {
  addProjectMember,
  changeProjectMemberRole,
  convertProjectToCollaborative,
  getTeams,
  inviteProjectExternalMember,
  removeProjectMember,
} from "../../api/client";
import { Combobox } from "../../components/Combobox";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import type { Project, ProjectMembership, ProjectRole, Team } from "../../types/watodo";
import "./ProjectAdminTab.css";

const ROLE_OPTIONS: { value: ProjectRole; label: string }[] = [
  { value: "chef_de_projet", label: "Chef de projet" },
  { value: "membre", label: "Membre" },
  { value: "lecteur", label: "Lecteur (lecture seule)" },
];

// Un projet individuel n'accueille que des lecteurs (session du 2026-09-11)
// — voir apps.projects.services._ensure_role_allowed_for_project_type.
// Passer en collaboratif (bloc dédié plus bas) pour ouvrir les autres rôles.
const READER_ONLY_ROLE_OPTIONS = ROLE_OPTIONS.filter((option) => option.value === "lecteur");

// Même logique que UserMenu.tsx (initiales) — duplication volontaire d'un
// petit bloc plutôt qu'une abstraction partagée pour deux usages, cohérent
// avec les conventions déjà en place dans ce projet.
function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

interface ProjectAdminTabProps {
  project: Project;
  onUpdated: (project: Project) => void;
}

export function ProjectAdminTab({ project, onUpdated }: ProjectAdminTabProps) {
  const { showToast } = useToast();
  const { currentUser } = useCurrentUser();
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingMembershipId, setPendingMembershipId] = useState<string | null>(null);
  const [groupSelection, setGroupSelection] = useState("");
  const [groupSubmitting, setGroupSubmitting] = useState(false);
  const [email, setEmail] = useState("");
  const [emailRole, setEmailRole] = useState<ProjectRole>("membre");
  const [emailSubmitting, setEmailSubmitting] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName] = useState("");
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [convertTeam, setConvertTeam] = useState("");
  const [convertSubmitting, setConvertSubmitting] = useState(false);

  useEffect(() => {
    getTeams()
      .then(setTeams)
      .catch(() => undefined);
  }, []);

  const isIndividual = project.project_type === "individuel";
  const roleOptions = isIndividual ? READER_ONLY_ROLE_OPTIONS : ROLE_OPTIONS;

  // Le rôle par défaut du formulaire "ajouter par email" (`membre`) n'est
  // pas proposé sur un projet individuel — le recaler sur `lecteur`, sinon
  // le Combobox afficherait un état sélectionné hors de sa propre liste.
  useEffect(() => {
    if (isIndividual) setEmailRole("lecteur");
  }, [isIndividual]);

  const isManager = project.permissions.can_manage_members;
  const team = teams.find((t) => t.id === project.team);
  const memberIds = new Set(project.members.map((m) => m.user.id));
  const addableFromGroup = (team?.members ?? []).filter((user) => !memberIds.has(user.id));
  const myTeams = teams.filter((t) => currentUser?.teams.includes(t.id));

  async function handleConvertToCollaborative() {
    if (!convertTeam) return;
    setConvertSubmitting(true);
    setError(null);
    try {
      onUpdated(await convertProjectToCollaborative(project.id, convertTeam));
      setConvertTeam("");
      showToast("Projet passé en collaboratif.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "La conversion a échoué.");
    } finally {
      setConvertSubmitting(false);
    }
  }

  async function handleAddFromGroup() {
    if (!groupSelection) return;
    setGroupSubmitting(true);
    setError(null);
    try {
      onUpdated(await addProjectMember(project.id, { user: groupSelection }));
      setGroupSelection("");
      showToast("Membre ajouté.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'ajout a échoué.");
    } finally {
      setGroupSubmitting(false);
    }
  }

  async function handleAddByEmail() {
    if (!email.trim()) return;
    setEmailSubmitting(true);
    setError(null);
    try {
      onUpdated(await addProjectMember(project.id, { email: email.trim(), role: emailRole }));
      setEmail("");
      setEmailRole("membre");
      showToast(emailRole === "lecteur" ? "Accès en lecture accordé." : "Membre ajouté.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'ajout a échoué.");
    } finally {
      setEmailSubmitting(false);
    }
  }

  async function handleInviteExternal() {
    if (!inviteEmail.trim()) return;
    setInviteSubmitting(true);
    setError(null);
    try {
      onUpdated(
        await inviteProjectExternalMember(project.id, {
          email: inviteEmail.trim(),
          first_name: inviteFirstName.trim() || undefined,
          last_name: inviteLastName.trim() || undefined,
        }),
      );
      setInviteEmail("");
      setInviteFirstName("");
      setInviteLastName("");
      showToast("Invitation envoyée.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'invitation a échoué.");
    } finally {
      setInviteSubmitting(false);
    }
  }

  async function handleRoleChange(membership: ProjectMembership, nextRole: ProjectRole) {
    if (nextRole === membership.role) return;
    setPendingMembershipId(membership.id);
    setError(null);
    try {
      onUpdated(await changeProjectMemberRole(project.id, membership.id, nextRole));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le changement de rôle a échoué.");
    } finally {
      setPendingMembershipId(null);
    }
  }

  async function handleRemove(membership: ProjectMembership) {
    setPendingMembershipId(membership.id);
    setError(null);
    try {
      onUpdated(await removeProjectMember(project.id, membership.id));
      showToast("Membre retiré.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le retrait a échoué.");
    } finally {
      setPendingMembershipId(null);
    }
  }

  return (
    <div className="project-admin-tab">
      {error && <p className="project-admin-tab__message project-admin-tab__message--error">{error}</p>}

      <table className="project-admin-tab__table">
        <thead>
          <tr>
            <th>Membre</th>
            <th>Rôle</th>
            {isManager && <th></th>}
          </tr>
        </thead>
        <tbody>
          {project.members.map((membership) => {
            const name = `${membership.user.first_name} ${membership.user.last_name}`.trim() || membership.user.username;
            return (
            <tr key={membership.id}>
              <td>
                <div className="project-admin-tab__member">
                  <span className="project-admin-tab__avatar">
                    {initials(name)}
                    <span
                      className={`project-admin-tab__status-dot project-admin-tab__status-dot--${membership.user.account_status}`}
                      title={membership.user.account_status === "active" ? "Compte actif" : "Invitation en attente"}
                    />
                  </span>
                  <div className="project-admin-tab__member-info">
                    <span className="project-admin-tab__member-name">
                      {name}
                      {membership.user.account_type === "externe" && (
                        <span className="project-admin-tab__external-badge">Externe</span>
                      )}
                    </span>
                    <span className="project-admin-tab__member-username">@{membership.user.username}</span>
                  </div>
                </div>
              </td>
              <td>
                {/* Sur un projet individuel, le chef de projet (le créateur)
                    ne peut pas être rétrogradé en lecteur depuis ce sélecteur
                    — `roleOptions` ne proposerait alors que "lecteur", hors
                    de sa valeur actuelle. Reste en lecture (texte simple),
                    cohérent avec le refus backend de toute façon
                    (`_ensure_not_last_manager`). */}
                {isManager && roleOptions.some((option) => option.value === membership.role) ? (
                  <span className="project-admin-tab__role-select">
                    <Combobox
                      options={roleOptions.map((o) => ({ value: o.value, label: o.label }))}
                      value={membership.role}
                      onChange={(value) => handleRoleChange(membership, value as ProjectRole)}
                      disabled={pendingMembershipId === membership.id}
                      clearable={false}
                    />
                  </span>
                ) : (
                  membership.role_display
                )}
              </td>
              {isManager && (
                <td className="project-admin-tab__actions">
                  <div className="project-admin-tab__actions-inner">
                    <button
                      type="button"
                      className="project-admin-tab__action project-admin-tab__action--danger"
                      onClick={() => handleRemove(membership)}
                      disabled={pendingMembershipId === membership.id}
                    >
                      Retirer
                    </button>
                  </div>
                </td>
              )}
            </tr>
            );
          })}
        </tbody>
      </table>

      {isManager && (
        <div className="project-admin-tab__forms">
          {project.permissions.can_convert_to_collaborative && (
            <div className="project-admin-tab__form">
              <h3>Passer en projet collaboratif</h3>
              <p className="project-admin-tab__hint">
                Un projet individuel n'accueille que des lecteurs. Pour y ajouter un membre ou un autre chef de
                projet, rattachez-le d'abord à un groupe — <strong>irréversible</strong>.
              </p>
              {myTeams.length === 0 ? (
                <p className="project-admin-tab__hint">Vous n'appartenez à aucun groupe pour l'instant.</p>
              ) : (
                <div className="project-admin-tab__form-row">
                  <Combobox
                    options={myTeams.map((t) => ({ value: t.id, label: t.name }))}
                    value={convertTeam}
                    onChange={setConvertTeam}
                    placeholder="Choisir un groupe…"
                    searchPlaceholder="Rechercher un groupe…"
                  />
                  <button
                    type="button"
                    onClick={handleConvertToCollaborative}
                    disabled={convertSubmitting || !convertTeam}
                  >
                    Convertir
                  </button>
                </div>
              )}
            </div>
          )}

          {team && addableFromGroup.length > 0 && (
            <div className="project-admin-tab__form">
              <h3>Ajouter un membre du groupe</h3>
              <div className="project-admin-tab__form-row">
                <Combobox
                  options={addableFromGroup.map((user) => ({
                    value: user.id,
                    label: `${user.first_name} ${user.last_name}`.trim() || user.username,
                  }))}
                  value={groupSelection}
                  onChange={setGroupSelection}
                  placeholder="Choisir…"
                  searchPlaceholder="Rechercher un nom…"
                />
                <button type="button" onClick={handleAddFromGroup} disabled={groupSubmitting || !groupSelection}>
                  Ajouter
                </button>
              </div>
            </div>
          )}

          <div className="project-admin-tab__form">
            <h3>Ajouter un membre existant de l'organisation</h3>
            <p className="project-admin-tab__hint">
              Recherche par email, même hors du groupe rattaché au projet. Le rôle <strong>Lecteur</strong> donne un
              accès en lecture seule (tâches, cahier des charges, bloc-notes) — pas d'accès au budget, aux incidents,
              au planning ni aux statistiques.
              {isIndividual && " Un projet individuel n'accueille que des lecteurs."}
            </p>
            <div className="project-admin-tab__form-row project-admin-tab__form-row--stacked">
              <input
                type="email"
                placeholder="email@organisation.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <Combobox
                options={roleOptions.map((o) => ({ value: o.value, label: o.label }))}
                value={emailRole}
                onChange={(value) => setEmailRole(value as ProjectRole)}
                clearable={false}
              />
              <button type="button" onClick={handleAddByEmail} disabled={emailSubmitting || !email.trim()}>
                Ajouter
              </button>
            </div>
          </div>

          <div className="project-admin-tab__form">
            <h3>Inviter une personne externe</h3>
            <p className="project-admin-tab__hint">Aucun compte existant — crée un compte externe restreint à ce projet.</p>
            <div className="project-admin-tab__form-row project-admin-tab__form-row--stacked">
              <input
                type="email"
                placeholder="Email"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
              />
              <input
                type="text"
                placeholder="Prénom (optionnel)"
                value={inviteFirstName}
                onChange={(event) => setInviteFirstName(event.target.value)}
              />
              <input
                type="text"
                placeholder="Nom (optionnel)"
                value={inviteLastName}
                onChange={(event) => setInviteLastName(event.target.value)}
              />
              <button type="button" onClick={handleInviteExternal} disabled={inviteSubmitting || !inviteEmail.trim()}>
                Inviter
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
