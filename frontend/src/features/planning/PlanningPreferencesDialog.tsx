import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  clearWorkingHoursOverride,
  getWorkingHours,
  updatePlanningPreferences,
  updateWorkingHours,
} from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { Combobox } from "../../components/Combobox";
import type { Me, WorkingHoursDay } from "../../types/watodo";
import { PLANNING_PALETTE } from "./types";

interface PlanningPreferencesDialogProps {
  me: Me;
  /** Lundi de la semaine actuellement affichée dans le planning (ISO
   * "YYYY-MM-DD") — cible par défaut du mode "cette semaine seulement". */
  currentWeekStart: string;
  /** Personnes qui m'ont accordé le droit de gérer leurs horaires. */
  delegatedUsers: { id: string; label: string }[];
  onClose: () => void;
  /** Appelé seulement si la couleur a changé (les horaires n'affectent pas `Me`). */
  onSaved: (updated: Me) => void;
}

type Scope = "base" | "week";

function displayName(user: { first_name: string; last_name: string; username: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

export function PlanningPreferencesDialog({
  me,
  currentWeekStart,
  delegatedUsers,
  onClose,
  onSaved,
}: PlanningPreferencesDialogProps) {
  const [color, setColor] = useState(me.planning_color);
  const [colorSaving, setColorSaving] = useState(false);
  const [outlookSyncSaving, setOutlookSyncSaving] = useState(false);

  const [targetUserId, setTargetUserId] = useState(""); // "" = moi-même
  const [scope, setScope] = useState<Scope>("base");
  const [days, setDays] = useState<WorkingHoursDay[] | null>(null);
  const [isOverride, setIsOverride] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const targetLabel = targetUserId
    ? (delegatedUsers.find((u) => u.id === targetUserId)?.label ?? "")
    : displayName(me);

  useEffect(() => {
    let cancelled = false;
    setDays(null);
    setError(null);
    getWorkingHours({ user: targetUserId || undefined, week: scope === "week" ? currentWeekStart : undefined })
      .then((data) => {
        if (cancelled) return;
        setDays(data.days);
        setIsOverride(data.is_override);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger les horaires.");
      });
    return () => {
      cancelled = true;
    };
  }, [targetUserId, scope, currentWeekStart]);

  function updateDay(weekday: number, patch: Partial<WorkingHoursDay>) {
    setDays((current) =>
      current ? current.map((d) => (d.weekday === weekday ? { ...d, ...patch } : d)) : current,
    );
  }

  async function handleSaveColor() {
    setColorSaving(true);
    setError(null);
    try {
      onSaved(await updatePlanningPreferences({ planningColor: color }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setColorSaving(false);
    }
  }

  async function handleToggleOutlookSync(checked: boolean) {
    setOutlookSyncSaving(true);
    setError(null);
    try {
      onSaved(await updatePlanningPreferences({ outlookCalendarSyncEnabled: checked }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setOutlookSyncSaving(false);
    }
  }

  async function handleSaveSchedule() {
    if (!days) return;
    for (const day of days) {
      if (day.enabled && day.start >= day.end) {
        setError(`${day.weekday_display} : l'heure de début doit précéder l'heure de fin.`);
        return;
      }
    }
    setBusy(true);
    setError(null);
    try {
      const data = await updateWorkingHours({
        days,
        user: targetUserId || undefined,
        weekStart: scope === "week" ? currentWeekStart : undefined,
      });
      setDays(data.days);
      setIsOverride(data.is_override);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Enregistrement impossible.");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearOverride() {
    setBusy(true);
    setError(null);
    try {
      const data = await clearWorkingHoursOverride({ week: currentWeekStart, user: targetUserId || undefined });
      setDays(data.days);
      setIsOverride(data.is_override);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Le retrait a échoué.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="planning-dialog__overlay" onClick={onClose}>
      <div className="planning-dialog" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="planning-dialog__header">
          <h2>Mon planning</h2>
          <button type="button" className="planning-dialog__close" onClick={onClose} aria-label="Fermer">
            <X size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        {error && <p className="planning-dialog__error">{error}</p>}

        <div className="planning-dialog__body">
          {!targetUserId && (
            <div className="planning-field">
              <span>Couleur de mon calendrier</span>
              <div className="planning-color-swatches">
                <button
                  type="button"
                  className={`planning-color-swatch planning-color-swatch--default${color === "" ? " planning-color-swatch--selected" : ""}`}
                  onClick={() => setColor("")}
                  aria-label="Couleur par défaut (accent thémé)"
                  title="Par défaut"
                >
                  {color === "" && <Check size={13} strokeWidth={2} aria-hidden="true" />}
                </button>
                {PLANNING_PALETTE.map((hex) => (
                  <button
                    key={hex}
                    type="button"
                    className={`planning-color-swatch${color === hex ? " planning-color-swatch--selected" : ""}`}
                    style={{ backgroundColor: hex }}
                    onClick={() => setColor(hex)}
                    aria-label={`Choisir la couleur ${hex}`}
                    title={hex}
                  >
                    {color === hex && <Check size={13} strokeWidth={2} color="#fff" aria-hidden="true" />}
                  </button>
                ))}
                {color !== me.planning_color && (
                  <button
                    type="button"
                    className="planning-btn planning-btn--primary planning-color-swatches__save"
                    onClick={handleSaveColor}
                    disabled={colorSaving}
                  >
                    {colorSaving ? "…" : "Enregistrer"}
                  </button>
                )}
              </div>
            </div>
          )}

          {!targetUserId && (
            <label className="planning-field planning-field--inline planning-field--align-top">
              <Checkbox
                checked={me.outlook_calendar_sync_enabled}
                onCheckedChange={handleToggleOutlookSync}
                disabled={outlookSyncSaving}
                aria-label="Synchroniser mon calendrier vers Outlook"
              />
              <span>
                Synchroniser mon calendrier vers Outlook
                <span className="planning-field__hint">
                  Awtodo → Outlook uniquement (création, modification, suppression), jamais l'inverse. Vos
                  événements existants sont synchronisés à l'activation. Nécessite que la connexion Office
                  365 de l'organisation soit configurée et activée par un administrateur.
                </span>
              </span>
            </label>
          )}

          <div className="planning-field">
            <span>Horaires de travail</span>

            {delegatedUsers.length > 0 && (
              <Combobox
                options={[
                  { value: "", label: "Moi" },
                  ...delegatedUsers.map((u) => ({ value: u.id, label: u.label })),
                ]}
                value={targetUserId}
                onChange={setTargetUserId}
                clearable={false}
              />
            )}

            <div className="planning-hours-scope" role="tablist" aria-label="Portée">
              <button
                type="button"
                role="tab"
                aria-selected={scope === "base"}
                className={scope === "base" ? "planning-toggle planning-toggle--on" : "planning-toggle"}
                onClick={() => setScope("base")}
              >
                Toutes les semaines
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={scope === "week"}
                className={scope === "week" ? "planning-toggle planning-toggle--on" : "planning-toggle"}
                onClick={() => setScope("week")}
              >
                Cette semaine seulement
              </button>
            </div>

            {scope === "week" && (
              <p className="planning-dialog__muted">
                {isOverride
                  ? `Exception déjà posée pour la semaine du ${currentWeekStart}, pour ${targetLabel}.`
                  : `Aucune exception pour la semaine du ${currentWeekStart} — ${targetLabel} suit le modèle habituel.`}
              </p>
            )}
          </div>

          {days === null ? (
            <p className="planning-dialog__muted">Chargement…</p>
          ) : (
            <ul className="planning-hours-days">
              {days.map((day) => (
                <li key={day.weekday} className="planning-hours-day">
                  <Checkbox
                    checked={day.enabled}
                    onCheckedChange={(checked) => updateDay(day.weekday, { enabled: checked })}
                    aria-label={`${day.weekday_display} travaillé`}
                  />
                  <span className="planning-hours-day__label">{day.weekday_display}</span>
                  {day.enabled ? (
                    <span className="planning-hours-day__times">
                      <input
                        type="time"
                        value={day.start}
                        onChange={(event) => updateDay(day.weekday, { start: event.target.value })}
                      />
                      <span>–</span>
                      <input
                        type="time"
                        value={day.end}
                        onChange={(event) => updateDay(day.weekday, { end: event.target.value })}
                      />
                    </span>
                  ) : (
                    <span className="planning-dialog__muted">Non travaillé</span>
                  )}
                </li>
              ))}
            </ul>
          )}

          <p className="planning-dialog__muted">
            Les horaires en dehors de cette plage apparaissent grisés dans la vue Semaine.
          </p>

          <div className="planning-dialog__footer">
            {scope === "week" && isOverride && (
              <button type="button" className="planning-btn planning-btn--danger" onClick={handleClearOverride} disabled={busy}>
                Retirer l'exception
              </button>
            )}
            <span className="planning-dialog__footer-spacer" />
            <button type="button" className="planning-btn" onClick={onClose} disabled={busy}>
              Fermer
            </button>
            <button
              type="button"
              className="planning-btn planning-btn--primary"
              onClick={handleSaveSchedule}
              disabled={busy || days === null}
            >
              Enregistrer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
