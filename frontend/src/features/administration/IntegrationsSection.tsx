import { Check, Copy, KeyRound, Plug } from "lucide-react";
import { useEffect, useState } from "react";
import { generateApiKey, getApiKeys, getO365Connection, revokeApiKey, updateO365Connection } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { Skeleton } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../context/ToastContext";
import type { ApiKey, ApiKeyCreated, O365Connection } from "../../types/watodo";
import "./IntegrationsSection.css";

function formatDate(value: string): string {
  return new Date(value).toLocaleString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

export function IntegrationsSection() {
  const { showToast } = useToast();
  const [connection, setConnection] = useState<O365Connection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ tenant_id: "", client_id: "", client_secret: "" });
  const [busy, setBusy] = useState(false);

  const [apiKeys, setApiKeys] = useState<ApiKey[] | null>(null);
  const [apiKeysError, setApiKeysError] = useState<string | null>(null);
  const [creatingKey, setCreatingKey] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [keyBusy, setKeyBusy] = useState(false);
  const [revealedKey, setRevealedKey] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getO365Connection()
      .then(setConnection)
      .catch(() => setError("Impossible de charger la connexion Office 365."));
    getApiKeys()
      .then(setApiKeys)
      .catch(() => setApiKeysError("Impossible de charger les clés API."));
  }, []);

  async function handleGenerateKey() {
    if (!newKeyName.trim()) return;
    setKeyBusy(true);
    setApiKeysError(null);
    try {
      const created = await generateApiKey(newKeyName.trim());
      setApiKeys((current) => (current ? [created, ...current] : [created]));
      setRevealedKey(created);
      setCreatingKey(false);
      setNewKeyName("");
    } catch (err) {
      setApiKeysError(err instanceof Error ? err.message : "La génération a échoué.");
    } finally {
      setKeyBusy(false);
    }
  }

  async function handleRevokeKey(apiKey: ApiKey) {
    if (!window.confirm(`Révoquer la clé « ${apiKey.name} » ? Tout système qui l'utilise perdra l'accès immédiatement.`)) {
      return;
    }
    setKeyBusy(true);
    try {
      const revoked = await revokeApiKey(apiKey.id);
      setApiKeys((current) => (current ? current.map((k) => (k.id === revoked.id ? revoked : k)) : current));
    } catch (err) {
      setApiKeysError(err instanceof Error ? err.message : "La révocation a échoué.");
    } finally {
      setKeyBusy(false);
    }
  }

  async function handleCopyKey() {
    if (!revealedKey) return;
    try {
      await navigator.clipboard.writeText(revealedKey.key);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      showToast("Impossible de copier automatiquement — sélectionnez la clé manuellement.");
    }
  }

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

      <section className="integrations-section__card">
        <div className="integrations-section__header">
          <h3>
            <KeyRound size={16} strokeWidth={1.75} aria-hidden="true" />
            Clés API
          </h3>
          {!creatingKey && (
            <button type="button" className="integrations-section__btn" onClick={() => setCreatingKey(true)}>
              Générer une clé
            </button>
          )}
        </div>

        <p className="integrations-section__intro">
          Pour connecter un système externe (outil de ticketing, Power Automate…) sans compte Awtodo
          personnel. Valable en production, indépendamment de l'hébergement — seule l'URL de base change
          en cas de migration, jamais cette clé. Une clé générée agit avec les mêmes droits que le
          contournement déjà en place pour la création automatique d'incidents.
        </p>

        {apiKeysError && <p className="integrations-section__error">{apiKeysError}</p>}

        {!apiKeys && !apiKeysError && (
          <div className="integrations-section__skeleton">
            <Skeleton height="20px" />
          </div>
        )}

        {apiKeys && apiKeys.length === 0 && !creatingKey && (
          <p className="integrations-section__intro">
            Aucune clé générée pour l'instant.
          </p>
        )}

        {apiKeys && apiKeys.length > 0 && (
          <ul className="integrations-section__key-list">
            {apiKeys.map((apiKey) => (
              <li key={apiKey.id} className="integrations-section__key-row">
                <div className="integrations-section__key-info">
                  <span className="integrations-section__key-name">{apiKey.name}</span>
                  <span className="integrations-section__key-meta">
                    {apiKey.key_prefix}… · créée le {formatDate(apiKey.created_at)}
                    {apiKey.last_used_at && <> · dernier appel {formatDate(apiKey.last_used_at)}</>}
                  </span>
                </div>
                <StatusBadge
                  label={apiKey.is_active ? "Active" : "Révoquée"}
                  tone={apiKey.is_active ? "positive" : "neutral"}
                />
                {apiKey.is_active && (
                  <button
                    type="button"
                    className="integrations-section__btn"
                    onClick={() => void handleRevokeKey(apiKey)}
                    disabled={keyBusy}
                  >
                    Révoquer
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        {creatingKey && (
          <div className="integrations-section__form">
            <label className="integrations-section__field">
              <span>Nom (pour la reconnaître dans la liste)</span>
              <input
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="ex. GLPI — production"
                autoFocus
              />
            </label>
            <div className="integrations-section__form-footer">
              <button
                type="button"
                className="integrations-section__btn"
                onClick={() => {
                  setCreatingKey(false);
                  setNewKeyName("");
                }}
                disabled={keyBusy}
              >
                Annuler
              </button>
              <button
                type="button"
                className="integrations-section__btn integrations-section__btn--primary"
                onClick={() => void handleGenerateKey()}
                disabled={keyBusy || !newKeyName.trim()}
              >
                Générer
              </button>
            </div>
          </div>
        )}
      </section>

      {revealedKey && (
        <div className="integrations-section__reveal-overlay" onClick={() => setRevealedKey(null)}>
          <div className="integrations-section__reveal" onClick={(e) => e.stopPropagation()}>
            <h3>Clé générée — « {revealedKey.name} »</h3>
            <p>
              Copiez-la maintenant : elle ne sera plus jamais affichée en clair, seule une révocation
              sera possible ensuite.
            </p>
            <div className="integrations-section__reveal-value">
              <code>{revealedKey.key}</code>
              <button type="button" onClick={() => void handleCopyKey()} aria-label="Copier la clé">
                {copied ? <Check size={15} strokeWidth={2} aria-hidden="true" /> : <Copy size={15} strokeWidth={1.75} aria-hidden="true" />}
              </button>
            </div>
            <button
              type="button"
              className="integrations-section__btn integrations-section__btn--primary"
              onClick={() => setRevealedKey(null)}
            >
              J'ai copié la clé
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
