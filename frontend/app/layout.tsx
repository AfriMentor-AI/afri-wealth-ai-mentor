import type { Metadata, Viewport } from "next";
import { AppStateProvider } from "@/lib/store";
import { OfflineBanner } from "@/components/OfflineBanner";
import "./globals.css";

export const metadata: Metadata = {
  title: "AfriMentor AI",
  description: "A financial mentorship companion for African entrepreneurs.",
  manifest: "/manifest.json",
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
    <html lang="en" data-theme="heritage">
      <head>
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
            fallback, see public/sw.js) as early as possible. Guarded for
            browsers without SW support and wrapped so a registration
            failure never breaks the page. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `if("serviceWorker" in navigator){window.addEventListener("load",function(){navigator.serviceWorker.register("/sw.js").catch(function(e){console.warn("SW registration failed:",e);});});}`,
          }}
        />
      </head>
      <body className="font-body min-h-screen">
        <AppStateProvider>
          <OfflineBanner />
          <div className="min-h-screen">{children}</div>
        </AppStateProvider>
      </body>
    </html>
  );
}
