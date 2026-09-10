import { motion } from "motion/react";
import { useState } from "react";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import { DatePickerField } from "../../components/DatePickerField";
import { useCurrentUser } from "../../context/CurrentUserContext";
import type { Project, Team, User } from "../../types/watodo";
import "./ProjectCreateDialog.css";

// Comptes externes exclus par défense (voir CLAUDE.md — restriction de
// visibilité) — ne devraient normalement jamais se retrouver dans un
// groupe (TeamMembership), mais on ne prend pas le risque de les proposer.
function selectableMembersOf(team: Team | undefined, currentUserId: string | undefined): User[] {
  return (team?.members ?? []).filter((user) => user.id !== currentUserId && user.account_type === "interne");
}

const PRIORITY_OPTIONS: { value: Exclude<Project["priority"], null>; label: string }[] = [
  { value: "basse", label: "Basse" },
  { value: "moyenne", label: "Moyenne" },
  { value: "haute", label: "Haute" },
  { value: "critique", label: "Critique" },
];

export interface ProjectCreateFormValues {
  name: string;
  description: string;
  project_type: Project["project_type"];
  deadline: string;
  already_in_production: boolean;
  priority: Exclude<Project["priority"], null> | "";
  team: string;
  member_ids: string[];
}

interface ProjectCreateDialogProps {
  myTeams: Team[];
  onCancel: () => void;
  onSubmit: (values: ProjectCreateFormValues) => void;
  submitting?: boolean;
  error?: string | null;
}

export function ProjectCreateDialog({
  myTeams,
  onCancel,
  onSubmit,
  submitting = false,
  error = null,
}: ProjectCreateDialogProps) {
  const { currentUser } = useCurrentUser();
  const [values, setValues] = useState<ProjectCreateFormValues>({
    name: "",
    description: "",
    project_type: "individuel",
    deadline: "",
    already_in_production: false,
    priority: "",
    team: "",
    member_ids: [],
  });

  const needsTeam = values.project_type === "collaboratif";
  const isValid = values.name.trim().length > 0 && (!needsTeam || values.team.length > 0);
  const selectedTeam = myTeams.find((team) => team.id === values.team);
  const selectableMembers = selectableMembersOf(selectedTeam, currentUser?.id);

  function update<K extends keyof ProjectCreateFormValues>(key: K, value: ProjectCreateFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function toggleMember(userId: string) {
    setValues((current) => ({
      ...current,
      member_ids: current.member_ids.includes(userId)
        ? current.member_ids.filter((id) => id !== userId)
        : [...current.member_ids, userId],
    }));
  }

  return (
    <div className="project-create-dialog__overlay" onClick={onCancel}>
      <div className="project-create-dialog" onClick={(event) => event.stopPropagation()}>
        <h2 className="project-create-dialog__title">Nouveau projet</h2>

        <div className="project-create-dialog__grid">
          <label className="project-create-dialog__field project-create-dialog__field--full">
            <span>Nom</span>
            <input type="text" value={values.name} onChange={(event) => update("name", event.target.value)} autoFocus />
          </label>

          <label className="project-create-dialog__field project-create-dialog__field--full">
            <span>Description</span>
            <textarea
              rows={3}
              value={values.description}
              onChange={(event) => update("description", event.target.value)}
            />
          </label>

          <label className="project-create-dialog__field">
            <span>Type</span>
            <Combobox
              options={[
                { value: "individuel", label: "Individuel" },
                { value: "collaboratif", label: "Collaboratif" },
              ]}
              value={values.project_type}
              onChange={(value) => update("project_type", value as Project["project_type"])}
              clearable={false}
            />
          </label>

          <label className="project-create-dialog__field">
            <span>Priorité</span>
            <Combobox
              options={[
                { value: "", label: "Non définie" },
                ...PRIORITY_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
              ]}
              value={values.priority}
              onChange={(value) => update("priority", value as ProjectCreateFormValues["priority"])}
              placeholder="Non définie"
            />
          </label>

          <label className="project-create-dialog__field">
            <span>Échéance</span>
            <DatePickerField
              value={values.already_in_production ? "" : values.deadline}
              onChange={(value) => update("deadline", value)}
              disabled={values.already_in_production}
            />
          </label>

          <label className="project-create-dialog__field project-create-dialog__field--full project-create-dialog__field--inline">
            <Checkbox
              checked={values.already_in_production}
              onCheckedChange={(checked) =>
                setValues((current) => ({
                  ...current,
                  already_in_production: checked,
                  deadline: checked ? "" : current.deadline,
                }))
              }
              aria-label="Déjà en production"
            />
            <span>Déjà en production (pas de date d'échéance)</span>
          </label>

          {needsTeam && (
            <label className="project-create-dialog__field">
              <span>Groupe</span>
              <Combobox
                options={myTeams.map((team) => ({ value: team.id, label: team.name }))}
                value={values.team}
                placeholder="Choisir un groupe"
                searchPlaceholder="Rechercher un groupe…"
                onChange={(teamId) => {
                  const team = myTeams.find((candidate) => candidate.id === teamId);
                  // Tout le groupe est ajouté par défaut au projet — décocher
                  // ci-dessous reste possible pour exclure quelqu'un au cas
                  // par cas, mais le cas courant ("le groupe entier") ne doit
                  // pas demander de tout cocher à la main.
                  const defaultMemberIds = selectableMembersOf(team, currentUser?.id).map((user) => user.id);
                  setValues((current) => ({ ...current, team: teamId, member_ids: defaultMemberIds }));
                }}
              />
            </label>
          )}

          {needsTeam && selectableMembers.length > 0 && (
            <label className="project-create-dialog__field project-create-dialog__field--full">
              <span>Membres du groupe ajoutés au projet — décochez pour exclure quelqu'un</span>
              <div className="project-create-dialog__member-list">
                {selectableMembers.map((user) => (
                  <label key={user.id} className="project-create-dialog__member-item">
                    <Checkbox
                      checked={values.member_ids.includes(user.id)}
                      onCheckedChange={() => toggleMember(user.id)}
                      aria-label={`${user.first_name} ${user.last_name}`.trim() || user.username}
                    />
                    {`${user.first_name} ${user.last_name}`.trim() || user.username}
                  </label>
                ))}
              </div>
            </label>
          )}
        </div>

        {needsTeam && myTeams.length === 0 && (
          <p className="project-create-dialog__hint">
            Vous n'appartenez à aucun groupe — un projet collaboratif doit être rattaché à un groupe dont vous êtes
            membre. Rapprochez-vous d'un administrateur, ou créez un projet individuel.
          </p>
        )}

        {error && <p className="project-create-dialog__error">{error}</p>}

        <div className="project-create-dialog__actions">
          <motion.button
            type="button"
            className="project-create-dialog__cancel"
            onClick={onCancel}
            disabled={submitting}
            whileTap={{ scale: 0.96 }}
          >
            Annuler
          </motion.button>
          <motion.button
            type="button"
            className="project-create-dialog__confirm"
            disabled={!isValid || submitting}
            onClick={() => onSubmit(values)}
            whileTap={{ scale: 0.96 }}
          >
            {submitting ? "Création…" : "Créer le projet"}
          </motion.button>
        </div>
      </div>
    </div>
  );
}
