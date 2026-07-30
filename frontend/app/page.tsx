"use client";

import { useRouter } from "next/navigation";
import { SankofaMotif } from "@/components/SankofaMotif";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";

export default function SplashPage() {
  const router = useRouter();

  return (
    <main className="relative mx-auto flex min-h-screen max-w-md flex-col justify-between overflow-x-hidden bg-surface">
      <div className="sankofa-bg -right-[10%] top-[10%] w-[120%] -rotate-12 text-primary" aria-hidden>
        <SankofaMotif size={480} />
      </div>

      <ThemeToggle className="absolute right-margin-mobile top-md z-20" />

      <div className="relative z-10 mx-auto flex w-full max-w-lg flex-1 flex-col justify-center px-margin-mobile pb-lg pt-xl">
        <div className="mb-xl text-center">
          <div className="mb-md inline-flex animate-bounce items-center justify-center rounded-full bg-primary-container p-sm">
            <Icon name="psychology" filled size={48} className="text-on-primary-container" />
          </div>
          <h1 className="font-headline-xl text-headline-xl tracking-tight text-primary">CHIOMA</h1>
          <p className="font-title-md text-title-md font-bold uppercase tracking-widest text-primary opacity-80">
            AfriMentor AI
          </p>
        </div>

        <div className="relative mb-xl aspect-[4/5] max-h-[45vh] w-full overflow-hidden rounded border border-outline-variant/30 bg-gradient-to-br from-primary-container to-secondary-container shadow-sm">
          <div className="absolute inset-0 z-10 bg-gradient-to-t from-primary/40 to-transparent" />
          <div className="absolute bottom-md left-md right-md z-20">
            <div className="rounded-lg border-l-4 border-primary bg-surface-bright/95 p-md shadow-lg backdrop-blur-sm">
              <p className="font-body-lg text-body-lg leading-tight text-on-surface-variant">
                &ldquo;Welcome, child. Let us build your legacy together.&rdquo;
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-md">
          <h2 className="font-headline-lg-mobile text-headline-lg-mobile px-sm text-center text-on-background">
            Your journey to financial independence, guided by those who have walked the path.
          </h2>
          <div className="flex justify-center gap-xs">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            <span className="h-1.5 w-1.5 rounded-full bg-primary/30" />
            <span className="h-1.5 w-1.5 rounded-full bg-primary/30" />
          </div>
        </div>
      </div>

      <footer className="relative z-10 bg-gradient-to-t from-surface via-surface to-transparent px-margin-mobile pb-xl pt-md">
        <Button variant="cta" className="h-14 w-full text-[20px]" onClick={() => router.push("/welcome")}>
          Get Started
          <Icon name="arrow_forward" />
        </Button>
        <p className="mt-md text-center font-label-sm text-label-sm text-on-surface-variant/70">
          Secure • Communal • Tailored for You
        </p>
      </footer>
    </main>
  );
}
