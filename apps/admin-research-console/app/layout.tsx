import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AfriMentor Research Console",
  description: "Internal admin console — RAG corpus & persona consistency (card O4.2)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen font-sans">{children}</body>
    </html>
  );
}
