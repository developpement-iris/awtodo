import { Archive, CheckCircle2, Clock, Mail, MessagesSquare, Plug, Send, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  archiveProjectCommunicationChannel,
  composeProjectCommunicationMessage,
  createProjectCommunicationChannel,
  getO365Connection,
  getProjectCommunicationChannels,
  getProjectCommunicationMessages,
  updateO365Connection,
} from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import { Skeleton } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import type { CommunicationChannel, CommunicationChannelType, CommunicationMessage, O365Connection, Project } from "../../types/watodo";
import "./CommunicationTab.css";

interface CommunicationTabProps {
  project: Project;
}

const CHANNEL_TYPE_OPTIONS: { value: CommunicationChannelType; label: string }[] = [
  { value: "email", label: "Adresse mail" },
  { value: "teams", label: "Canal Teams" },
];

const MESSAGE_STATUS_ICON: Record<CommunicationMessage["status"], typeof Clock> = {
  en_attente: Clock,
  envoye: CheckCircle2,
  echec: XCircle,
};

function displayName(user: { first_name: string; last_name: string; username: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function CommunicationTab({ project }: CommunicationTabProps) {
  const { currentUser } = useCurrentUser();
  const { showToast } = useToast();
  const canManage = project.permissions.can_manage_project_communication;
  const canSend = project.permissions.can_send_project_communication;
  const isOrgAdmin = Boolean(currentUser?.is_platform_admin || currentUser?.organisation_role === "admin");

  const [connection, setConnection] = useState<O365Connection | null>(null);
  const [channels, setChannels] = useState<CommunicationChannel[] | null>(null);
  const [messages, setMessages] = useState<CommunicationMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  function reload() {
    setReloadKey((k) => k + 1);
  }

  useEffect(() => {
    getO365Connection()
      .then(setConnection)
      .catch(() => undefined);
  }, [reloadKey]);

  // --- Boîte expéditrice (admin d'organisation) --------------------------
  // Rattachée au même O365Connection organisation-scoped que la connexion
  // Graph elle-même (voir Administration > Intégrations pour tenant/client/
  // secret) — champ affiché/édité ici plutôt que là-bas car c'est la seule
  // donnée de la connexion qui varie d'un usage à l'autre (remonté
  // directement). ⚠️ Limite assumée : le modèle ne porte qu'une seule
  // valeur pour toute l'organisation, pas encore une par projet — une vraie
  // boîte par projet nécessiterait sa propre autorisation d'envoi (permission
  // "Send As"/"Send on Behalf" par boîte), en attente, chantier Communication
  // plus large, non traité ici.
  const [senderEditing, setSenderEditing] = useState(false);
  const [senderMailbox, setSenderMailbox] = useState("");
  const [senderBusy, setSenderBusy] = useState(false);

  function startSenderEdit() {
    setSenderMailbox(connection?.sender_mailbox ?? "");
    setSenderEditing(true);
  }

  async function handleSaveSender() {
    setSenderBusy(true);
    setError(null);
    try {
      setConnection(await updateO365Connection({ sender_mailbox: senderMailbox.trim() }));
      setSenderEditing(false);
      showToast("Boîte expéditrice mise à jour.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de la mise à jour.");
    } finally {
      setSenderBusy(false);
    }
  }

  useEffect(() => {
    getProjectCommunicationChannels(project.id)
      .then(setChannels)
      .catch(() => setChannels([]));
    getProjectCommunicationMessages(project.id)
      .then(setMessages)
      .catch(() => setMessages([]));
  }, [project.id, reloadKey]);

  const activeChannels = useMemo(() => (channels ?? []).filter((c) => c.status === "active"), [channels]);

  // --- Canaux --------------------------------------------------------
  const [channelType, setChannelType] = useState<CommunicationChannelType>("email");
  const [channelLabel, setChannelLabel] = useState("");
  const [channelTarget, setChannelTarget] = useState("");
  const [channelNotifyIncident, setChannelNotifyIncident] = useState(false);
  const [channelBusy, setChannelBusy] = useState(false);

  async function handleCreateChannel() {
    if (!channelLabel.trim() || !channelTarget.trim()) return;
    setChannelBusy(true);
    setError(null);
    try {
      await createProjectCommunicationChannel(project.id, {
        channel_type: channelType,
        label: channelLabel.trim(),
        email: channelType === "email" ? channelTarget.trim() : undefined,
        teams_webhook_url: channelType === "teams" ? channelTarget.trim() : undefined,
        notify_incident_created: channelNotifyIncident,
      });
      setChannelLabel("");
      setChannelTarget("");
      setChannelNotifyIncident(false);
      reload();
      showToast("Canal ajouté.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'ajout a échoué.");
    } finally {
      setChannelBusy(false);
    }
  }

  async function handleArchiveChannel(channel: CommunicationChannel) {
    try {
      await archiveProjectCommunicationChannel(project.id, channel.id);
      reload();
      showToast("Canal archivé.");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Échec de l'archivage.");
    }
  }

  // --- Rédaction -------------------------------------------------------
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [selectedChannelIds, setSelectedChannelIds] = useState<Set<string>>(new Set());
  const [composeBusy, setComposeBusy] = useState(false);

  function toggleChannelSelection(id: string) {
    setSelectedChannelIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleCompose() {
    if (!subject.trim() || !body.trim() || selectedChannelIds.size === 0) return;
    setComposeBusy(true);
    setError(null);
    try {
      await composeProjectCommunicationMessage(project.id, {
        subject: subject.trim(),
        body: body.trim(),
        channel_ids: [...selectedChannelIds],
      });
      setSubject("");
      setBody("");
      setSelectedChannelIds(new Set());
      reload();
      showToast("Message enregistré — l'envoi réel sera activé après le déploiement.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'enregistrement a échoué.");
    } finally {
      setComposeBusy(false);
    }
  }

  return (
    <div className="communication-tab">
      <p className="communication-tab__intro">
        Communiquez autour de ce projet par mail ou vers un canal Teams. Cette connexion Office 365 est aussi
        celle utilisée par la synchronisation Outlook du planning (voir « Mon planning »). L'envoi de mails et
        de messages Teams reste en attente ici, câblage prévu au déploiement.
      </p>

      {error && <p className="communication-tab__error">{error}</p>}

      {/* --- Connexion Office 365 (lecture seule — configuration dans
          Administration > Intégrations, réservée à un admin d'organisation) */}
      <section className="communication-tab__section communication-tab__section--compact">
        <div className="communication-tab__section-header">
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
        {!connection && (
          <div className="communication-tab__skeleton">
            <Skeleton height="16px" />
          </div>
        )}
        {connection && (
          <>
            <p className="communication-tab__hint">
              Identifiants Microsoft Graph gérés depuis Administration &gt; Intégrations (réservé à un
              administrateur d'organisation). La boîte expéditrice ci-dessous se configure ici, par projet.
            </p>
            <div className="communication-tab__sender-row">
              <span className="communication-tab__sender-label">Boîte expéditrice</span>
              {!senderEditing && (
                <>
                  <span className="communication-tab__sender-value">{connection.sender_mailbox || "—"}</span>
                  {isOrgAdmin && (
                    <button type="button" className="communication-tab__btn" onClick={startSenderEdit}>
                      Modifier
                    </button>
                  )}
                </>
              )}
              {senderEditing && (
                <>
                  <input
                    type="email"
                    className="communication-tab__sender-input"
                    value={senderMailbox}
                    onChange={(e) => setSenderMailbox(e.target.value)}
                    placeholder="equipe@reparstores.com"
                  />
                  <button type="button" className="communication-tab__btn" onClick={() => setSenderEditing(false)} disabled={senderBusy}>
                    Annuler
                  </button>
                  <button
                    type="button"
                    className="communication-tab__btn communication-tab__btn--primary"
                    onClick={handleSaveSender}
                    disabled={senderBusy}
                  >
                    Enregistrer
                  </button>
                </>
              )}
            </div>
          </>
        )}
      </section>

      {/* --- Canaux ---------------------------------------------------- */}
      <section className="communication-tab__section">
        <div className="communication-tab__section-header">
          <h3>
            <MessagesSquare size={16} strokeWidth={1.75} aria-hidden="true" />
            Canaux du projet
          </h3>
        </div>

        {channels === null && (
          <div className="communication-tab__skeleton">
            <Skeleton height="36px" />
            <Skeleton height="36px" />
          </div>
        )}

        {channels !== null && (
          <ul className="communication-tab__channel-list">
            {activeChannels.map((channel) => (
              <li key={channel.id} className="communication-tab__channel">
                {channel.channel_type === "email" ? (
                  <Mail size={15} strokeWidth={1.75} aria-hidden="true" />
                ) : (
                  <MessagesSquare size={15} strokeWidth={1.75} aria-hidden="true" />
                )}
                <div className="communication-tab__channel-info">
                  <span className="communication-tab__channel-label">{channel.label}</span>
                  <span className="communication-tab__channel-target">
                    {channel.channel_type === "email" ? channel.email : channel.teams_webhook_url || "Webhook non renseigné"}
                  </span>
                </div>
                {channel.notify_incident_created && (
                  <StatusBadge label="Auto à la création d'incident" tone="neutral" />
                )}
                {canManage && (
                  <button
                    type="button"
                    className="communication-tab__icon-btn"
                    onClick={() => handleArchiveChannel(channel)}
                    aria-label={`Archiver ${channel.label}`}
                  >
                    <Archive size={14} strokeWidth={1.75} aria-hidden="true" />
                  </button>
                )}
              </li>
            ))}
            {activeChannels.length === 0 && <li className="communication-tab__empty">Aucun canal configuré.</li>}
          </ul>
        )}

        {canManage && (
          <div className="communication-tab__form">
            <div className="communication-tab__form-row">
              <label className="communication-tab__field">
                <span>Type</span>
                <Combobox
                  options={CHANNEL_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                  value={channelType}
                  onChange={(v) => {
                    setChannelType(v as CommunicationChannelType);
                    setChannelTarget("");
                  }}
                  clearable={false}
                />
              </label>
              <label className="communication-tab__field">
                <span>Libellé</span>
                <input
                  value={channelLabel}
                  onChange={(e) => setChannelLabel(e.target.value)}
                  placeholder={channelType === "email" ? "Ex. Support client" : "Ex. #suivi-projet"}
                />
              </label>
            </div>
            <label className="communication-tab__field">
              <span>{channelType === "email" ? "Adresse mail" : "URL du flux Power Automate"}</span>
              <input
                type={channelType === "email" ? "email" : "url"}
                value={channelTarget}
                onChange={(e) => setChannelTarget(e.target.value)}
                placeholder={channelType === "email" ? "equipe@reparstores.com" : "https://prod-00.westeurope.logic.azure.com/…"}
              />
            </label>
            <label className="communication-tab__switch-row">
              <Checkbox checked={channelNotifyIncident} onCheckedChange={setChannelNotifyIncident} aria-label="Notifier à la création d'un incident" />
              <span>Notifier automatiquement ce canal à la création d'un incident sur ce projet</span>
            </label>
            <div className="communication-tab__form-footer">
              <button
                type="button"
                className="communication-tab__btn communication-tab__btn--primary"
                onClick={handleCreateChannel}
                disabled={channelBusy || !channelLabel.trim() || !channelTarget.trim()}
              >
                Ajouter le canal
              </button>
            </div>
          </div>
        )}
      </section>

      {/* --- Rédaction + historique ------------------------------------ */}
      <section className="communication-tab__section">
        <div className="communication-tab__section-header">
          <h3>
            <Send size={16} strokeWidth={1.75} aria-hidden="true" />
            Communications
          </h3>
        </div>

        {canSend && (
          <div className="communication-tab__form">
            <label className="communication-tab__field">
              <span>Objet</span>
              <input value={subject} onChange={(e) => setSubject(e.target.value)} />
            </label>
            <label className="communication-tab__field">
              <span>Message</span>
              <textarea rows={4} value={body} onChange={(e) => setBody(e.target.value)} />
            </label>
            <div className="communication-tab__field">
              <span>Destinataires</span>
              {activeChannels.length === 0 && (
                <p className="communication-tab__hint">Configurez au moins un canal ci-dessus pour pouvoir envoyer.</p>
              )}
              <ul className="communication-tab__recipient-list">
                {activeChannels.map((channel) => (
                  <li key={channel.id}>
                    <label className="communication-tab__switch-row">
                      <Checkbox
                        checked={selectedChannelIds.has(channel.id)}
                        onCheckedChange={() => toggleChannelSelection(channel.id)}
                        aria-label={channel.label}
                      />
                      <span>{channel.label}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
            <div className="communication-tab__form-footer">
              <button
                type="button"
                className="communication-tab__btn communication-tab__btn--primary"
                onClick={handleCompose}
                disabled={composeBusy || !subject.trim() || !body.trim() || selectedChannelIds.size === 0}
              >
                Envoyer
              </button>
            </div>
          </div>
        )}

        <h4 className="communication-tab__history-title">Historique</h4>
        {messages === null && (
          <div className="communication-tab__skeleton">
            <Skeleton height="48px" />
          </div>
        )}
        {messages !== null && (
          <ul className="communication-tab__message-list">
            {messages.map((message) => {
              const Icon = MESSAGE_STATUS_ICON[message.status];
              return (
                <li key={message.id} className="communication-tab__message">
                  <div className="communication-tab__message-header">
                    <span className="communication-tab__message-subject">{message.subject}</span>
                    <StatusBadge label={message.status_display} tone="neutral" icon={Icon} />
                  </div>
                  <p className="communication-tab__message-body">{message.body}</p>
                  <div className="communication-tab__message-meta">
                    <span>
                      {message.trigger_display}
                      {message.created_by && ` · ${displayName(message.created_by)}`}
                    </span>
                    <span>{message.channels.map((c) => c.label).join(", ") || "Aucun destinataire"}</span>
                  </div>
                </li>
              );
            })}
            {messages.length === 0 && <li className="communication-tab__empty">Aucune communication pour l'instant.</li>}
          </ul>
        )}
      </section>
    </div>
  );
}
