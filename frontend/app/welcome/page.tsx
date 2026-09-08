"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";
import { DesktopLanding } from "@/components/DesktopLanding";
import { isIntakeCompleted } from "@/lib/session";

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

export default function WelcomePage() {
  const router = useRouter();
  const [slide, setSlide] = useState(0);
  const isLast = slide === slides.length - 1;
  const current = slides[slide];

  return (
    <main className="relative min-h-screen bg-surface">
      {/* Desktop: full landing page (splash_welcome_screen_desktop) */}
      <div className="hidden md:block">
        <DesktopLanding />
      </div>

      {/* Mobile: swipeable carousel */}
      <div className="relative mx-auto flex min-h-screen max-w-md flex-col justify-between px-margin-mobile py-xl md:hidden">
        <ThemeToggle className="absolute right-margin-mobile top-md z-20" />

        <div className="flex flex-1 flex-col items-center justify-center text-center" aria-live="polite">
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
              <span
                key={i}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  i === slide ? "w-6 bg-primary" : "w-1.5 bg-primary/30"
                }`}
              />
            ))}
          </div>
          <Button
            variant="cta"
            className="h-14 w-full text-[20px]"
            onClick={() =>
              isIntakeCompleted()
                ? router.push("/chat")
                : isLast
                ? router.push("/intake")
                : setSlide((s) => s + 1)
            }
          >
            {isIntakeCompleted() ? "Continue to Chat" : isLast ? "Tell us about your business" : "Continue"}
            <Icon name="arrow_forward" />
          </Button>
        </div>
      </div>
    </main>
  );
}
