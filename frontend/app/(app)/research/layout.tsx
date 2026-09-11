"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";

const NAV_ITEMS = [
  { label: "Personas", icon: "person", href: "/research/personas" },
  { label: "RAG Corpus", icon: "folder_shared", href: "/research/rag-corpus" },
];

export default function ResearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const openDrawer = useCallback(() => setMobileOpen(true), []);
  const closeDrawer = useCallback(() => setMobileOpen(false), []);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = "";
      };
    }
  }, [mobileOpen]);

  /* ----------------------------------------------------------------
     Shared sidebar content — rendered by both the static sidebar
     (tablet/desktop) and the mobile overlay drawer.
     `collapsed` = true renders the narrow icon-only variant (tablet).
  ---------------------------------------------------------------- */
  const sidebarContent = (collapsed: boolean) => (
    <>
      {/* Logo / brand */}
      <div className={collapsed ? "px-sm py-lg" : "px-lg py-xl"}>
        <h1
          className={`font-headline-lg tracking-tighter text-primary ${
            collapsed
              ? "text-center text-base"
              : "text-headline-lg"
          }`}
        >
          {collapsed ? "AM" : "AfriMentor"}
        </h1>
        {!collapsed && (
          <p className="mt-xs font-label-sm text-[10px] font-medium uppercase tracking-widest text-on-surface-variant">
            Console
          </p>
        )}
      </div>

      {/* Nav items */}
      <nav
        className={`flex-1 space-y-xs ${collapsed ? "px-sm" : "px-md"}`}
        aria-label="Console"
      >
        {NAV_ITEMS.map(({ label, icon, href }) => {
          const isActive =
            pathname === href || pathname?.startsWith(href + "/");
          return (
            <Link
              key={label}
              href={href}
              title={collapsed ? label : undefined}
              className={`flex items-center rounded-full font-semibold transition-all ${
                collapsed
                  ? "justify-center px-sm py-sm"
                  : "gap-md px-md py-sm"
              } ${
                isActive
                  ? "bg-secondary-container text-on-secondary-container"
                  : "text-on-surface-variant hover:bg-surface-variant"
              }`}
            >
              <Icon name={icon} filled={isActive} size={20} />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Profile footer */}
      <div
        className={`mt-auto border-t border-outline-variant ${
          collapsed ? "p-sm" : "p-lg"
        }`}
      >
        <div
          className={`flex items-center ${
            collapsed ? "justify-center" : "gap-md"
          }`}
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-primary bg-surface-container">
            <Icon
              name="person"
              size={22}
              className="text-on-surface-variant"
            />
          </div>
          {!collapsed && (
            <div>
              <p className="font-bold leading-tight text-on-surface">
                Kofi Mensah
              </p>
              <p className="text-xs text-on-surface-variant">Lead Architect</p>
            </div>
          )}
        </div>
      </div>
    </>
  );

  return (
    // h-full fills the flex content area given by app/(app)/layout.tsx
    <div className="relative flex h-full overflow-hidden bg-[#F1F4F9] text-on-surface">
      {/* ----------------------------------------------------------------
          Mobile hamburger button (< md)
          Positioned absolutely so it doesn't push page content.
      ---------------------------------------------------------------- */}
      <button
        type="button"
        onClick={openDrawer}
        aria-label="Open navigation"
        className="absolute left-3 top-3 z-30 flex h-10 w-10 items-center justify-center rounded-full bg-surface shadow-md md:hidden"
      >
        <Icon name="menu" size={22} />
      </button>

      {/* ----------------------------------------------------------------
          Mobile overlay drawer (< md)
          Slides in from the left with a backdrop scrim.
      ---------------------------------------------------------------- */}
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 md:hidden ${
          mobileOpen
            ? "pointer-events-auto opacity-100"
            : "pointer-events-none opacity-0"
        }`}
        onClick={closeDrawer}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-surface shadow-xl transition-transform duration-300 ease-in-out md:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Close button inside drawer */}
        <button
          type="button"
          onClick={closeDrawer}
          aria-label="Close navigation"
          className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-variant"
        >
          <Icon name="close" size={20} />
        </button>

        {sidebarContent(false)}
      </aside>

      {/* ----------------------------------------------------------------
          Persistent Research Console sidebar — tablet & desktop
          • md → lg : Collapsed icon-only rail (w-[72px])
          • lg+      : Full w-64 sidebar with labels
          Hidden on mobile where the overlay drawer is used instead.
          No `hidden md:flex` — always visible. The console is a desktop-first
          admin tool; the main app BottomTabNav (which is already `md:flex-row`)
          handles top-level routing, so a persistent second sidebar here is fine.
      ---------------------------------------------------------------- */}
      <aside className="hidden shrink-0 flex-col border-r border-outline-variant bg-surface md:flex md:w-[72px] lg:w-64">
        {/* Render collapsed on md–lg, full on lg+ via two layers */}
        {/* Collapsed (tablet: md–lg) */}
        <div className="flex h-full flex-col lg:hidden">
          {sidebarContent(true)}
        </div>
        {/* Expanded (desktop: lg+) */}
        <div className="hidden h-full flex-col lg:flex">
          {sidebarContent(false)}
        </div>
      </aside>

      {/* Page content — fills remaining width, manages its own scroll */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
