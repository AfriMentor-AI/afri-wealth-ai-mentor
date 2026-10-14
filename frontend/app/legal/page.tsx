import Link from "next/link";
import { Icon } from "@/components/Icon";
import { ThemeToggleButton } from "@/components/ThemeSwitch";

export const metadata = { title: "Privacy & Terms · AfriMentor AI" };

const INDEX = [
  ["privacy", "1. Your data and privacy"],
  ["voice", "2. Voice and audio"],
  ["ethics", "3. How mentors behave"],
  ["groups", "4. Savings circles and group finance"],
  ["terms", "5. Terms of use and disclaimer"],
];

function H({ id, children }: { id: string; children: React.ReactNode }) {
  return <h2 id={id} className="mt-10 scroll-mt-24 font-title-md text-[26px] leading-8 text-on-surface">{children}</h2>;
}
const P = ({ children }: { children: React.ReactNode }) => <p className="mt-3 font-body-md text-body-md text-on-surface-variant">{children}</p>;

export default function LegalPage() {
  return (
    <div className="min-h-screen bg-warm-white text-on-surface">
      <header className="sticky top-0 z-30 border-b border-outline-variant/60 bg-warm-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 md:px-10">
          <Link href="/" className="font-title-md text-[22px] text-on-surface">AfriMentor AI</Link>
          <div className="flex items-center gap-3">
            <Link href="/chat" className="hidden items-center gap-1 font-label-sm text-label-sm text-primary hover:underline sm:flex"><Icon name="arrow_back" size={16} /> Back to workspace</Link>
            <ThemeToggleButton />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 md:px-10 lg:grid-cols-[260px_1fr]">
        <aside className="hidden lg:block">
          <nav aria-label="Contents" className="sticky top-24 rounded-2xl border border-outline-variant bg-surface-container-low p-5">
            <p className="flex items-center gap-2 font-eyebrow text-eyebrow uppercase text-on-surface-variant"><Icon name="list" size={16} /> Contents</p>
            <ul className="mt-3 space-y-2">
              {INDEX.map(([id, label]) => <li key={id}><a href={`#${id}`} className="font-body-md text-[14px] text-on-surface hover:text-primary">{label}</a></li>)}
            </ul>
          </nav>
        </aside>

        <article className="min-w-0 rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm md:p-10">
          <p className="font-eyebrow text-eyebrow uppercase text-sunburst-gold">Legal framework · Data dignity pledge</p>
          <h1 className="mt-3 font-headline-xl-mobile text-headline-xl-mobile text-on-surface md:font-headline-lg md:text-[40px] md:leading-[48px]">Privacy policy &amp; terms of use</h1>
          <span className="kente-band mt-4 block h-1 w-full rounded-full" />
          <p className="mt-6 font-quote text-[20px] italic leading-8 text-on-surface-variant">“The wealth of our markets lies not only in the goods exchanged, but in the trust and privacy of the ledger.”</p>
          <p className="mt-4 rounded-xl bg-gold-mist px-4 py-3 font-caption text-caption text-on-surface">This page summarises how the product treats your information. It is a plain-language summary and should be reviewed and finalised by your organisation’s legal counsel before public launch.</p>

          <H id="privacy">1. Your data and privacy</H>
          <P>AfriMentor AI uses the information you give it — your intake answers, goals, milestones, conversations and activity — to personalise guidance and to show your progress. It is stored against your account and used to operate the service.</P>
          <P>You can review and change your profile and goals in the app. Contact the service operator to request export or deletion of your data.</P>

          <H id="voice">2. Voice and audio</H>
          <P>If you use voice input, your recording is sent to the voice service to be transcribed into text, and mentor replies can be read aloud. Allow microphone access only when you want to speak; you can type instead at any time.</P>

          <H id="ethics">3. How mentors behave</H>
          <ul className="mt-3 space-y-2">
            {["Guidance is educational and aims to support your long-term stability over quick wins.", "Mentors cite the trade knowledge they draw on where it is available.", "You decide what to do. Nothing a mentor says obliges you to act."].map((t) => (
              <li key={t} className="flex items-start gap-2 font-body-md text-body-md text-on-surface-variant"><Icon name="check_circle" size={20} className="mt-0.5 shrink-0 text-primary" />{t}</li>
            ))}
          </ul>

          <H id="groups">4. Savings circles and group finance</H>
          <P>Mentors may explain rotating savings circles (susu, tontines, esusu) and similar arrangements. AfriMentor AI does not hold money, act as an escrow or deposit-taking institution, or arbitrate disputes between members.</P>

          <H id="terms">5. Terms of use and disclaimer</H>
          <P>Mentors are AI personas inspired by African trade traditions. They are not licensed financial, legal or tax advisers. Content is general information, may contain mistakes, and should be checked with a qualified professional before you make significant financial decisions.</P>
          <P>By using the service you agree to use it lawfully, to keep your sign-in details private, and to treat other people’s information with respect.</P>
        </article>
      </div>

      <footer className="border-t border-outline-variant/60 bg-surface-container-low">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 md:px-10">
          <p className="font-caption text-caption text-on-surface-variant">AfriMentor AI — rooted in tradition, built for growth.</p>
          <div className="flex gap-4 font-caption text-caption"><a href="#privacy" className="hover:text-primary">Privacy</a><a href="#terms" className="hover:text-primary">Terms</a></div>
        </div>
      </footer>
    </div>
  );
}
