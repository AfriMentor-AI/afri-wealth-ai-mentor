"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import {
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  type AppNotification,
} from "@/lib/api";

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffHours = (now.getTime() - d.getTime()) / (1000 * 60 * 60);
    if (diffHours < 1) {
      const diffMins = Math.max(1, Math.round(diffHours * 60));
      return `${diffMins}m ago`;
    }
    if (diffHours < 24) {
      return `${Math.round(diffHours)}h ago`;
    }
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function getIconForKind(kind: string): string {
  switch (kind) {
    case "streak_at_risk":
      return "local_fire_department";
    case "daily_action_reminder":
      return "flag";
    default:
      return "notifications";
  }
}

export function NotificationPopover() {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.readAt).length;

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const list = await fetchNotifications();
        if (mounted) setNotifications(list);
      } catch (err) {
        console.warn("Error loading notifications:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();

    const interval = setInterval(load, 60000); // refresh every minute
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  // Close when clicking outside
  useEffect(() => {
    if (!isOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  async function handleMarkRead(id: string) {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, readAt: new Date().toISOString() } : n))
    );
    await markNotificationRead(id);
  }

  async function handleMarkAllRead() {
    setNotifications((prev) =>
      prev.map((n) => ({ ...n, readAt: n.readAt || new Date().toISOString() }))
    );
    await markAllNotificationsRead();
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={`Notifications (${unreadCount} unread)`}
        className="tap-target relative flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container-low active:scale-95"
      >
        <Icon name="notifications" size={20} filled={isOpen} />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-bold text-on-error">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-outline-variant bg-surface p-sm shadow-xl animate-in fade-in zoom-in-95">
          <div className="mb-xs flex items-center justify-between border-b border-outline-variant/50 pb-xs px-xs">
            <h4 className="font-title-sm text-title-sm text-on-surface">Notifications</h4>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-[11px] font-medium text-primary hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-72 overflow-y-auto space-y-1">
            {loading && notifications.length === 0 ? (
              <div className="py-6 text-center text-body-sm text-on-surface-variant">
                Loading notifications...
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center text-body-sm text-on-surface-variant">
                <Icon name="notifications_off" size={28} className="mx-auto mb-2 opacity-40" />
                <p>No notifications yet</p>
                <p className="text-[11px] text-on-surface-variant/70">You are all caught up!</p>
              </div>
            ) : (
              notifications.map((n) => {
                const isUnread = !n.readAt;
                return (
                  <div
                    key={n.id}
                    onClick={() => isUnread && handleMarkRead(n.id)}
                    className={`flex items-start gap-sm rounded-lg p-2 transition-colors cursor-pointer ${
                      isUnread
                        ? "bg-primary-container/25 hover:bg-primary-container/35"
                        : "hover:bg-surface-container-low"
                    }`}
                  >
                    <div
                      className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                        isUnread
                          ? "bg-primary text-on-primary"
                          : "bg-surface-variant text-on-surface-variant"
                      }`}
                    >
                      <Icon name={getIconForKind(n.kind)} size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <p className={`text-xs font-semibold truncate ${isUnread ? "text-on-surface" : "text-on-surface-variant"}`}>
                          {n.title}
                        </p>
                        <span className="shrink-0 text-[10px] text-on-surface-variant/70">
                          {formatTimestamp(n.createdAt)}
                        </span>
                      </div>
                      <p className="text-[11px] leading-snug text-on-surface-variant line-clamp-2 mt-0.5">
                        {n.body}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
