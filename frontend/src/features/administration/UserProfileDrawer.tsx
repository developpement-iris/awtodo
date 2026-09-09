import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { getUserAssignedTasks } from "../../api/client";
import { StatusBadge } from "../../components/StatusBadge";
import { TypeBadge } from "../../components/TypeBadge";
import { priorityTone, statusTone, taskStatusIcon } from "../../lib/badges";
import type { Task, Team, User } from "../../types/watodo";
import "./UserProfileDrawer.css";

interface UserProfileDrawerProps {
  user: User;
  teams: Team[];
  onClose: () => void;
}

export function UserProfileDrawer({ user, teams, onClose }: UserProfileDrawerProps) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setTasks(null);
    setError(null);

    getUserAssignedTasks(user.id)
      .then((data) => {
        if (!cancelled) setTasks(data);
      })
      .catch(() => {
        if (!cancelled) setError("Impossible de charger les tâches assignées.");
      });

    return () => {
      cancelled = true;
    };
  }, [user.id]);

  const displayName = `${user.first_name} ${user.last_name}`.trim() || user.username;
  const userTeams = teams.filter((team) => user.teams.includes(team.id));

  return (
    <div className="user-profile-drawer__overlay" onClick={onClose}>
      <aside className="user-profile-drawer" onClick={(event) => event.stopPropagation()}>
        <div className="user-profile-drawer__header">
          <h2 className="user-profile-drawer__title">{displayName}</h2>
          <button type="button" className="user-profile-drawer__close" onClick={onClose} aria-label="Fermer">
            <X size={18} strokeWidth={1.75} aria-hidden="true" />
          </button>
        </div>

        <div className="user-profile-drawer__badges">
          <StatusBadge label={user.organisation_role_display} tone="neutral" />
          <StatusBadge label={user.account_type_display} tone="neutral" />
          <StatusBadge label={user.account_status_display} tone={user.account_status === "active" ? "positive" : "neutral"} />
        </div>

        <section className="user-profile-drawer__section">
          <h3 className="user-profile-drawer__section-title">Email</h3>
          <p className="user-profile-drawer__meta">{user.email || "Non renseigné"}</p>
        </section>

        <section className="user-profile-drawer__section">
          <h3 className="user-profile-drawer__section-title">Groupes</h3>
          {userTeams.length === 0 ? (
            <p className="user-profile-drawer__empty">Aucun groupe.</p>
          ) : (
            <ul className="user-profile-drawer__team-list">
              {userTeams.map((team) => (
                <li key={team.id}>{team.name}</li>
              ))}
            </ul>
          )}
        </section>

        <section className="user-profile-drawer__section">
          <h3 className="user-profile-drawer__section-title">Tâches assignées</h3>
          <p className="user-profile-drawer__meta-note">
            Toutes les tâches assignées, y compris sur des projets hors de votre appartenance.
          </p>
          {tasks === null && !error && <p className="user-profile-drawer__empty">Chargement…</p>}
          {error && <p className="user-profile-drawer__error">{error}</p>}
          {tasks !== null && tasks.length === 0 && (
            <p className="user-profile-drawer__empty">Aucune tâche assignée pour l'instant.</p>
          )}
          {tasks !== null && tasks.length > 0 && (
            <ul className="user-profile-drawer__task-list">
              {tasks.map((task) => (
                <li key={task.id} className="user-profile-drawer__task">
                  <span className="user-profile-drawer__task-title">{task.title}</span>
                  <span className="user-profile-drawer__task-badges">
                    <TypeBadge type={task.task_type} label={task.task_type_display} />
                    <StatusBadge label={task.status_display} tone={statusTone(task.status)} icon={taskStatusIcon(task.status)} />
                    <StatusBadge label={task.priority_display} tone={priorityTone(task.priority)} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </div>
  );
}
