import { Bell, Check } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/client";
import { formatRelativeTime } from "../lib/relativeTime";
import type { Notification } from "../types/watodo";
import "./NotificationsDropdown.css";

interface NotificationsDropdownProps {
  onNotificationClick?: (notification: Notification) => void;
}

export function NotificationsDropdown({ onNotificationClick }: NotificationsDropdownProps) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getUnreadNotificationCount()
      .then((data) => setUnreadCount(data.count))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!open) return;
    getNotifications()
      .then(setNotifications)
      .catch(() => setNotifications([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  async function handleNotificationClick(notification: Notification) {
    if (!notification.is_read) {
      try {
        await markNotificationRead(notification.id);
        setNotifications((current) =>
          current ? current.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)) : current,
        );
        setUnreadCount((current) => Math.max(0, current - 1));
      } catch {
        // Navigation quand même — un échec de marquage-lu ne doit pas
        // bloquer l'accès à la notification elle-même.
      }
    }
    setOpen(false);
    onNotificationClick?.(notification);
  }

  async function handleMarkAllRead() {
    try {
      await markAllNotificationsRead();
      setNotifications((current) => (current ? current.map((n) => ({ ...n, is_read: true })) : current));
      setUnreadCount(0);
    } catch {
      // Silencieux : l'utilisateur peut réessayer, pas d'état bloquant.
    }
  }

  return (
    <div className="notifications-dropdown" ref={containerRef}>
      <button
        type="button"
        className="topbar__icon-btn notifications-dropdown__trigger"
        onClick={() => setOpen((current) => !current)}
        aria-label="Notifications"
        title="Notifications"
      >
        <Bell size={17} strokeWidth={1.75} aria-hidden="true" />
        {unreadCount > 0 && <span className="notifications-dropdown__badge">{unreadCount}</span>}
      </button>

      {open && (
        <div className="notifications-dropdown__panel">
          <div className="notifications-dropdown__header">
            <span>Notifications</span>
            {unreadCount > 0 && (
              <button type="button" className="notifications-dropdown__mark-all" onClick={handleMarkAllRead}>
                <Check size={13} strokeWidth={1.75} aria-hidden="true" />
                Tout marquer comme lu
              </button>
            )}
          </div>

          {notifications === null && <p className="notifications-dropdown__empty">Chargement…</p>}
          {notifications !== null && notifications.length === 0 && (
            <p className="notifications-dropdown__empty">Aucune notification.</p>
          )}
          {notifications !== null && notifications.length > 0 && (
            <ul className="notifications-dropdown__list">
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    className={
                      notification.is_read
                        ? "notifications-dropdown__item"
                        : "notifications-dropdown__item notifications-dropdown__item--unread"
                    }
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <span className="notifications-dropdown__item-message">{notification.message}</span>
                    <time
                      dateTime={notification.created_at}
                      title={new Date(notification.created_at).toLocaleString("fr-FR")}
                    >
                      {formatRelativeTime(notification.created_at)}
                    </time>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
