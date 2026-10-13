import { DesktopLanding } from "@/components/landing/DesktopLanding";
import { MobileSplash } from "@/components/landing/MobileSplash";

export default function LandingPage() {
  return (
    <main>
      <div className="hidden md:block"><DesktopLanding /></div>
      <div className="md:hidden"><MobileSplash /></div>
    </main>
  );
}
