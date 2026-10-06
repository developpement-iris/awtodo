import { Archive, ChevronDown, MessagesSquare, Plus, Send, Trash2, CheckCircle2, Clock, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  archiveProjectCommunicationChannel,
  composeProjectCommunicationMessage,
  createProjectCommunicationChannel,
  getIncidents,
  getProjectCommunicationChannels,
  getProjectCommunicationMessages,
  getTasks,
} from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import { Skeleton } from "../../components/Skeleton";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../context/ToastContext";
import type {
  CommunicationChannel,
  CommunicationDelivery,
  CommunicationMessage,
  CommunicationPayloadTemplate,
  Incident,
  Project,
  Task,
} from "../../types/watodo";
import { PAYLOAD_FIELD_CATALOG, placeholderFor } from "./payloadFields";
import "./CommunicationTab.css";

interface CommunicationTabProps {
  project: Project;
}

const STATUS_ICON: Record<CommunicationMessage["status"], typeof Clock> = {
  en_attente: Clock,
  envoye: CheckCircle2,
  echec: XCircle,
};

const STATUS_TONE: Record<CommunicationMessage["status"], "neutral" | "positive" | "priorityCritique"> = {
  en_attente: "neutral",
  envoye: "positive",
  echec: "priorityCritique",
};

const FIELD_OPTIONS = Object.entries(PAYLOAD_FIELD_CATALOG).flatMap(([namespace, fields]) =>
  fields.map((field) => ({ value: `${namespace}.${field}`, label: `${namespace} → ${field}` })),
);

// Miroir illustratif de `apps.communication.payload.DEFAULT_TEMPLATE` (valeurs
// d'exemple, pas une donnée réelle) — affiché tel quel dans le panneau d'aide
// pour configurer l'automation Power Automate sans avoir à décortiquer le
// code backend. À garder synchronisé si le gabarit par défaut change.
const DEFAULT_PAYLOAD_EXAMPLE = `{
  "subject": "Nouvelle version déployée",
  "body": "Le correctif XYZ est en production.",
  "project": "Traitement ARC Auto",
  "sender_name": "Ada Lovelace",
  "trigger": "manuel",
  "sent_at": "2026-10-06T14:32:00+02:00",
  "channel_id": "19:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@thread.tacv2",
  "channel_name": "SI / Correctifs / MAJ"
}`;

