import { Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createCalendarShare, listCalendarShares, revokeCalendarShare } from "../../api/client";
import { Combobox, type ComboboxOption } from "../../components/Combobox";
import { useCurrentUser } from "../../context/CurrentUserContext";
import type { CalendarShareList } from "../../types/watodo";

interface SharePanelProps {
  onClose: () => void;
  onChanged: () => void;
}

function displayName(user: { first_name: string; last_name: string; username: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function SharePanel({ onClose, onChanged }: SharePanelProps) {
  const { users, currentUser } = useCurrentUser();
  const [shares, setShares] = useState<CalendarShareList | null>(null);
  const [granteeId, setGranteeId] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reload() {
    listCalendarShares()
      .then(setShares)
      .catch(() => setError("Impossible de charger les partages."));
  }

  useEffect(reload, []);

  async function handleShare() {
    if (!granteeId) return;
    setError(null);
    try {
      await createCalendarShare(granteeId);
      setGranteeId("");
      reload();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Partage impossible.");
    }
  }

  async function handleRevoke(shareId: string) {
    try {
      await revokeCalendarShare(shareId);
      reload();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Révocation impossible.");
    }
  }

  // Le partage n'est lié à aucun groupe ni type de compte : on peut partager
  // son calendrier avec n'importe quel utilisateur du site (interne ou externe
  // invité sur un projet), pas seulement les membres de ses groupes.
  const options = useMemo<ComboboxOption[]>(() => {
    const alreadyGranted = new Set((shares?.granted ?? []).map((s) => s.grantee.id));
    return users
      .filter((u) => u.id !== currentUser?.id && !alreadyGranted.has(u.id))
      .map((u) => ({
        value: u.id,
        label: displayName(u),
        hint: u.account_status === "pending" ? "invitation en attente" : undefined,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "fr"));
  }, [users, currentUser?.id, shares?.granted]);

  return (
    <div className="planning-dialog__overlay" onClick={onClose}>
      <div
        className="planning-dialog planning-dialog--narrow planning-dialog--overflow-visible"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
      >
        <div className="planning-dialog__header">
          <h2>Partage de calendrier</h2>
          <button type="button" className="planning-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {error && <p className="planning-dialog__error">{error}</p>}

        <div className="planning-dialog__body">
          <section className="share-panel__section">
            <h3>Je partage mon calendrier avec</h3>
            <div className="planning-field-row planning-field-row--combobox">
              <Combobox
                options={options}
                value={granteeId}
                onChange={setGranteeId}
                placeholder="Choisir une personne…"
                searchPlaceholder="Rechercher un nom…"
                emptyLabel="Aucune personne à qui partager."
              />
              <button type="button" className="planning-btn planning-btn--primary" onClick={handleShare} disabled={!granteeId}>
                Partager
              </button>
            </div>
            <ul className="share-panel__list">
              {(shares?.granted ?? []).map((s) => (
                <li key={s.id}>
                  <span>{displayName(s.grantee)}</span>
                  <button type="button" onClick={() => handleRevoke(s.id)} aria-label="Révoquer">
                    <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                  </button>
                </li>
              ))}
              {shares?.granted.length === 0 && <li className="planning-dialog__muted">Personne pour l'instant</li>}
            </ul>
          </section>

          <section className="share-panel__section">
            <h3>Calendriers partagés avec moi</h3>
            <ul className="share-panel__list">
              {(shares?.received ?? []).map((s) => (
                <li key={s.id}>
                  <span>{displayName(s.owner)}</span>
                  <button type="button" onClick={() => handleRevoke(s.id)} aria-label="Ne plus afficher">
                    <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                  </button>
                </li>
              ))}
              {shares?.received.length === 0 && <li className="planning-dialog__muted">Aucun</li>}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
