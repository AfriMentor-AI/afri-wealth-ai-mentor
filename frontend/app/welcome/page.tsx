"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { SankofaMotif } from "@/components/SankofaMotif";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";

// The Stitch export bundles Splash + Welcome into a single file with a
// 3-dot pagination indicator, implying a short swipeable intro carousel.
// This screen is that carousel's remaining slides (slide 1's content —
// the "walked the path" headline — lives on the Splash screen itself).
const slides = [
  {
    icon: "menu_book",
    headline: "Guidance sourced from Africa",
    body: "Every answer draws on content written by African founders, traders, and builders — not generic advice.",
  },
  {
    icon: "task_alt",
    headline: "One action a day",
    body: "No overwhelming plans. Just the next concrete step, chosen with you, every day.",
  },
];

// The desktop mockup (splash_welcome_screen_desktop) is a full marketing
// landing page — different copy, a stock-photo hero, and a "12,000+ users"
// stat — not just a wider version of the mobile carousel. Structure and
// copy are reproduced faithfully; the stock photos and the fabricated user
// count are left out (no real numbers to show, and no other screen in this
// codebase hotlinks the mockup's placeholder images either).
const desktopFeatures = [
  {
    icon: "menu_book",
    title: "Cultural Context",
    body: "AI that understands local nuances, languages, and traditional savings practices like Susu and Esusu.",
  },
  {
    icon: "handshake",
    title: "Trusted Mentorship",
    body: "A mentor grounded in African business wisdom, dedicated to your long-term success and dignity.",
  },
  {
    icon: "insights",
    title: "Data-Driven Growth",
    body: "Smart tracking of your milestones with actionable steps toward your specific goals.",
  },
];

export default function WelcomePage() {
  const router = useRouter();
  const [slide, setSlide] = useState(0);
  const isLast = slide === slides.length - 1;
  const current = slides[slide];

  return (
    <main className="relative min-h-screen bg-surface">
      <ThemeToggle className="absolute right-margin-mobile top-md z-20 md:right-xl md:top-lg" />

      {/* Mobile: swipeable carousel */}
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-between px-margin-mobile py-xl md:hidden">
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <div className="mb-md inline-flex items-center justify-center rounded-full bg-primary-container p-lg">
            <Icon name={current.icon} filled size={48} className="text-on-primary-container" />
          </div>
          <h1 className="font-headline-lg-mobile text-headline-lg-mobile px-sm text-on-background">
            {current.headline}
          </h1>
          <p className="mt-sm max-w-xs font-body-md text-body-md text-on-surface-variant">{current.body}</p>
        </div>

        <div>
          <div className="mb-lg flex justify-center gap-xs">
            {slides.map((_, i) => (
              <span key={i} className={`h-1.5 rounded-full transition-all ${i === slide ? "w-6 bg-primary" : "w-1.5 bg-primary/30"}`} />
            ))}
          </div>
          <Button
            variant="cta"
            className="h-14 w-full text-[20px]"
            onClick={() => (isLast ? router.push("/intake") : setSlide((s) => s + 1))}
          >
            {isLast ? "Tell us about your business" : "Continue"}
            <Icon name="arrow_forward" />
          </Button>
        </div>
      </div>

      {/* Desktop: full landing page (splash_welcome_screen_desktop) */}
      <div className="hidden md:block">
        <header className="fixed left-0 right-0 top-0 z-10 flex h-20 items-center border-b border-outline-variant/60 bg-surface/80 px-xl backdrop-blur-md">
          <div className="mx-auto flex w-full max-w-[1440px] items-center gap-md">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary-container text-on-primary-container">
              <Icon name="psychology" size={32} />
            </div>
            <div>
              <h2 className="font-headline-lg text-headline-lg text-primary">AfriMentor AI</h2>
              <p className="-mt-1 font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
                Dignified Growth
              </p>
            </div>
          </div>
        </header>

        <section className="mx-auto flex min-h-screen max-w-[1440px] items-center gap-xl px-xl pt-20">
          <div className="flex w-full flex-col gap-lg lg:w-1/2">
            <div className="inline-flex w-fit items-center gap-sm rounded-full bg-secondary-container/30 px-md py-xs text-on-secondary-container">
              <Icon name="verified" size={18} />
              <span className="font-label-sm text-label-sm">Communal Wisdom Powered by AI</span>
            </div>
            <h1 className="font-headline-xl text-headline-xl leading-tight text-on-surface">
              Empowering Your Financial Journey with <span className="text-primary">Trusted Guidance</span>.
            </h1>
            <p className="max-w-lg font-body-lg text-body-lg text-on-surface-variant">
              A mentor grounded in West African heritage and modern financial intelligence — the next concrete
              step, chosen with you, every day.
            </p>
            <div className="flex flex-col gap-md pt-md sm:flex-row">
              <Button variant="primary" className="h-14 px-xl text-[16px]" onClick={() => router.push("/intake")}>
                Get Started
                <Icon name="arrow_forward" />
              </Button>
            </div>
          </div>
          <div className="relative hidden w-1/2 items-center justify-center lg:flex">
            <SankofaMotif size={280} className="text-primary/10" />
          </div>
        </section>

        <section className="border-t border-outline-variant bg-surface-container-low py-xl">
          <div className="mx-auto grid max-w-[1440px] grid-cols-1 gap-lg px-xl md:grid-cols-3">
            {desktopFeatures.map((f) => (
              <div key={f.title} className="flex flex-col gap-md rounded-xl border border-outline-variant bg-surface p-lg">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-secondary-container text-on-secondary-container">
                  <Icon name={f.icon} />
                </div>
                <h3 className="font-title-md text-title-md text-on-surface">{f.title}</h3>
                <p className="font-body-md text-body-md text-on-surface-variant">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        <footer className="border-t border-outline-variant py-lg">
          <div className="mx-auto flex max-w-[1440px] items-center justify-center gap-sm px-xl">
            <Icon name="spa" className="text-primary" />
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              AfriMentor AI. Rooted in tradition, powered by future.
            </span>
          </div>
        </footer>
      </div>
    </main>
  );
}
