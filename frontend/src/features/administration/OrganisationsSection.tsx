import { useEffect, useState } from "react";
import { createOrganisation, getOrganisations } from "../../api/client";
import { SkeletonTable } from "../../components/Skeleton";
import { useToast } from "../../context/ToastContext";
import type { Organisation } from "../../types/watodo";
import "./OrganisationsSection.css";

export function OrganisationsSection() {
  const { showToast } = useToast();
  const [organisations, setOrganisations] = useState<Organisation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [organisationName, setOrganisationName] = useState("");
  const [adminName, setAdminName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    getOrganisations()
      .then(setOrganisations)
      .catch(() => setError("Impossible de charger les organisations."));
  }, []);

  async function handleCreate() {
    setSubmitting(true);
    setCreateError(null);
    try {
      const result = await createOrganisation({
        organisation_name: organisationName.trim(),
        admin_name: adminName.trim(),
        admin_email: adminEmail.trim(),
      });
      setOrganisations((current) => (current ? [...current, result] : current));
      setCreating(false);
      setOrganisationName("");
      setAdminName("");
      setAdminEmail("");
      showToast(`Organisation créée (admin : ${result.admin.username}).`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "La création a échoué.");
    } finally {
      setSubmitting(false);
    }
  }

  const isValid = organisationName.trim() && adminName.trim() && adminEmail.trim();

  return (
    <div className="organisations-section">
      {error && <p className="organisations-section__message organisations-section__message--error">{error}</p>}
      {organisations === null && !error && <SkeletonTable columns={2} rows={3} />}

      {organisations !== null && (
        <table className="organisations-section__table">
          <thead>
            <tr>
              <th>Organisation</th>
              <th>Créée le</th>
            </tr>
          </thead>
          <tbody>
            {organisations.map((org) => (
              <tr key={org.id}>
                <td>{org.name}</td>
                <td>{new Date(org.created_at).toLocaleDateString("fr-FR")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {creating ? (
        <div className="organisations-section__form">
          <h3>Nouvelle organisation</h3>
          <label>
            <span>Nom de l'organisation</span>
            <input value={organisationName} onChange={(event) => setOrganisationName(event.target.value)} autoFocus />
          </label>
          <label>
            <span>Nom du premier administrateur</span>
            <input value={adminName} onChange={(event) => setAdminName(event.target.value)} />
          </label>
          <label>
            <span>Email du premier administrateur</span>
            <input type="email" value={adminEmail} onChange={(event) => setAdminEmail(event.target.value)} />
          </label>
          {createError && <p className="organisations-section__message organisations-section__message--error">{createError}</p>}
          <div className="organisations-section__form-actions">
            <button type="button" onClick={() => setCreating(false)} disabled={submitting}>
              Annuler
            </button>
            <button type="button" onClick={handleCreate} disabled={!isValid || submitting}>
              {submitting ? "Création…" : "Créer l'organisation"}
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="organisations-section__create-trigger" onClick={() => setCreating(true)}>
          Créer une organisation
        </button>
      )}
    </div>
  );
}
