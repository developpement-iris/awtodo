import { Plug } from "lucide-react";
import { useEffect, useState } from "react";
import { getO365Connection, updateO365Connection } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { Skeleton } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../context/ToastContext";
import type { O365Connection } from "../../types/watodo";
import "./IntegrationsSection.css";

export function IntegrationsSection() {
  const { showToast } = useToast();
  const [connection, setConnection] = useState<O365Connection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ tenant_id: "", client_id: "", client_secret: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getO365Connection()
      .then(setConnection)
      .catch(() => setError("Impossible de charger la connexion Office 365."));
  }, []);

  function startEdit() {
    if (!connection) return;
    setForm({
      tenant_id: connection.tenant_id,
      client_id: connection.client_id,
      client_secret: "",
    });
    setEditing(true);
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, string> = { ...form };
      if (!payload.client_secret) delete payload.client_secret; // ne pas écraser un secret déjà saisi
      setConnection(await updateO365Connection(payload));
      setEditing(false);
      showToast("Connexion Office 365 mise à jour.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de la mise à jour.");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggle(enabled: boolean) {
    try {
      setConnection(await updateO365Connection({ is_enabled: enabled }));
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Échec de la mise à jour.");
    }
  }

  return (
    <div className="integrations-section">
      <p className="integrations-section__intro">
        Identifiants Microsoft Graph (tenant, application, secret) pour toute l'organisation — sert à
        la synchronisation Outlook du planning (« Mon planning ») et, plus tard, à l'envoi de
        mails/Teams (module Communication). Réservé à un administrateur d'organisation. La boîte
        expéditrice pour les mails se configure par projet, dans l'onglet Communication.
      </p>

      {error && <p className="integrations-section__error">{error}</p>}

      <section className="integrations-section__card">
        <div className="integrations-section__header">
          <h3>
            <Plug size={16} strokeWidth={1.75} aria-hidden="true" />
            Connexion Office 365
          </h3>
          {connection && (
            <StatusBadge
              label={connection.is_configured ? "Configurée" : "Non configurée"}
              tone={connection.is_configured ? "positive" : "neutral"}
            />
          )}
        </div>

        {!connection && !error && (
          <div className="integrations-section__skeleton">
            <Skeleton height="20px" />
          </div>
        )}

        {connection && !editing && (
          <div className="integrations-section__summary">
            <dl>
              <div>
                <dt>Tenant ID</dt>
                <dd>{connection.tenant_id || "—"}</dd>
              </div>
              <div>
                <dt>Client ID</dt>
                <dd>{connection.client_id || "—"}</dd>
              </div>
              <div>
                <dt>Secret</dt>
                <dd>{connection.has_client_secret ? "•••••••• (enregistré)" : "—"}</dd>
              </div>
            </dl>
            <div className="integrations-section__actions">
              <label className="integrations-section__switch-row">
                <Checkbox checked={connection.is_enabled} onCheckedChange={handleToggle} aria-label="Activer la connexion" />
                <span>Activée</span>
              </label>
              <button type="button" className="integrations-section__btn" onClick={startEdit}>
                Modifier
              </button>
            </div>
          </div>
        )}

        {connection && editing && (
          <div className="integrations-section__form">
            <div className="integrations-section__form-row">
              <label className="integrations-section__field">
                <span>Tenant ID</span>
                <input value={form.tenant_id} onChange={(e) => setForm((f) => ({ ...f, tenant_id: e.target.value }))} />
              </label>
              <label className="integrations-section__field">
                <span>Client ID</span>
                <input value={form.client_id} onChange={(e) => setForm((f) => ({ ...f, client_id: e.target.value }))} />
              </label>
            </div>
            <label className="integrations-section__field">
              <span>Client secret</span>
              <input
                type="password"
                placeholder={connection.has_client_secret ? "Laisser vide pour conserver l'actuel" : ""}
                value={form.client_secret}
                onChange={(e) => setForm((f) => ({ ...f, client_secret: e.target.value }))}
              />
            </label>
            <div className="integrations-section__form-footer">
              <button type="button" className="integrations-section__btn" onClick={() => setEditing(false)} disabled={busy}>
                Annuler
              </button>
              <button
                type="button"
                className="integrations-section__btn integrations-section__btn--primary"
                onClick={handleSave}
                disabled={busy}
              >
                Enregistrer
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
