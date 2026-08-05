"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";

// Shows only while genuinely offline (navigator.onLine + the online/offline
// events) — so cached content never silently looks indistinguishable from
// live content. Matters more once G1.3's real API is live and "offline"
// starts meaning "possibly stale," not just "the mock data still works."
export function OfflineBanner() {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    setIsOffline(!navigator.onLine);
    const goOffline = () => setIsOffline(true);
    const goOnline = () => setIsOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <div
      role="status"
      className="flex items-center justify-center gap-xs bg-error-container px-md py-xs text-center font-label-sm text-label-sm text-on-error-container"
    >
      <Icon name="cloud_off" size={16} />
      You&rsquo;re offline — showing the last cached version.
    </div>
  );
}
