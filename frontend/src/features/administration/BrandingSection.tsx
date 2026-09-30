import { Palette } from "lucide-react";
import { useEffect, useState } from "react";
import { getOrganisationBranding, updateOrganisationBranding } from "../../api/client";
import { useCurrentUser } from "../../context/CurrentUserContext";
import type { OrganisationBranding } from "../../types/watodo";
import "./BrandingSection.css";

const DEFAULT_PRIMARY = "#F5EFEC";
const DEFAULT_SECONDARY = "#753030";

export function BrandingSection() {
  const { refreshBranding } = useCurrentUser();
  const [branding, setBranding] = useState<OrganisationBranding | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getOrganisationBranding()
      .then(setBranding)
      .catch(() => setError("Impossible de charger les couleurs de marque."));
  }, []);

  async function handleChange(field: "primary_color" | "secondary_color", value: string) {
    setBusy(true);
    setError(null);
    try {
      setBranding(await updateOrganisationBranding({ [field]: value }));
      await refreshBranding();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de la mise à jour.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="branding-section">
      <p className="branding-section__intro">
        Couleurs de marque pour toute l'organisation — remplacent la charte graphique par défaut pour tous les
        utilisateurs.
      </p>

      {error && <p className="branding-section__error">{error}</p>}

      <section className="branding-section__card">
        <div className="branding-section__header">
          <h3>
            <Palette size={16} strokeWidth={1.75} aria-hidden="true" />
            Couleurs
          </h3>
        </div>

        {!branding && !error && <p className="branding-section__hint">Chargement…</p>}

        {branding && (
          <div className="branding-section__rows">
            <div className="branding-section__row">
              <label className="branding-section__color-label">
                <input
                  type="color"
                  value={branding.brand_primary_color || DEFAULT_PRIMARY}
                  onChange={(e) => void handleChange("primary_color", e.target.value)}
                  disabled={busy}
                  aria-label="Couleur principale"
                  className="branding-section__color-input"
                />
              </label>
              <span className="branding-section__row-label">
                Couleur principale
                <span className="branding-section__hint">
                  Fond et surfaces de l'application (remplace le neutre clair/sombre par défaut).
                </span>
              </span>
              {branding.brand_primary_color && (
                <button
                  type="button"
                  className="branding-section__btn"
                  onClick={() => void handleChange("primary_color", "")}
                  disabled={busy}
                >
                  Par défaut
                </button>
              )}
            </div>

            <div className="branding-section__row">
              <label className="branding-section__color-label">
                <input
                  type="color"
                  value={branding.brand_secondary_color || DEFAULT_SECONDARY}
                  onChange={(e) => void handleChange("secondary_color", e.target.value)}
                  disabled={busy}
                  aria-label="Couleur secondaire"
                  className="branding-section__color-input"
                />
              </label>
              <span className="branding-section__row-label">
                Couleur secondaire
                <span className="branding-section__hint">
                  Bande de marque (onglets, menu latéral) et boutons d'accent.
                </span>
              </span>
              {branding.brand_secondary_color && (
                <button
                  type="button"
                  className="branding-section__btn"
                  onClick={() => void handleChange("secondary_color", "")}
                  disabled={busy}
                >
                  Par défaut
                </button>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
