import { History } from "lucide-react";
import { useEffect, useState } from "react";
import { getProjectHistory } from "../../api/client";
import { Skeleton } from "../../components/Skeleton";
import { auditEntityLabel, auditFieldLabel, auditVerbLabel } from "../../lib/auditFieldLabels";
import type { Project, ProjectHistoryEntry } from "../../types/watodo";
import "./HistoryTab.css";

interface HistoryTabProps {
  project: Project;
}

function displayName(user: { first_name: string; last_name: string; username: string } | null): string {
  if (!user) return "Système";
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

function entryDescription(entry: ProjectHistoryEntry): string {
  if (entry.verb === "field_changed") {
    return `${auditFieldLabel(entry.field_name)} : ${entry.old_value || "—"} → ${entry.new_value || "—"}`;
  }
  return entry.new_value;
}

export function HistoryTab({ project }: HistoryTabProps) {
  const [entries, setEntries] = useState<ProjectHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProjectHistory(project.id)
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Impossible de charger l'historique."));
  }, [project.id]);

  return (
    <div className="history-tab">
      <p className="history-tab__intro">
        Tâches, incidents, membres, budget, documentation, communication, planning.
      </p>

      {error && <p className="history-tab__error">{error}</p>}

      {entries === null && !error && (
        <div className="history-tab__skeleton">
          <Skeleton height="40px" />
          <Skeleton height="40px" />
          <Skeleton height="40px" />
        </div>
      )}

      {entries !== null && (
        <ul className="history-tab__list">
          {entries.map((entry) => (
            <li key={entry.id} className="history-tab__entry">
              <History size={14} strokeWidth={1.75} aria-hidden="true" className="history-tab__entry-icon" />
              <div className="history-tab__entry-body">
                <div className="history-tab__entry-header">
                  <span className="history-tab__entry-tag">{auditEntityLabel(entry.entity_type)}</span>
                  <span className="history-tab__entry-verb">{auditVerbLabel(entry.verb)}</span>
                </div>
                <p className="history-tab__entry-description">{entryDescription(entry)}</p>
                <span className="history-tab__entry-meta">
                  {displayName(entry.actor)} ·{" "}
                  <time dateTime={entry.created_at} title={new Date(entry.created_at).toLocaleString("fr-FR")}>
                    {new Date(entry.created_at).toLocaleString("fr-FR", {
                      day: "2-digit",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </span>
              </div>
            </li>
          ))}
          {entries.length === 0 && <li className="history-tab__empty">Aucune activité enregistrée pour l'instant.</li>}
        </ul>
      )}
    </div>
  );
}
