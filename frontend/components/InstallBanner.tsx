"use client";

import { useEffect, useState } from "react";
import { Icon } from "./Icon";
import { useInstallPrompt } from "@/lib/useInstallPrompt";

const DISMISS_KEY = "afrimentor-install-banner-dismissed";

export function InstallBanner() {
  const { platform, promptInstall } = useInstallPrompt();
  const [dismissed, setDismissed] = useState(true); // default hidden until confirmed dismiss-state, client-only (see effect)
  const [showIOSSteps, setShowIOSSteps] = useState(false);

  useEffect(() => {
    setDismissed(window.localStorage.getItem(DISMISS_KEY) === "1");
  }, []);

  function dismiss() {
    setDismissed(true);
    window.localStorage.setItem(DISMISS_KEY, "1");
  }

  if (dismissed) return null;
  if (platform === "unsupported" || platform === "already-installed") return null;

  return (
    <div className="border-b border-outline-variant bg-primary-container px-md py-sm text-on-primary-container">
      <div className="mx-auto flex max-w-5xl items-center gap-sm">
        <Icon name="install_mobile" filled size={20} className="shrink-0" />

        {platform === "installable" && (
          <>
            <p className="flex-1 font-body-md text-[13px] leading-tight md:text-body-md">
              Install AfriMentor AI for quick, offline-ready access — no app store needed.
            </p>
            <button
              onClick={promptInstall}
              className="tap-target shrink-0 whitespace-nowrap rounded-full bg-primary px-md py-xs font-label-sm text-label-sm text-on-primary transition-transform active:scale-95"
            >
              Install
            </button>
          </>
        )}

        {platform === "ios" && (
          <>
            <p className="flex-1 font-body-md text-[13px] leading-tight md:text-body-md">
              Install AfriMentor AI: tap <Icon name="ios_share" size={14} className="inline align-text-bottom" /> Share, then &ldquo;Add to Home Screen.&rdquo;
            </p>
            <button
              onClick={() => setShowIOSSteps((s) => !s)}
              aria-expanded={showIOSSteps}
              className="tap-target shrink-0 rounded-full bg-primary px-md py-xs font-label-sm text-label-sm text-on-primary"
            >
              {showIOSSteps ? "Hide" : "How?"}
            </button>
          </>
        )}

        <button
          onClick={dismiss}
          aria-label="Dismiss install banner"
          className="tap-target shrink-0 flex items-center justify-center rounded-full text-on-primary-container/70 hover:bg-primary/20"
        >
          <Icon name="close" size={18} />
        </button>
      </div>

      {platform === "ios" && showIOSSteps && (
        <ol className="mx-auto mt-sm max-w-5xl list-decimal space-y-1 pl-8 font-body-md text-[13px] text-on-primary-container">
          <li>
            Tap the <strong>Share</strong> icon in Safari&rsquo;s toolbar (the square with an arrow pointing up).
          </li>
          <li>
            Scroll down and tap <strong>&ldquo;Add to Home Screen.&rdquo;</strong>
          </li>
          <li>
            Tap <strong>&ldquo;Add&rdquo;</strong> in the top-right corner.
          </li>
        </ol>
      )}
    </div>
  );
}
