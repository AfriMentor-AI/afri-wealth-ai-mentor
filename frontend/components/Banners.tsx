"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { useInstallPrompt } from "@/lib/useInstallPrompt";
import { FeedbackSurveyModal } from "./FeedbackSurveyModal";

const DISMISS_KEY = "afrimentor-install-banner-dismissed";

/** Offline notice + PWA install prompt (W13/M10 designs). Mounted once in the root layout. */
export function Banners() {
  const { platform, promptInstall } = useInstallPrompt();
  const [offline, setOffline] = useState(false);
  const [offlineHidden, setOfflineHidden] = useState(false);
  const [dismissed, setDismissed] = useState(true);
  const [iosSteps, setIosSteps] = useState(false);

  useEffect(() => {
    setOffline(!navigator.onLine);
    const off = () => { setOffline(true); setOfflineHidden(false); };
    const on = () => setOffline(false);
    window.addEventListener("offline", off);
    window.addEventListener("online", on);
    try { setDismissed(window.localStorage.getItem(DISMISS_KEY) === "1"); } catch { setDismissed(false); }
    return () => { window.removeEventListener("offline", off); window.removeEventListener("online", on); };
  }, []);

  function dismissInstall() {
    setDismissed(true);
    try { window.localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
  }

  const showInstall = !dismissed && (platform === "installable" || platform === "ios");

  return (
    <>
      {(offline && !offlineHidden) || showInstall ? (
        <div className="relative z-[60] flex w-full flex-col gap-3 px-4 pb-1 pt-3 md:px-8">
          {offline && !offlineHidden && (
            <div role="status" className="flex w-full items-center justify-between rounded-xl bg-indigo-mist px-4 py-3 shadow-sm md:px-5">
              <div className="flex min-w-0 items-center gap-3.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-paper/80 text-secondary">
                  <span className="material-symbols-outlined text-[18px]">wifi_off</span>
                </div>
                <p className="font-body-md text-label-sm text-secondary">
                  <span className="font-semibold">You are offline.</span> Showing your last saved version until the connection returns.
                </p>
              </div>
              <button type="button" aria-label="Dismiss offline notice" onClick={() => setOfflineHidden(true)} className="ml-3 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-secondary transition-colors hover:bg-paper/60">
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            </div>
          )}

          {showInstall && (
            <div className="relative w-full overflow-hidden rounded-2xl border border-outline-subtle bg-paper p-4 shadow-sm lg:p-5">
              <div className="absolute inset-y-0 left-0 w-1.5 bg-sunburst-gold" />
              <div className="flex flex-col justify-between gap-4 pl-2 md:flex-row md:items-center">
                <div className="flex items-start gap-4 sm:items-center">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gold-mist/80 p-0.5 shadow-sm">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-paper">
                      <span className="material-symbols-outlined text-[24px] text-sunburst-gold">verified</span>
                    </div>
                  </div>
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className="font-label-sm text-label-sm font-semibold text-on-surface">Install AfriMentor AI</span>
                      <span className="rounded-full bg-surface-container px-2 py-0.5 font-caption text-[11px] font-medium text-outline-strong">Works offline</span>
                    </div>
                    <p className="mt-0.5 font-body-md text-label-sm text-on-surface-variant">
                      {platform === "ios" ? (
                        <>Tap <Icon name="ios_share" size={14} className="inline align-text-bottom" /> Share, then “Add to Home Screen”.</>
                      ) : (
                        "Quick, offline-ready access. No app store needed."
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2.5 self-end md:self-center">
                  <button type="button" onClick={dismissInstall} className="h-10 rounded-full px-4 font-label-sm text-label-sm text-on-surface-variant transition-colors hover:bg-surface-default">Not now</button>
                  {platform === "installable" ? (
                    <button type="button" onClick={promptInstall} className="flex h-10 items-center gap-2 rounded-full bg-sunburst-gold px-6 font-label-sm text-label-sm font-bold text-on-surface shadow-[0_4px_0_0_#9A6B00] transition-all active:translate-y-1 active:shadow-none">
                      <span className="material-symbols-outlined text-[18px]">download_for_offline</span>
                      <span>Install app</span>
                    </button>
                  ) : (
                    <button type="button" onClick={() => setIosSteps((s) => !s)} aria-expanded={iosSteps} className="flex h-10 items-center gap-2 rounded-full bg-sunburst-gold px-6 font-label-sm text-label-sm font-bold text-on-surface shadow-[0_4px_0_0_#9A6B00] transition-all active:translate-y-1 active:shadow-none">
                      {iosSteps ? "Hide steps" : "How?"}
                    </button>
                  )}
                </div>
              </div>
              {platform === "ios" && iosSteps && (
                <ol className="mt-4 list-decimal space-y-1 pl-12 font-body-md text-label-sm text-on-surface-variant">
                  <li>Tap the <strong>Share</strong> icon in Safari’s toolbar.</li>
                  <li>Scroll down and tap <strong>“Add to Home Screen”</strong>.</li>
                  <li>Tap <strong>“Add”</strong> in the top-right corner.</li>
                </ol>
              )}
            </div>
          )}
        </div>
      ) : null}
      <FeedbackSurveyModal />
    </>
  );
}
