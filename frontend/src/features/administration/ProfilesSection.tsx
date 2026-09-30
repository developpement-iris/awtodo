import { ShieldCheck, Trash2, UserPlus, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  archivePermissionProfile,
  assignPermissionProfile,
  createPermissionProfile,
  getPermissionProfiles,
  unassignPermissionProfile,
} from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import { Skeleton } from "../../components/Skeleton";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import type { PermissionCapabilityKey, PermissionProfile } from "../../types/watodo";
import "./ProfilesSection.css";

// Miroir de apps.accounts.models.PERMISSION_CAPABILITY_CHOICES (backend,
// source de vérité) — à garder synchronisé.
const CAPABILITY_OPTIONS: { key: PermissionCapabilityKey; label: string }[] = [
  { key: "manage_members", label: "Activer/désactiver des comptes membres" },
  { key: "manage_groups", label: "Gérer les groupes (création, composition, renommage)" },
  { key: "manage_invitations", label: "Inviter de nouveaux comptes internes" },
  { key: "manage_branding", label: "Gérer les couleurs de marque de l'organisation" },
  { key: "manage_integrations", label: "Gérer la connexion Office 365 et les clés API" },
];

function displayName(user: { first_name: string; last_name: string; username: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function ProfilesSection() {
  const { users } = useCurrentUser();
  const { showToast } = useToast();
  const [profiles, setProfiles] = useState<PermissionProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  function reload() {
    setReloadKey((k) => k + 1);
  }

  useEffect(() => {
    getPermissionProfiles()
      .then((all) => setProfiles(all.filter((p) => p.status === "active")))
      .catch(() => setProfiles([]));
  }, [reloadKey]);

  // --- Création ----------------------------------------------------------
  const [name, setName] = useState("");
  const [capabilities, setCapabilities] = useState<Set<PermissionCapabilityKey>>(new Set());
  const [creating, setCreating] = useState(false);

  function toggleCapability(key: PermissionCapabilityKey) {
    setCapabilities((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleCreate() {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createPermissionProfile({ name: name.trim(), capabilities: [...capabilities] });
      setName("");
      setCapabilities(new Set());
      reload();
      showToast("Profil créé.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "La création a échoué.");
    } finally {
      setCreating(false);
    }
  }

  async function handleArchive(profile: PermissionProfile) {
    if (!window.confirm(`Archiver le profil « ${profile.name} » ? Plus personne n'en héritera des capacités.`)) return;
    try {
      await archivePermissionProfile(profile.id);
      reload();
      showToast("Profil archivé.");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "L'archivage a échoué.");
    }
  }

  // --- Assignation ---------------------------------------------------------
  const [assigningProfileId, setAssigningProfileId] = useState<string | null>(null);
  const [pickedUserId, setPickedUserId] = useState("");

  async function handleAssign(profile: PermissionProfile) {
    if (!pickedUserId) return;
    try {
      await assignPermissionProfile(profile.id, pickedUserId);
      setPickedUserId("");
      setAssigningProfileId(null);
      reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "L'assignation a échoué.");
    }
  }

  async function handleUnassign(profile: PermissionProfile, userId: string) {
    try {
      await unassignPermissionProfile(profile.id, userId);
      reload();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Le retrait a échoué.");
    }
  }

  return (
    <div className="profiles-section">
      <p className="profiles-section__intro">
        Accordent des capacités précises (ex. « gérer les intégrations ») sans le statut d'administrateur
        complet — s'ajoutent aux rôles existants, ne les remplacent jamais.
      </p>

      {error && <p className="profiles-section__error">{error}</p>}

      {profiles === null && (
        <div className="profiles-section__skeleton">
          <Skeleton height="60px" />
        </div>
      )}

      {profiles !== null && (
        <ul className="profiles-section__list">
          {profiles.map((profile) => (
            <li key={profile.id} className="profiles-section__card">
              <div className="profiles-section__card-header">
                <h3>
                  <ShieldCheck size={16} strokeWidth={1.75} aria-hidden="true" />
                  {profile.name}
                </h3>
                <button
                  type="button"
                  className="profiles-section__icon-btn"
                  onClick={() => handleArchive(profile)}
                  aria-label={`Archiver ${profile.name}`}
                >
                  <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </div>
              <div className="profiles-section__capabilities">
                {profile.capabilities.map((key) => (
                  <span key={key} className="profiles-section__capability-chip">
                    {CAPABILITY_OPTIONS.find((c) => c.key === key)?.label ?? key}
                  </span>
                ))}
                {profile.capabilities.length === 0 && (
                  <span className="profiles-section__hint">Aucune capacité — profil sans effet pour l'instant.</span>
                )}
              </div>

              <div className="profiles-section__assignees">
                <span className="profiles-section__assignees-label">Assigné à</span>
                <ul className="profiles-section__assignee-list">
                  {profile.assigned_users.map((u) => (
                    <li key={u.id} className="profiles-section__assignee">
                      {displayName(u)}
                      <button
                        type="button"
                        className="profiles-section__icon-btn"
                        onClick={() => handleUnassign(profile, u.id)}
                        aria-label={`Retirer ${displayName(u)}`}
                      >
                        <X size={12} strokeWidth={2} aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                  {profile.assigned_users.length === 0 && (
                    <li className="profiles-section__hint">Personne pour l'instant.</li>
                  )}
                </ul>

                {assigningProfileId === profile.id ? (
                  <div className="profiles-section__assign-row">
                    <Combobox
                      options={users
                        .filter((u) => !profile.assigned_users.some((au) => au.id === u.id))
                        .map((u) => ({ value: u.id, label: displayName(u) }))}
                      value={pickedUserId}
                      onChange={setPickedUserId}
                      placeholder="Choisir une personne"
                    />
                    <button
                      type="button"
                      className="profiles-section__btn profiles-section__btn--primary"
                      onClick={() => handleAssign(profile)}
                      disabled={!pickedUserId}
                    >
                      Ajouter
                    </button>
                    <button
                      type="button"
                      className="profiles-section__btn"
                      onClick={() => {
                        setAssigningProfileId(null);
                        setPickedUserId("");
                      }}
                    >
                      Annuler
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="profiles-section__btn"
                    onClick={() => setAssigningProfileId(profile.id)}
                  >
                    <UserPlus size={13} strokeWidth={1.75} aria-hidden="true" />
                    Assigner à quelqu'un
                  </button>
                )}
              </div>
            </li>
          ))}
          {profiles.length === 0 && <li className="profiles-section__hint">Aucun profil de droits pour l'instant.</li>}
        </ul>
      )}

      <section className="profiles-section__form">
        <h3>Créer un profil</h3>
        <label className="profiles-section__field">
          <span>Nom</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex. Intégrateur" />
        </label>
        <div className="profiles-section__field">
          <span>Capacités</span>
          <ul className="profiles-section__capability-picker">
            {CAPABILITY_OPTIONS.map((option) => (
              <li key={option.key}>
                <label className="profiles-section__switch-row">
                  <Checkbox
                    checked={capabilities.has(option.key)}
                    onCheckedChange={() => toggleCapability(option.key)}
                    aria-label={option.label}
                  />
                  <span>{option.label}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
        <div className="profiles-section__form-footer">
          <button
            type="button"
            className="profiles-section__btn profiles-section__btn--primary"
            onClick={handleCreate}
            disabled={creating || !name.trim()}
          >
            Créer le profil
          </button>
        </div>
      </section>
    </div>
  );
}
