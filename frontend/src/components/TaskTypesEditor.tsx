import { Archive, ChevronDown, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  archiveTaskType,
  createTaskType,
  getTaskTypes,
  restoreTaskType,
  updateTaskTypeDefinition,
  type TaskTypeScope,
} from "../api/client";
import { useToast } from "../context/ToastContext";
import { invalidateTaskTypes } from "../hooks/useTaskTypes";
import { TASK_TYPE_ICON_KEYS, TASK_TYPE_ICONS } from "../lib/taskTypeIcons";
import type { TaskType, TaskTypeIcon, TaskTypeList } from "../types/watodo";
import { AnchoredPanel } from "./AnchoredPanel";
import { InlineEditableText } from "./InlineEditableText";
import { TypeBadge } from "./TypeBadge";
import "./TaskTypesEditor.css";

function IconPicker({
  value,
  onChange,
  disabled,
}: {
  value: TaskTypeIcon;
  onChange: (icon: TaskTypeIcon) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const Current = TASK_TYPE_ICONS[value];

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        className="task-types-editor__icon-trigger"
        onClick={() => setOpen((current) => !current)}
        disabled={disabled}
        aria-label="Choisir une icône"
        aria-expanded={open}
      >
        <Current size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {open && (
        <AnchoredPanel
          anchorRef={anchorRef}
          onClose={() => setOpen(false)}
          width="auto"
          className="task-types-editor__icon-panel"
        >
          <div className="task-types-editor__icon-grid" role="listbox" aria-label="Icônes">
            {TASK_TYPE_ICON_KEYS.map((key) => {
              const Icon = TASK_TYPE_ICONS[key];
              return (
                <button
                  key={key}
                  type="button"
                  role="option"
                  aria-selected={key === value}
                  className="task-types-editor__icon-option"
                  onClick={() => {
                    onChange(key);
                    setOpen(false);
                  }}
                >
                  <Icon size={15} strokeWidth={1.75} aria-hidden="true" />
                </button>
              );
            })}
          </div>
        </AnchoredPanel>
      )}
    </>
  );
}

interface TaskTypesEditorProps {
  scope: TaskTypeScope;
  /** Replié par défaut dans une carte de groupe, déplié dans un onglet. */
  collapsible?: boolean;
}

// Types de tâche personnalisables (session du 2026-10-09) — même composant
// pour un groupe (Administration > Groupes) et un projet sans groupe (onglet
// Administration du projet). Droits calculés par le serveur (`can_manage`).
export function TaskTypesEditor({ scope, collapsible = false }: TaskTypesEditorProps) {
  const { showToast } = useToast();
  const [data, setData] = useState<TaskTypeList | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [open, setOpen] = useState(!collapsible);
  const [pending, setPending] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newIcon, setNewIcon] = useState<TaskTypeIcon>("tag");
  const scopeKey = "team" in scope ? `team:${scope.team}` : `project:${scope.project}`;

  const reload = useCallback(() => {
    getTaskTypes(scope, true)
      .then((list) => {
        setData(list);
        setLoadError(null);
      })
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Impossible de charger les types."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey]);

  useEffect(() => {
    if (open) reload();
  }, [open, reload]);

  async function run(action: () => Promise<unknown>, success?: string) {
    setPending(true);
    try {
      await action();
      invalidateTaskTypes();
      reload();
      if (success) showToast(success);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action impossible.");
    } finally {
      setPending(false);
    }
  }

  async function handleCreate() {
    const label = newLabel.trim();
    if (!label) return;
    await run(() => createTaskType(scope, label, newIcon), "Type de tâche ajouté.");
    setNewLabel("");
    setNewIcon("tag");
  }

  const active = data?.types.filter((t) => t.status === "active") ?? [];
  const archived = data?.types.filter((t) => t.status === "archived") ?? [];
  const canManage = data?.can_manage ?? false;

  function renderRow(taskType: TaskType) {
    if (!canManage) {
      return (
        <li key={taskType.id}>
          <TypeBadge icon={taskType.icon} label={taskType.label} />
        </li>
      );
    }
    return (
      <li key={taskType.id} className="task-types-editor__row">
        <IconPicker
          value={taskType.icon}
          onChange={(icon) => void run(() => updateTaskTypeDefinition(taskType.id, { icon }))}
          disabled={pending}
        />
        <span className="task-types-editor__label">
          <InlineEditableText
            value={taskType.label}
            onSave={(label) => void run(() => updateTaskTypeDefinition(taskType.id, { label }))}
            ariaLabel="Libellé du type"
            disabled={pending}
          />
        </span>
        <button
          type="button"
          className="task-types-editor__row-action"
          onClick={() => void run(() => archiveTaskType(taskType.id), "Type archivé.")}
          disabled={pending || active.length <= 1}
          aria-label={`Archiver ${taskType.label}`}
          title={active.length <= 1 ? "Il faut garder au moins un type actif" : "Archiver"}
        >
          <Archive size={13} strokeWidth={1.75} aria-hidden="true" />
        </button>
      </li>
    );
  }

  const body = (
    <div className="task-types-editor__body">
      {loadError ? (
        <p className="task-types-editor__muted">{loadError}</p>
      ) : data === null ? (
        <p className="task-types-editor__muted">Chargement…</p>
      ) : (
        <>
          <ul className={canManage ? "task-types-editor__list" : "task-types-editor__badges"}>
            {active.map(renderRow)}
          </ul>

          {canManage && (
            <div className="task-types-editor__add">
              <IconPicker value={newIcon} onChange={setNewIcon} disabled={pending} />
              <input
                type="text"
                value={newLabel}
                maxLength={50}
                placeholder="Nouveau type…"
                onChange={(event) => setNewLabel(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void handleCreate();
                }}
                disabled={pending}
              />
              <button type="button" onClick={() => void handleCreate()} disabled={pending || !newLabel.trim()}>
                Ajouter
              </button>
            </div>
          )}

          {canManage && archived.length > 0 && (
            <div className="task-types-editor__archived">
              <span className="task-types-editor__muted">Archivés</span>
              <ul className="task-types-editor__list">
                {archived.map((taskType) => (
                  <li key={taskType.id} className="task-types-editor__row task-types-editor__row--archived">
                    <TypeBadge icon={taskType.icon} label={taskType.label} />
                    <button
                      type="button"
                      className="task-types-editor__row-action"
                      onClick={() => void run(() => restoreTaskType(taskType.id), "Type restauré.")}
                      disabled={pending}
                      aria-label={`Restaurer ${taskType.label}`}
                      title="Restaurer"
                    >
                      <RotateCcw size={13} strokeWidth={1.75} aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );

  if (!collapsible) return <div className="task-types-editor">{body}</div>;

  return (
    <div className="task-types-editor task-types-editor--collapsible">
      <button
        type="button"
        className="task-types-editor__toggle"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        Types de tâche
        <ChevronDown
          size={14}
          strokeWidth={1.75}
          aria-hidden="true"
          className={open ? "task-types-editor__chevron task-types-editor__chevron--open" : "task-types-editor__chevron"}
        />
      </button>
      {open && body}
    </div>
  );
}