function displayName(user: { first_name: string; last_name: string; username: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

interface TemplateRow {
  key: string;
  value: string;
}

export function CommunicationTab({ project }: CommunicationTabProps) {
  const { showToast } = useToast();
  const canManage = project.permissions.can_manage_project_communication;
  const canSend = project.permissions.can_send_project_communication;

  const [channels, setChannels] = useState<CommunicationChannel[] | null>(null);
  const [messages, setMessages] = useState<CommunicationMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  function reload() {
    setReloadKey((k) => k + 1);
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

  // --- Canaux Teams ----------------------------------------------------
  const [channelLabel, setChannelLabel] = useState("");
  const [channelId, setChannelId] = useState("");
  const [channelName, setChannelName] = useState("");
  const [channelWebhook, setChannelWebhook] = useState("");
  const [channelNotifyIncident, setChannelNotifyIncident] = useState(false);
  const [channelBusy, setChannelBusy] = useState(false);

  // Gabarit de payload personnalisable (session du 2026-09-28) — vide par
  // défaut, le backend applique alors le payload standard (sujet/corps/…).
  const [templateOpen, setTemplateOpen] = useState(false);
  const [templateRows, setTemplateRows] = useState<TemplateRow[]>([]);

  function addTemplateRow() {
    setTemplateRows((rows) => [...rows, { key: "", value: "" }]);
  }

  function updateTemplateRow(index: number, patch: Partial<TemplateRow>) {
    setTemplateRows((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function removeTemplateRow(index: number) {
    setTemplateRows((rows) => rows.filter((_, i) => i !== index));
  }

  function insertFieldIntoRow(index: number, fieldPath: string) {
    if (!fieldPath) return;
    const [namespace, field] = fieldPath.split(".");
    updateTemplateRow(index, { value: templateRows[index].value + placeholderFor(namespace, field) });
  }

  const canCreateChannel =
    channelLabel.trim() && channelId.trim() && channelName.trim() && channelWebhook.trim();

  async function handleCreateChannel() {
    if (!canCreateChannel) return;
    setChannelBusy(true);
    setError(null);
    try {
      const payload_template: CommunicationPayloadTemplate = {};
      for (const row of templateRows) {
        if (row.key.trim()) payload_template[row.key.trim()] = row.value;
      }
      await createProjectCommunicationChannel(project.id, {
        label: channelLabel.trim(),
        teams_channel_id: channelId.trim(),
        teams_channel_name: channelName.trim(),
        teams_webhook_url: channelWebhook.trim(),
        payload_template,
        notify_incident_created: channelNotifyIncident,
      });
      setChannelLabel("");
      setChannelId("");
      setChannelName("");
      setChannelWebhook("");
      setChannelNotifyIncident(false);
      setTemplateRows([]);
      setTemplateOpen(false);
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

  // Tâche/incident du projet à joindre (optionnel) — rend leurs champs
  // disponibles au gabarit de payload d'un canal (`{{task.*}}`/`{{incident.*}}`).
  const [projectTasks, setProjectTasks] = useState<Task[]>([]);
  const [projectIncidents, setProjectIncidents] = useState<Incident[]>([]);
  const [attachedTaskId, setAttachedTaskId] = useState("");
  const [attachedIncidentId, setAttachedIncidentId] = useState("");

  useEffect(() => {
    if (!canSend) return;
    getTasks({ project: project.id }).then(setProjectTasks).catch(() => setProjectTasks([]));
    getIncidents({ project: project.id }).then(setProjectIncidents).catch(() => setProjectIncidents([]));
  }, [canSend, project.id]);

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
      const message = await composeProjectCommunicationMessage(project.id, {
        subject: subject.trim(),
        body: body.trim(),
        channel_ids: [...selectedChannelIds],
        task_id: attachedTaskId || undefined,
        incident_id: attachedIncidentId || undefined,
      });
      setSubject("");
      setBody("");
      setSelectedChannelIds(new Set());
      setAttachedTaskId("");
      setAttachedIncidentId("");
      reload();
      if (message.status === "envoye") {
        showToast("Message envoyé.");
      } else if (message.status === "echec") {
        const failed = message.deliveries.filter((d) => d.status === "echec").map((d) => d.channel_label);
        showToast(`Échec de l'envoi vers : ${failed.join(", ") || "un ou plusieurs canaux"}.`);
      } else {
        showToast("Message enregistré.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "L'envoi a échoué.");
    } finally {
      setComposeBusy(false);
    }
  }

  return (
    <div className="communication-tab">
      <p className="communication-tab__intro">
        Communiquez autour de ce projet vers un ou plusieurs canaux Teams, via un flow Power Automate déclenché
        sur l'URL du canal.
      </p>

      {error && <p className="communication-tab__error">{error}</p>}

      {/* --- Canaux ---------------------------------------------------- */}
      <div className="communication-tab__channels-row">
      <section className="communication-tab__section">
        <div className="communication-tab__section-header">
          <h3>
            <MessagesSquare size={16} strokeWidth={1.75} aria-hidden="true" />
            Canaux Teams du projet
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
                <MessagesSquare size={15} strokeWidth={1.75} aria-hidden="true" />
                <div className="communication-tab__channel-info">
                  <span className="communication-tab__channel-label">{channel.label}</span>
                  <span className="communication-tab__channel-target">
                    {channel.teams_channel_name || "Canal non renseigné"}
                    {channel.teams_channel_id ? ` · ${channel.teams_channel_id}` : ""}
                  </span>
                </div>
                {Object.keys(channel.payload_template ?? {}).length > 0 && (
                  <StatusBadge label="Payload personnalisé" tone="neutral" />
                )}
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
                <span>Libellé</span>
                <input
                  value={channelLabel}
                  onChange={(e) => setChannelLabel(e.target.value)}
                  placeholder="Ex. #suivi-projet"
                />
              </label>
              <label className="communication-tab__field">
                <span>Nom du canal Teams</span>
                <input
                  value={channelName}
                  onChange={(e) => setChannelName(e.target.value)}
                  placeholder="Ex. Suivi projet"
                />
              </label>
            </div>
            <label className="communication-tab__field">
              <span>ID du canal ou de la conversation Teams</span>
              <input
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                placeholder="19:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@thread.tacv2"
              />
              <span className="communication-tab__field-hint">
                Un canal d'équipe comme une conversation de groupe fonctionnent — l'identifiant est transmis tel
                quel à votre flow. Pour le récupérer : dans Teams, « Obtenir le lien » sur le canal/la conversation
                (clic droit), l'ID est le segment commençant par <code>19:</code> dans l'URL copiée.
              </span>
            </label>
            <label className="communication-tab__field">
              <span>URL de l'automation</span>
              <input
                type="url"
                value={channelWebhook}
                onChange={(e) => setChannelWebhook(e.target.value)}
                placeholder="https://prod-00.westeurope.logic.azure.com/…"
              />
            </label>
            <label className="communication-tab__switch-row">
              <Checkbox checked={channelNotifyIncident} onCheckedChange={setChannelNotifyIncident} aria-label="Notifier à la création d'un incident" />
              <span>Notifier automatiquement ce canal à la création d'un incident sur ce projet</span>
            </label>

            <div className="communication-tab__template">
              <button
                type="button"
                className="communication-tab__disclosure"
                onClick={() => setTemplateOpen((v) => !v)}
                aria-expanded={templateOpen}
              >
                <ChevronDown
                  size={13}
                  strokeWidth={1.75}
                  aria-hidden="true"
                  className={templateOpen ? "communication-tab__disclosure-icon communication-tab__disclosure-icon--open" : "communication-tab__disclosure-icon"}
                />
                Personnaliser le payload envoyé au flow (optionnel)
              </button>
              {templateOpen && (
                <div className="communication-tab__template-body">
                  <p className="communication-tab__hint">
                    Par défaut, le canal reçoit un payload standard (sujet, corps, projet…). Définissez vos
                    propres clés ci-dessous pour le remplacer entièrement — insérez un champ Awtodo ou tapez une
                    valeur fixe pour votre propre automatisation.
                  </p>
                  <div className="communication-tab__template-rows">
                    {templateRows.map((row, index) => (
                      <div key={index} className="communication-tab__template-row">
                        <input
                          className="communication-tab__template-key"
                          value={row.key}
                          onChange={(e) => updateTemplateRow(index, { key: e.target.value })}
                          placeholder="clé JSON"
                        />
                        <input
                          className="communication-tab__template-value"
                          value={row.value}
                          onChange={(e) => updateTemplateRow(index, { value: e.target.value })}
                          placeholder="valeur, ou {{message.subject}}"
                        />
                        <Combobox
                          options={FIELD_OPTIONS}
                          value=""
                          onChange={(v) => insertFieldIntoRow(index, v)}
                          placeholder="+ champ"
                          clearable={false}
                          panelWidth="auto"
                        />
                        <button
                          type="button"
                          className="communication-tab__icon-btn"
                          onClick={() => removeTemplateRow(index)}
                          aria-label="Retirer ce champ"
                        >
                          <Trash2 size={14} strokeWidth={1.75} aria-hidden="true" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <button type="button" className="communication-tab__btn" onClick={addTemplateRow}>
                    <Plus size={13} strokeWidth={1.75} aria-hidden="true" />
                    Ajouter un champ
                  </button>
                </div>
              )}
            </div>

            <div className="communication-tab__form-footer">
              <button
                type="button"
                className="communication-tab__btn communication-tab__btn--primary"
                onClick={handleCreateChannel}
                disabled={channelBusy || !canCreateChannel}
              >
                Ajouter le canal
              </button>
            </div>
          </div>
        )}
      </section>

      {canManage && (
        <aside className="communication-tab__payload-example">
          <h4>Payload envoyé à l'automation</h4>
          <p>
            Sans personnalisation, chaque canal reçoit exactement ce JSON (valeurs d'exemple ci-dessous) — à
            utiliser pour configurer l'action « Analyser JSON » de votre flow Power Automate, déclenché par
            « Quand une requête HTTP est reçue ».
          </p>
          <pre>
            <code>{DEFAULT_PAYLOAD_EXAMPLE}</code>
          </pre>
          <p>
            <code>trigger</code> vaut <code>manuel</code> (envoi depuis cet onglet) ou{" "}
            <code>incident_cree</code> (si la case « Notifier automatiquement... » est cochée ci-contre).
          </p>
          <p>
            En personnalisant le gabarit ci-contre, vos propres clés remplacent entièrement ce payload — le
            flow ne reçoit alors que ce que vous avez défini.
          </p>
        </aside>
      )}
      </div>

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
            <div className="communication-tab__form-row">
              <label className="communication-tab__field">
                <span>Tâche liée (optionnel)</span>
                <Combobox
                  options={projectTasks.map((t) => ({ value: t.id, label: t.title }))}
                  value={attachedTaskId}
                  onChange={setAttachedTaskId}
                  placeholder="Aucune"
                  clearable
                />
              </label>
              <label className="communication-tab__field">
                <span>Incident lié (optionnel)</span>
                <Combobox
                  options={projectIncidents.map((i) => ({ value: i.id, label: i.title }))}
                  value={attachedIncidentId}
                  onChange={setAttachedIncidentId}
                  placeholder="Aucun"
                  clearable
                />
              </label>
            </div>
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
              const Icon = STATUS_ICON[message.status];
              return (
                <li key={message.id} className="communication-tab__message">
                  <div className="communication-tab__message-header">
                    <span className="communication-tab__message-subject">{message.subject}</span>
                    <StatusBadge label={message.status_display} tone={STATUS_TONE[message.status]} icon={Icon} />
                  </div>
                  <p className="communication-tab__message-body">{message.body}</p>
                  <div className="communication-tab__message-meta">
                    <span>
                      {message.trigger_display}
                      {message.created_by && ` · ${displayName(message.created_by)}`}
                      {message.task_title && ` · tâche : ${message.task_title}`}
                      {message.incident_title && ` · incident : ${message.incident_title}`}
                    </span>
                  </div>
                  <ul className="communication-tab__delivery-list">
                    {message.deliveries.map((delivery: CommunicationDelivery) => {
                      const DeliveryIcon = STATUS_ICON[delivery.status];
                      return (
                        <li key={delivery.id} className="communication-tab__delivery">
                          <StatusBadge
                            label={`${delivery.channel_label} · ${delivery.status_display}`}
                            tone={STATUS_TONE[delivery.status]}
                            icon={DeliveryIcon}
                          />
                          {delivery.status === "echec" && delivery.response_detail && (
                            <span className="communication-tab__delivery-detail">{delivery.response_detail}</span>
                          )}
                        </li>
                      );
                    })}
                    {message.deliveries.length === 0 && (
                      <li className="communication-tab__empty">Aucun destinataire</li>
                    )}
                  </ul>
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
