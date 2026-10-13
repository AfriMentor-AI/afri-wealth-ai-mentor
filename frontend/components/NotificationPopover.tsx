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
    const diffHours = (Date.now() - d.getTime()) / 3600000;
    if (diffHours < 1) return `${Math.max(1, Math.round(diffHours * 60))}m ago`;
    if (diffHours < 24) return `${Math.round(diffHours)}h ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function iconForKind(kind: string): string {
  switch (kind) {
    case "streak_at_risk": return "local_fire_department";
    case "daily_action_reminder": return "flag";
    default: return "notifications";
  }
}

/**
 * Bell + popover. Same backend calls as before (fetchNotifications,
 * markNotificationRead, markAllNotificationsRead); only the look changed.
 * `buttonClassName` lets the rail, sidebar and mobile header each place it.
 */
export function NotificationPopover({
  buttonClassName = "relative flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface",
  ringClassName = "ring-surface-low",
  placement = "right-bottom",
  iconSize = 22,
  outline = false,
}: {
  buttonClassName?: string;
  ringClassName?: string;
  /** where the panel opens relative to the bell */
  placement?: "right-bottom" | "below-right" | "above-left";
  iconSize?: number;
  outline?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const unread = items.filter((n) => !n.readAt).length;

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const list = await fetchNotifications();
        if (mounted) setItems(list);
      } catch (err) {
        console.warn("Error loading notifications:", err);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    const t = setInterval(load, 60000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [open]);

  async function readOne(id: string) {
    setItems((p) => p.map((n) => (n.id === id ? { ...n, readAt: new Date().toISOString() } : n)));
    await markNotificationRead(id);
  }
  async function readAll() {
    setItems((p) => p.map((n) => ({ ...n, readAt: n.readAt || new Date().toISOString() })));
    await markAllNotificationsRead();
  }

  const pos =
    placement === "right-bottom" ? "left-full bottom-0 ml-3"
    : placement === "above-left" ? "left-0 bottom-full mb-2"
    : "right-0 top-full mt-2";

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-label={`Notifications (${unread} unread)`} aria-expanded={open} title="Notifications" className={buttonClassName}>
        <Icon name={unread || open ? "notifications" : "notifications"} filled={open} size={iconSize} />
        {unread > 0 && <span className={`absolute right-2 top-2 h-2 w-2 rounded-full bg-tertiary-container ring-2 ${ringClassName}`} />}
        {outline && null}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications" className={`absolute ${pos} z-[70] w-80 max-w-[calc(100vw-2rem)] animate-rise rounded-xl border border-outline-subtle bg-paper p-sm shadow-[0_16px_40px_rgba(20,17,13,0.14)]`}>
          <div className="mb-xs flex items-center justify-between border-b border-outline-subtle px-xs pb-xs">
            <h4 className="font-title-md text-[18px] text-on-surface">Notifications</h4>
            {unread > 0 && (
              <button type="button" onClick={readAll} className="font-caption text-caption font-semibold text-primary hover:underline">Mark all read</button>
            )}
          </div>
          <div className="max-h-80 space-y-1 overflow-y-auto">
            {loading && items.length === 0 ? (
              <div className="py-6 text-center font-caption text-caption text-on-surface-variant">Loading notifications…</div>
            ) : items.length === 0 ? (
              <div className="py-8 text-center text-on-surface-variant">
                <Icon name="notifications_off" size={28} className="mx-auto mb-2 opacity-40" />
                <p className="font-label-sm text-label-sm">No notifications yet</p>
                <p className="font-caption text-caption opacity-70">You are all caught up.</p>
              </div>
            ) : (
              items.map((n) => {
                const isUnread = !n.readAt;
                return (
                  <button key={n.id} type="button" onClick={() => isUnread && readOne(n.id)}
                    className={`flex w-full items-start gap-sm rounded-lg p-2 text-left transition-colors ${isUnread ? "bg-gold-mist/70 hover:bg-gold-mist" : "hover:bg-surface-low"}`}>
                    <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${isUnread ? "bg-primary-container text-on-primary" : "bg-surface-default text-on-surface-variant"}`}>
                      <Icon name={iconForKind(n.kind)} size={16} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className={`truncate font-label-sm text-label-sm ${isUnread ? "text-on-surface" : "text-on-surface-variant"}`}>{n.title}</p>
                        <span className="shrink-0 font-caption text-[11px] text-outline-strong">{formatTimestamp(n.createdAt)}</span>
                      </div>
                      <p className="mt-0.5 line-clamp-2 font-caption text-caption text-on-surface-variant">{n.body}</p>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
