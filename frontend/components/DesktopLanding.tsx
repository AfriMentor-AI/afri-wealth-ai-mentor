"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";
import { isIntakeCompleted } from "@/lib/session";

const desktopFeatures = [
  {
    icon: "menu_book",
    iconBg: "bg-secondary-container text-on-secondary-container",
    title: "Cultural Context",
    body: "AI that understands local nuances, languages, and traditional savings practices like Susu and Esusu.",
  },
  {
    icon: "handshake",
    iconBg: "bg-primary-fixed-dim text-on-primary-fixed-variant",
    title: "Trusted Mentorship",
    body: "A mentor grounded in African business wisdom, dedicated to your long-term success and dignity.",
  },
  {
    icon: "insights",
    iconBg: "bg-tertiary-container text-on-tertiary-container",
    title: "Data-Driven Growth",
    body: "Smart tracking of your milestones with actionable steps toward your specific goals.",
  },
];

export function DesktopLanding() {
  const router = useRouter();
  const [returning, setReturning] = useState(false);

  useEffect(() => {
    setReturning(isIntakeCompleted());
  }, []);

  return (
    <div className="min-h-screen bg-surface">
      {/* Ambient atmosphere blobs */}
      <div className="fixed top-20 right-10 w-64 h-64 bg-primary-fixed-dim/10 blur-[100px] rounded-full -z-10 animate-pulse" />
      <div className="fixed bottom-20 left-10 w-96 h-96 bg-secondary-fixed-dim/10 blur-[120px] rounded-full -z-10" />

      {/* Nav */}
      <header className="fixed left-0 right-0 top-0 z-50 h-20 border-b border-outline-variant/60 bg-surface/80 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[1440px] items-center justify-between px-xl">
          <div className="flex items-center gap-md">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-container text-on-primary-container">
              <Icon name="psychology" size={32} />
            </div>
            <div>
              <h1 className="font-headline-lg text-headline-lg tracking-tight text-primary">AfriMentor AI</h1>
              <p className="-mt-1 font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
                Dignified Growth
              </p>
            </div>
          </div>
          <div className="flex items-center gap-xl">
            <nav className="hidden items-center gap-xl md:flex">
              <a className="font-label-sm text-label-sm text-on-surface-variant transition-colors hover:text-primary" href="#">About</a>
              <a className="font-label-sm text-label-sm text-on-surface-variant transition-colors hover:text-primary" href="#" onClick={(e) => { e.preventDefault(); router.push("/persona"); }}>Mentors</a>
              <a className="font-label-sm text-label-sm text-on-surface-variant transition-colors hover:text-primary" href="#">Support</a>
            </nav>
            <ThemeToggle />
            <Button
              variant="primary"
              className="h-10 px-lg text-[14px]"
              onClick={() => router.push(returning ? "/chat" : "/intake")}
            >
              {returning ? "Continue" : "Get Started"}
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="relative flex min-h-screen flex-col overflow-hidden pt-20">
        <section className="relative mx-auto flex w-full max-w-[1440px] flex-grow items-center px-xl py-xl">

          {/* Content — sits on top of the gradient fade */}
          <div className="relative z-10 flex w-full flex-col gap-lg md:w-1/2">
            <div className="inline-flex w-fit items-center gap-sm rounded-full bg-secondary-container/30 px-md py-xs text-on-secondary-container">
              <Icon name="verified" size={18} />
              <span className="font-label-sm text-label-sm">Communal Wisdom Powered by AI</span>
            </div>

            <h2 className="max-w-md font-headline-xl text-headline-xl leading-tight text-on-surface">
              Empowering Your Financial Journey with{" "}
              <span className="text-primary">Trusted Guidance</span>.
            </h2>

            <p className="max-w-lg font-body-lg text-body-lg text-on-surface-variant">
              Like a mentor sitting across from you, AfriMentor AI blends West African heritage
              with modern financial intelligence to help you flourish.
            </p>

            <div className="flex flex-col gap-md pt-md sm:flex-row">
              <Button
                variant="cta"
                className="h-14 px-xl text-[18px]"
                onClick={() => router.push(returning ? "/chat" : "/intake")}
              >
                {returning ? "Continue to Chat" : "Get Started"}
                <Icon name="arrow_forward" />
              </Button>
              <Button
                variant="secondary"
                className="h-14 px-xl text-[18px]"
                onClick={() => router.push("/persona")}
              >
                <Icon name="play_circle" />
                Explore Mentors
              </Button>
            </div>

            {/* Social proof */}
            <div className="mt-xl flex items-center gap-lg border-t border-outline-variant pt-lg">
              <div className="flex -space-x-3">
                {["bg-primary-fixed-dim", "bg-secondary-fixed", "bg-tertiary-fixed"].map((bg, i) => (
                  <div
                    key={i}
                    className={`flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border-2 border-surface ${bg}`}
                  >
                    <Icon name="person" size={20} className="text-on-surface-variant" />
                  </div>
                ))}
              </div>
              <p className="font-label-sm text-label-sm text-on-surface-variant">
                Joined by <span className="font-bold text-on-surface">12,000+</span> seekers of growth across the continent.
              </p>
            </div>
          </div>

          {/* sage.jpg — absolute right, overlapping, with gradient fade */}
          <div className="absolute right-0 top-0 hidden h-full w-3/5 select-none md:block">
            {/* gradient fade: surface → transparent, matching stitch hero-gradient */}
            <div className="absolute inset-0 z-10 bg-gradient-to-r from-surface via-surface/60 to-transparent" />
            <div className="h-full w-full overflow-hidden rounded-bl-[120px] bg-surface-container">
              <Image
                src="/images/sage.jpg"
                alt="A wise African mentor"
                fill
                className="scale-105 object-cover object-center opacity-90 dark:opacity-60"
                priority
              />
            </div>
            {/* Decorative Sankofa dot pattern bottom-right */}
            <div className="absolute bottom-xl right-xl z-20 h-32 w-32 opacity-20">
              <svg viewBox="0 0 60 60" className="h-full w-full text-primary" fill="currentColor">
                <path d="M30 5c-5 0-9 4-9 9s4 9 9 9 9-4 9-9-4-9-9-9zm0 14c-2.8 0-5-2.2-5-5s2.2-5 5-5 5 2.2 5 5-2.2 5-5 5zm0 10c-11 0-20 9-20 20h5c0-8.3 6.7-15 15-15s15 6.7 15 15h5c0-11-9-20-20-20z" />
              </svg>
            </div>
          </div>
        </section>

        {/* Feature cards */}
        <section className="border-t border-outline-variant bg-surface-container-low py-xl">
          <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-lg px-xl md:grid-cols-3">
            {desktopFeatures.map((f) => (
              <div
                key={f.title}
                className="flex flex-col gap-md rounded-xl border border-outline-variant bg-surface p-lg transition-all hover:-translate-y-1 hover:shadow-md"
              >
                <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${f.iconBg}`}>
                  <Icon name={f.icon} />
                </div>
                <h3 className="font-title-md text-title-md text-on-surface">{f.title}</h3>
                <p className="font-body-md text-body-md text-on-surface-variant">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-auto border-t border-outline-variant py-lg">
          <div className="mx-auto flex max-w-[1440px] flex-col items-center justify-between gap-md px-xl md:flex-row">
            <div className="flex items-center gap-sm">
              <Icon name="spa" className="text-primary" />
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                © 2024 AfriMentor AI. Rooted in tradition, powered by future.
              </span>
            </div>
            <div className="flex gap-lg">
              <a className="font-label-sm text-label-sm text-on-surface-variant transition-colors hover:text-primary" href="#">Privacy Policy</a>
              <a className="font-label-sm text-label-sm text-on-surface-variant transition-colors hover:text-primary" href="#">Terms of Service</a>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}
