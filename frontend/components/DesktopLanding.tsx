"use client";

import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { SankofaMotif } from "@/components/SankofaMotif";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";

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

export function DesktopLanding() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-surface">
      <header className="fixed left-0 right-0 top-0 z-50 flex h-20 items-center border-b border-outline-variant/60 bg-surface/80 px-xl backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-[1440px] items-center justify-between">
          <div className="flex items-center gap-md">
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
          <div className="flex items-center gap-md">
            <ThemeToggle />
            <Button
              variant="secondary"
              className="h-10 px-md text-[14px]"
              onClick={() => router.push("/persona")}
            >
              Mentors
            </Button>
            <Button
              variant="primary"
              className="h-10 px-lg text-[14px]"
              onClick={() => router.push("/intake")}
            >
              Get Started
            </Button>
          </div>
        </div>
      </header>

      <section className="mx-auto flex min-h-[calc(100vh-80px)] max-w-[1440px] items-center gap-xl px-xl pt-24 pb-xl">
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
            <Button
              variant="cta"
              className="h-14 px-xl text-[18px]"
              onClick={() => router.push("/intake")}
            >
              Get Started
              <Icon name="arrow_forward" />
            </Button>
            <Button
              variant="secondary"
              className="h-14 px-xl text-[18px]"
              onClick={() => router.push("/persona")}
            >
              Explore Mentors
            </Button>
          </div>
        </div>
        <div className="relative hidden w-1/2 items-center justify-center lg:flex">
          <SankofaMotif size={360} className="text-primary/15" />
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
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-xl">
          <div className="flex items-center gap-sm">
            <Icon name="spa" className="text-primary" />
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              AfriMentor AI. Rooted in tradition, powered by future.
            </span>
          </div>
          <div className="flex items-center gap-lg">
            <span className="font-label-sm text-label-sm text-on-surface-variant/70">
              Secure • Communal • Tailored for You
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

