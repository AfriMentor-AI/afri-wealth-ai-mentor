import Link from "next/link";
import { Icon } from "@/components/Icon";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-warm-white px-5 py-16 text-on-surface">
      <div className="relative w-full max-w-xl overflow-hidden rounded-3xl border border-outline-variant bg-surface-container-low p-8 text-center shadow-sm md:p-12">
        <span className="kente-band absolute inset-x-0 top-0 h-1.5" />
        <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-gold-mist text-sunburst-gold"><Icon name="explore_off" size={32} /></span>
        <p className="mt-5 font-eyebrow text-eyebrow uppercase text-error">Status 404 · Route uncharted</p>
        <h1 className="mt-3 font-headline-xl-mobile text-headline-xl-mobile text-on-surface md:font-headline-lg md:text-[40px] md:leading-[48px]">We couldn’t find that trade corridor</h1>
        <p className="mx-auto mt-3 max-w-md font-body-md text-body-md text-on-surface-variant">The page you asked for has moved or never existed. Let us guide you back to familiar trading ground.</p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/chat" className="flex h-12 items-center gap-2 rounded-full bg-sunburst-gold px-8 font-label-sm text-[15px] font-bold text-ink shadow-md">Back to chat <Icon name="arrow_forward" size={18} /></Link>
          <Link href="/" className="flex h-12 items-center rounded-full border border-outline px-8 font-label-sm text-[15px] text-on-surface hover:bg-surface-container">Home</Link>
        </div>
      </div>
    </main>
  );
}
