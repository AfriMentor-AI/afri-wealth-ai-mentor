"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { SankofaMotif } from "@/components/SankofaMotif";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/Icon";
import { DesktopLanding } from "@/components/DesktopLanding";

const mobileSlides = [
  {
    type: "splash" as const,
    headline: "Your journey to financial independence, guided by those who have walked the path.",
  },
  {
    type: "feature" as const,
    icon: "menu_book",
    headline: "Guidance sourced from Africa",
    body: "Every answer draws on content written by African founders, traders, and builders — not generic advice.",
  },
  {
    type: "feature" as const,
    icon: "task_alt",
    headline: "One action a day",
    body: "No overwhelming plans. Just the next concrete step, chosen with you, every day.",
  },
];

const DEVICE_ID_KEY = "afrimentor-device-id";

function isDeviceRegistered(): boolean {
  return !!localStorage.getItem(DEVICE_ID_KEY);
}

export default function SplashPage() {
  const router = useRouter();
  const [slide, setSlide] = useState(0);
  const [returning, setReturning] = useState(false);
  const isLast = slide === mobileSlides.length - 1;
  const current = mobileSlides[slide];

  useEffect(() => {
    setReturning(isDeviceRegistered());
  }, []);

  return (
    <main className="relative min-h-screen bg-surface">
      {/* Desktop View: Full Landing Screen (splash_welcome_screen_desktop) */}
      <div className="hidden md:block">
        <DesktopLanding />
      </div>

      {/* Mobile View: Splash & Intro Carousel (splash_welcome_screen) */}
      <div className="relative mx-auto flex min-h-screen max-w-md flex-col justify-between overflow-x-hidden px-margin-mobile pb-xl pt-md md:hidden">
        <div className="sankofa-bg -right-[10%] top-[10%] w-[120%] -rotate-12 text-primary" aria-hidden>
          <SankofaMotif size={480} />
        </div>

        <ThemeToggle className="absolute right-margin-mobile top-md z-20" />

        <div className="relative z-10 mx-auto flex w-full max-w-lg flex-1 flex-col justify-center pb-lg pt-md">
          {current.type === "splash" ? (
            <>
              <div className="mb-xl text-center">
                <div className="mb-md inline-flex animate-bounce items-center justify-center rounded-full bg-primary-container p-sm">
                  <Icon name="psychology" filled size={48} className="text-on-primary-container" />
                </div>
                <h1 className="font-headline-xl text-headline-xl tracking-tight text-primary">CHIOMA</h1>
                <p className="font-title-md text-title-md font-bold uppercase tracking-widest text-primary opacity-80">
                  AfriMentor AI
                </p>
              </div>

              <div className="relative mb-xl aspect-[4/5] max-h-[45vh] w-full overflow-hidden rounded border border-outline-variant/30 shadow-sm">
                <Image
                  src="/images/chioma-avatar.png"
                  alt="Chioma, your AI mentor, in her home"
                  fill
                  className="object-cover"
                  priority
                />
                <div className="absolute inset-0 z-10 bg-gradient-to-t from-black/50 to-transparent" />
                <div className="absolute bottom-md left-md right-md z-20">
                  <div className="rounded-lg border-l-4 border-primary bg-black/70 p-md shadow-lg backdrop-blur-sm">
                    <p className="font-body-lg text-body-lg leading-tight text-white">
                      &ldquo;Welcome, child. Let us build your legacy together.&rdquo;
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-md">
                <h2 className="font-headline-lg-mobile text-headline-lg-mobile px-sm text-center text-on-background">
                  {current.headline}
                </h2>
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center text-center" aria-live="polite">
              <div className="mb-md inline-flex items-center justify-center rounded-full bg-primary-container p-lg">
                <Icon name={current.icon} filled size={48} className="text-on-primary-container" />
              </div>
              <h2 className="font-headline-lg-mobile text-headline-lg-mobile px-sm text-on-background">
                {current.headline}
              </h2>
              <p className="mt-sm max-w-xs font-body-md text-body-md text-on-surface-variant">{current.body}</p>
            </div>
          )}
        </div>

        <footer className="relative z-10 bg-gradient-to-t from-surface via-surface to-transparent pt-md">
          <div className="mb-lg flex justify-center gap-xs">
            {mobileSlides.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  i === slide ? "w-6 bg-primary" : "w-1.5 bg-primary/30"
                }`}
              />
            ))}
          </div>

          {returning && slide === 0 ? (
            <Button
              variant="cta"
              className="h-14 w-full text-[20px]"
              onClick={() => router.push("/chat")}
            >
              Continue to Chat
              <Icon name="arrow_forward" />
            </Button>
          ) : (
            <Button
              variant="cta"
              className="h-14 w-full text-[20px]"
              onClick={() => (isLast ? router.push("/intake") : setSlide((s) => s + 1))}
            >
              {slide === 0 ? "Get Started" : isLast ? "Tell us about your business" : "Continue"}
              <Icon name="arrow_forward" />
            </Button>
          )}
          <p className="mt-md text-center font-label-sm text-label-sm text-on-surface-variant/70">
            Secure • Communal • Tailored for You
          </p>
        </footer>
      </div>
    </main>
  );
}
