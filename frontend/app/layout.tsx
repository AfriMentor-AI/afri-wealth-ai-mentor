import type { Metadata, Viewport } from "next";
import { AppStateProvider } from "@/lib/store";
import { OfflineBanner } from "@/components/OfflineBanner";
import { InstallBanner } from "@/components/InstallBanner";
import "./globals.css";

export const metadata: Metadata = {
  title: "AfriMentor AI",
  description: "A financial mentorship companion for African entrepreneurs.",
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#fcf9f3",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="heritage" suppressHydrationWarning>
      <head>
        <link
          rel="manifest"
          href="/manifest.json"
          crossOrigin="use-credentials"
        />
        {/* eslint-disable @next/next/no-page-custom-font */}
        {/* Fonts load via <link> (not CSS @import) so the browser can start
            fetching them in parallel with the app CSS instead of serially.
            preconnect lets the font host handshake overlap the main document
            fetch. The stylesheets were previously also duplicated via @import
            in globals.css — that double-load is gone, and `display=swap` keeps
            the icon ligatures readable (a fallback font can't render the
            Material Symbols ligature names). */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700;800&family=Inter:wght@400;600&display=swap"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
        />
        {/* Runs before hydration so the correct theme is applied before
            first paint — without this, the page briefly flashes the
            default "heritage" theme even for users who chose "nocturnal",
            since React state (and thus the useEffect that normally sets
            this attribute) isn't available until after hydration. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("afrimentor-theme");if(t==="heritage"||t==="nocturnal"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`,
          }}
        />
        {/* Registers the service worker (app-shell caching + offline
            fallback, see public/sw.js) — PRODUCTION ONLY. Running a
            caching service worker during `npm run dev` is a well-known
            footgun: the browser's SW registration persists independently
            of the dev server, so restarting `next dev` (or even editing
            source files) does NOT clear it — you can end up debugging a
            "fixed" bug that your browser is still silently serving the
            old cached JS for. In dev mode this actively unregisters any
            SW a previous production build may have left behind, so
            npm run dev is always guaranteed to hit the real dev server. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              process.env.NODE_ENV === "production"
                ? `if("serviceWorker" in navigator){window.addEventListener("load",function(){navigator.serviceWorker.register("/sw.js").catch(function(e){console.warn("SW registration failed:",e);});});}`
                : `if("serviceWorker" in navigator){navigator.serviceWorker.getRegistrations().then(function(regs){regs.forEach(function(r){r.unregister();});});}`,
          }}
        />
      </head>
      <body className="font-body min-h-screen" suppressHydrationWarning>
        <AppStateProvider>
          <InstallBanner />
          <OfflineBanner />
          <div className="min-h-screen">{children}</div>
        </AppStateProvider>
      </body>
    </html>
  );
}
