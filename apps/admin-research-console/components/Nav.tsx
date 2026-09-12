"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearSession, currentUser, type ConsoleRole } from "@/lib/session";

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Persona Consistency", icon: "analytics" },
  { href: "/corpus-admin", label: "RAG Corpus Admin", icon: "folder_shared" },
];

function formatRole(roles?: string[]): string {
  if (!roles || roles.length === 0) return "Researcher";
  if (roles.includes("lead_architect")) return "Lead Architect";
  if (roles.includes("admin")) return "Lead Architect / Admin";
  if (roles.includes("researcher")) return "Research Scientist";
  return roles[0].replace(/_/g, " ");
}

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [userRole, setUserRole] = useState("Lead Architect");
  const [userId, setUserId] = useState("Kofi Mensah");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const user = currentUser();
    if (user) {
      setUserRole(formatRole(user.roles));
      if (user.id) {
        setUserId(user.id.includes("@") ? user.id.split("@")[0] : user.id.length > 16 ? user.id.slice(0, 12) : user.id);
      }
    }
  }, []);

  function handleSignOut() {
    clearSession();
    router.replace("/login");
  }

  const sidebarBody = (
    <div className="flex h-full flex-col">
      {/* Brand Header */}
      <div className="flex items-center gap-md px-lg py-xl">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-on-primary shadow-sm">
          <span className="material-symbols-outlined text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
            account_tree
          </span>
        </div>
        <div>
          <h1 className="font-headline font-bold text-lg text-primary tracking-tight leading-none">
            AfriMentor
          </h1>
          <p className="mt-1 font-label-sm text-[10px] uppercase tracking-widest text-on-surface-variant opacity-70">
            Research Console
          </p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 space-y-xs px-md">
        <div className="px-md py-xs text-[11px] font-bold uppercase tracking-widest text-on-surface-variant/60">
          Management
        </div>
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={`flex items-center gap-md px-md py-sm rounded-full text-sm font-semibold transition-all ${
                isActive
                  ? "bg-secondary-container text-on-secondary-container shadow-xs"
                  : "text-on-surface-variant hover:bg-surface-variant/80"
              }`}
            >
              <span
                className="material-symbols-outlined text-xl"
                style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
              >
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User Profile & Sign Out Footer */}
      <div className="p-md mt-auto border-t border-outline-variant/60">
        <div className="flex items-center justify-between rounded-2xl bg-surface-container-high/60 p-sm border border-outline-variant/40">
          <div className="flex items-center gap-sm min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-container text-on-primary-container border-2 border-primary font-bold text-xs">
              {userId.slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-bold text-on-surface leading-tight">{userId}</p>
              <p className="truncate text-[10px] text-on-surface-variant font-medium">{userRole}</p>
            </div>
          </div>
          <button
            onClick={handleSignOut}
            title="Sign out"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-variant transition-colors"
          >
            <span className="material-symbols-outlined text-lg">logout</span>
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside className="hidden md:flex w-64 lg:w-72 shrink-0 flex-col bg-surface border-r border-outline-variant h-screen sticky top-0 z-30">
        {sidebarBody}
      </aside>

      {/* Mobile Top Bar + Drawer Toggle */}
      <div className="md:hidden flex items-center justify-between bg-surface px-md py-sm border-b border-outline-variant shrink-0 z-40">
        <div className="flex items-center gap-sm">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-on-primary">
            <span className="material-symbols-outlined text-lg">account_tree</span>
          </div>
          <span className="font-headline font-bold text-sm text-primary">AfriMentor Console</span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-variant"
        >
          <span className="material-symbols-outlined">{mobileOpen ? "close" : "menu"}</span>
        </button>
      </div>

      {/* Mobile Drawer Backdrop and Aside */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs md:hidden"
          onClick={() => setMobileOpen(false)}
        >
          <div
            className="w-72 h-full bg-surface border-r border-outline-variant shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {sidebarBody}
          </div>
        </div>
      )}
    </>
  );
}
