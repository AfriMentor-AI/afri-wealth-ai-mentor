"use client";

import { useEffect, useState } from "react";

// The event Chrome/Edge (mobile AND desktop) fire when a page meets PWA
// installability criteria — valid manifest, registered service worker,
// served over HTTPS. This is exactly what the Lighthouse PWA checks in
// G1.4 verify; a passing Lighthouse score is what makes this event fire
// at all. TypeScript doesn't ship a built-in type for it.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

type InstallPlatform = "installable" | "ios" | "unsupported" | "already-installed";

export function useInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  // Starts as "unsupported" on both server AND the client's first render
  // — the real platform is only knowable client-side (user agent, matchMedia,
  // and whether the browser ever fires the event), so detecting it must
  // happen in an effect, not during render. Same hydration-safety pattern
  // as OfflineBanner/ThemeToggle elsewhere in this app — determining this
  // during render would make the client's first pass diverge from the
  // server's and throw a hydration error.
  const [platform, setPlatform] = useState<InstallPlatform>("unsupported");

  useEffect(() => {
    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      // iOS Safari's own (non-standard) flag for "already added to home screen"
      (window.navigator as unknown as { standalone?: boolean }).standalone === true;

    if (isStandalone) {
      setPlatform("already-installed");
      return;
    }

    const isIOS = /iphone|ipad|ipod/i.test(window.navigator.userAgent);
    if (isIOS) {
      setPlatform("ios");
      // No beforeinstallprompt on iOS at all — nothing further to listen for.
      return;
    }

    function handleBeforeInstallPrompt(e: Event) {
      e.preventDefault(); // stop the browser's own mini-infobar so our banner is the single source of the prompt
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setPlatform("installable");
    }

    function handleAppInstalled() {
      setPlatform("already-installed");
      setDeferredPrompt(null);
    }

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, []);

  async function promptInstall() {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    if (choice.outcome === "accepted") {
      setPlatform("already-installed");
    }
    // The captured event can only be used once — discard it either way.
    setDeferredPrompt(null);
  }

  return { platform, promptInstall };
}
