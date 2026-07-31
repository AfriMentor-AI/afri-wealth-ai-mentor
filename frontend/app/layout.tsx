import type { Metadata, Viewport } from "next";
import { AppStateProvider } from "@/lib/store";
import "./globals.css";

export const metadata: Metadata = {
  title: "AfriMentor AI",
  description: "A financial mentorship companion for African entrepreneurs.",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f7efe1",
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
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700;800&family=Inter:wght@400;600&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap" rel="stylesheet" />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("afrimentor-theme");if(t==="heritage"||t==="nocturnal"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="font-body min-h-screen">
        <AppStateProvider>
          <div className="min-h-screen">{children}</div>
        </AppStateProvider>
      </body>
    </html>
  );
}
