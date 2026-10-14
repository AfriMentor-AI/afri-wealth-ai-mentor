"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ThemeToggleButton } from "@/components/ThemeSwitch";
import { KenteStrip } from "@/components/shell/AppSidebar";
import { useAppDispatch } from "@/lib/store";
import { submitIntake } from "@/lib/api";
import { markIntakeCompleted } from "@/lib/session";
import { startAudioRecording, type ActiveRecording } from "@/lib/voice";
import { MENTORS } from "@/lib/mentors";
import { img } from "@/lib/stitchImages";

const SECTORS_LIST = [
  { name: "Trader", icon: "storefront", desc: "Retail shops, market trading, imports/exports" },
  { name: "Tech", icon: "computer", desc: "Software, digital services, web development" },
  { name: "Fashion/Retail", icon: "checkroom", desc: "Apparel, textiles, boutiques, tailoring" },
  { name: "Agriculture", icon: "agriculture", desc: "Farming, agro-processing, livestock" },
  { name: "Creative", icon: "palette", desc: "Design, crafts, media, content creation" },
];
const SECTORS = SECTORS_LIST.map((s) => s.name);
const EDUCATION_LEVELS = ["No formal schooling", "Primary school", "Secondary school", "Vocational training", "University"];
const TIME_OPTIONS = ["Under 5 hours", "6-10 hours", "11-20 hours", "20+ hours"];
const CONSTRAINT_ITEMS = [
  { label: "Limited startup capital", icon: "savings" },
  { label: "No reliable internet", icon: "wifi_off" },
  { label: "No smartphone data plan at home", icon: "signal_cellular_off" },
  { label: "Limited business network", icon: "group_off" },
  { label: "Family/caregiving responsibilities", icon: "family_restroom" },
];
const CONSTRAINT_OPTIONS = CONSTRAINT_ITEMS.map((c) => c.label);

const STEPS = [
  { tag: "Sector", headline: "To start, what sector do you work in?", sub: "This helps me tailor my financial advice to your specific business reality.", next: "Background" },
  { tag: "Background", headline: "How much time and schooling do you bring to this?", sub: "There's no wrong answer — this just shapes how I explain things.", next: "Constraints" },
  { tag: "Constraints", headline: "Anything working against you right now?", sub: "Tap any that apply. This stays between us.", next: "Identity" },
  { tag: "Identity", headline: "Last thing — what should I call you?", sub: "So I can make this feel like it's actually yours.", next: "" },
];

interface IntakeAnswers {
  sector: string;
  educationLevel: string;
  timeAvailablePerWeek: string;
  constraints: string[];
  name: string;
  businessName: string;
  location: string;
}

const inputCls =
  "w-full rounded-xl border border-outline-variant bg-surface-container-lowest px-4 py-3 font-body-md text-body-md text-on-surface outline-none transition-colors placeholder:text-on-surface-variant/60 focus:border-primary focus:ring-2 focus:ring-primary/20";

function Choice({ active, onClick, children, className = "" }: { active: boolean; onClick: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-xl border text-left transition-all active:scale-[0.98] ${
        active
          ? "border-primary bg-primary-container/25 ring-2 ring-primary"
          : "border-outline-variant bg-surface-container-lowest hover:bg-surface-container-low"
      } ${className}`}
    >
      {children}
    </button>
  );
}

export default function IntakePage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [step, setStep] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const activeRecordingRef = useRef<ActiveRecording | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<IntakeAnswers>({
    sector: "", educationLevel: "", timeAvailablePerWeek: "", constraints: [], name: "", businessName: "", location: "",
  });
  const mentor = MENTORS["market-queen"];
  const cur = STEPS[step];

  async function toggleIntakeVoice() {
    if (isRecording) {
      setIsRecording(false);
      setIsTranscribing(true);
      try {
        if (activeRecordingRef.current) {
          const text = await activeRecordingRef.current.stop();
          activeRecordingRef.current = null;
          if (text) handleVoiceResult(text);
        }
      } catch (err) {
        console.error("Voice intake transcription error:", err);
      } finally {
        setIsTranscribing(false);
      }
    } else {
      try {
        const rec = await startAudioRecording();
        activeRecordingRef.current = rec;
        setIsRecording(true);
      } catch (err) {
        console.error("Microphone access error:", err);
        alert("Please allow microphone permissions to answer using your voice.");
      }
    }
  }

  function handleVoiceResult(text: string) {
    const lower = text.toLowerCase();
    if (step === 0) {
      const match = SECTORS.find((s) => lower.includes(s.toLowerCase()));
      if (match) setAnswers((a) => ({ ...a, sector: match }));
    } else if (step === 1) {
      const eduMatch = EDUCATION_LEVELS.find((e) => lower.includes(e.toLowerCase()));
      if (eduMatch) setAnswers((a) => ({ ...a, educationLevel: eduMatch }));
      const timeMatch = TIME_OPTIONS.find((t) => lower.includes(t.toLowerCase()));
      if (timeMatch) setAnswers((a) => ({ ...a, timeAvailablePerWeek: timeMatch }));
    } else if (step === 2) {
      CONSTRAINT_OPTIONS.forEach((c) => {
        if (lower.includes(c.toLowerCase()) || (lower.includes("capital") && c.includes("capital"))) toggleConstraint(c);
      });
    } else if (step === 3) {
      if (!answers.name) setAnswers((a) => ({ ...a, name: text }));
      else setAnswers((a) => ({ ...a, businessName: text }));
    }
  }

  function toggleConstraint(option: string) {
    setAnswers((a) => ({
      ...a,
      constraints: a.constraints.includes(option) ? a.constraints.filter((c) => c !== option) : [...a.constraints, option],
    }));
  }

  const canAdvance =
    (step === 0 && answers.sector !== "") ||
    (step === 1 && answers.educationLevel !== "" && answers.timeAvailablePerWeek !== "") ||
    step === 2 ||
    (step === 3 && answers.name.trim() !== "" && answers.businessName.trim() !== "");

  async function handleNext() {
    if (step < 3) {
      setStep((s) => s + 1);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const profile = await submitIntake(answers);
      dispatch({ type: "SET_PROFILE", profile });
      markIntakeCompleted();
      router.push("/persona");
    } catch {
      setSubmitError("Couldn't save that — check your connection and try again.");
      setSubmitting(false);
    }
  }

  function handleBack() {
    if (step > 0) setStep((s) => s - 1);
    else router.push("/");
  }

  const voiceLabel = isTranscribing ? "Transcribing voice input..." : isRecording ? "Stop voice input" : "Answer with your voice";
  const summary = [answers.sector, answers.educationLevel, answers.timeAvailablePerWeek].filter(Boolean);

  return (
    <div className="min-h-screen bg-surface text-on-surface lg:grid lg:grid-cols-[minmax(340px,5fr)_7fr]">
      {/* Left: mentor card (desktop) */}
      <aside className="relative hidden overflow-hidden bg-surface-container-low lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div>
          <p className="font-title-md text-title-md text-primary">AfriMentor AI</p>
          <p className="mt-1 font-eyebrow text-eyebrow uppercase text-on-surface-variant">Foundation Intake</p>
        </div>
        <div className="mx-auto w-full max-w-sm">
          <div className="overflow-hidden rounded-t-[999px] rounded-b-3xl border border-outline-variant bg-surface-container-lowest shadow-xl">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img(mentor.portrait)} alt={mentor.name} className="aspect-[4/5] w-full object-cover" />
            <div className="p-6">
              <p className="font-title-md text-title-md text-on-surface">{mentor.name}</p>
              <p className="font-label-sm text-label-sm text-sunburst-gold">{mentor.role}</p>
              <p className="mt-3 font-quote text-body-md italic text-on-surface-variant">“{mentor.quote}”</p>
            </div>
          </div>
        </div>
        <p className="font-caption text-caption text-on-surface-variant">Your answers shape how your mentor speaks to you.</p>
      </aside>

      {/* Right: intake panel */}
      <section className="mx-auto flex min-h-screen w-full max-w-2xl flex-col lg:max-w-none">
        <KenteStrip />
        <header className="flex items-center justify-between gap-3 px-5 pb-3 pt-4 md:px-10 lg:px-14 lg:pt-8">
          <div className="flex items-center gap-3">
            <button type="button" onClick={handleBack} aria-label="Go back" className="flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container-low">
              <Icon name="arrow_back" />
            </button>
            <div className="lg:hidden">
              <p className="font-title-md text-[18px] leading-none text-primary">CHIOMA</p>
              <p className="font-label-sm text-label-sm text-on-surface-variant">AfriMentor AI</p>
            </div>
            <p className="hidden font-eyebrow text-eyebrow uppercase text-on-surface-variant lg:block">Foundation Intake</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-primary-container px-3 py-1 font-label-sm text-label-sm text-on-primary-container">Step {step + 1} of 4</span>
            <ThemeToggleButton />
          </div>
        </header>

        {/* progress */}
        <div className="px-5 md:px-10 lg:px-14">
          <div className="flex gap-2" role="progressbar" aria-valuemin={1} aria-valuemax={4} aria-valuenow={step + 1}>
            {STEPS.map((_, i) => (
              <span key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i <= step ? "bg-primary" : "bg-outline-variant"}`} />
            ))}
          </div>
          <nav className="mt-3 hidden grid-cols-4 gap-2 md:grid" aria-label="Intake steps">
            {STEPS.map((s, i) => (
              <button
                key={s.tag}
                type="button"
                disabled={i > step}
                onClick={() => setStep(i)}
                className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-left font-eyebrow text-eyebrow uppercase transition-colors ${
                  i === step ? "text-primary" : i < step ? "text-on-surface hover:bg-surface-container-low" : "text-on-surface-variant/50"
                }`}
              >
                <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] ${i < step ? "bg-primary text-on-primary" : i === step ? "border-2 border-primary" : "border border-outline-variant"}`}>
                  {i < step ? <Icon name="check" size={13} /> : i + 1}
                </span>
                {s.tag}
              </button>
            ))}
          </nav>
        </div>

        <main className="flex-1 px-5 pb-6 pt-6 md:px-10 lg:px-14">
          {/* mentor speech */}
          <div className="flex items-start gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img(mentor.avatar)} alt="" className="h-11 w-11 shrink-0 rounded-full border-2 border-sunburst-gold object-cover" />
            <div className="rounded-2xl rounded-tl-sm bg-surface-container-low px-5 py-4">
              <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface md:font-headline-lg md:text-[34px] md:leading-[42px]">{cur.headline}</h1>
              <p className="mt-2 font-body-md text-body-md text-on-surface-variant">{cur.sub}</p>
            </div>
          </div>

          <div className="mt-6">
            {step === 0 && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {SECTORS_LIST.map((s) => {
                  const active = answers.sector === s.name;
                  return (
                    <Choice key={s.name} active={active} onClick={() => setAnswers((a) => ({ ...a, sector: s.name }))} className="flex items-start gap-3 p-4 sm:flex-col sm:p-5">
                      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${active ? "bg-primary text-on-primary" : "bg-secondary-container/50 text-on-secondary-container"}`}>
                        <Icon name={s.icon} />
                      </span>
                      <span>
                        <span className="block font-label-sm text-[15px] font-bold text-on-surface">{s.name}</span>
                        <span className="mt-0.5 block font-caption text-caption text-on-surface-variant">{s.desc}</span>
                      </span>
                    </Choice>
                  );
                })}
              </div>
            )}

            {step === 1 && (
              <div className="grid gap-6 md:grid-cols-2">
                <div>
                  <p className="mb-3 flex items-center gap-2 font-label-sm text-label-sm text-on-surface-variant"><Icon name="school" className="text-primary" /> Highest level of education</p>
                  <div className="flex flex-wrap gap-2">
                    {EDUCATION_LEVELS.map((e) => (
                      <Choice key={e} active={answers.educationLevel === e} onClick={() => setAnswers((a) => ({ ...a, educationLevel: e }))} className="rounded-full px-4 py-2 font-label-sm text-label-sm text-on-surface">{e}</Choice>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-3 flex items-center gap-2 font-label-sm text-label-sm text-on-surface-variant"><Icon name="schedule" className="text-primary" /> Time available per week</p>
                  <div className="grid grid-cols-2 gap-2">
                    {TIME_OPTIONS.map((t) => (
                      <Choice key={t} active={answers.timeAvailablePerWeek === t} onClick={() => setAnswers((a) => ({ ...a, timeAvailablePerWeek: t }))} className="px-4 py-3 text-center font-label-sm text-label-sm text-on-surface">{t}</Choice>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="grid gap-3 sm:grid-cols-2">
                {CONSTRAINT_ITEMS.map((c) => {
                  const active = answers.constraints.includes(c.label);
                  return (
                    <Choice key={c.label} active={active} onClick={() => toggleConstraint(c.label)} className="flex items-center gap-3 p-4">
                      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${active ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"}`}>
                        <Icon name={active ? "check_circle" : c.icon} filled={active} />
                      </span>
                      <span className="font-label-sm text-[15px] text-on-surface">{c.label}</span>
                    </Choice>
                  );
                })}
              </div>
            )}

            {step === 3 && (
              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col gap-1.5">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Your name *</span>
                  <input value={answers.name} onChange={(e) => setAnswers((a) => ({ ...a, name: e.target.value }))} className={inputCls} placeholder="e.g. Kofi Mensah" />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Business name *</span>
                  <input value={answers.businessName} onChange={(e) => setAnswers((a) => ({ ...a, businessName: e.target.value }))} className={inputCls} placeholder="e.g. Kumasi Poultry & Agro" />
                </label>
                <label className="flex flex-col gap-1.5 md:col-span-2">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Location</span>
                  <input value={answers.location} onChange={(e) => setAnswers((a) => ({ ...a, location: e.target.value }))} className={inputCls} placeholder="e.g. Kumasi, Ghana" />
                </label>
              </div>
            )}
          </div>

          {summary.length > 0 && step > 0 && (
            <div className="mt-6 flex justify-end">
              <div className="max-w-md rounded-2xl rounded-tr-sm bg-primary px-5 py-3 font-body-md text-body-md text-on-primary">
                {summary.join(" · ")}
              </div>
            </div>
          )}
        </main>

        <footer className="sticky bottom-0 border-t border-outline-variant/50 bg-surface/95 px-5 py-4 backdrop-blur md:px-10 lg:px-14">
          {submitError && <p role="alert" className="mb-3 text-center font-label-sm text-label-sm text-error">{submitError}</p>}
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label={voiceLabel}
              onClick={toggleIntakeVoice}
              disabled={isTranscribing}
              className={`flex h-12 items-center gap-2 rounded-full px-4 font-label-sm text-label-sm transition-all ${
                isRecording ? "animate-pulse bg-error text-on-error ring-2 ring-error/40" : isTranscribing ? "bg-surface-container-high text-primary" : "bg-secondary-container text-on-secondary-container hover:opacity-90"
              }`}
            >
              <Icon name={isTranscribing ? "hourglass_empty" : isRecording ? "graphic_eq" : "mic"} />
              <span className="hidden sm:inline">{isTranscribing ? "Transcribing..." : isRecording ? "Listening — tap to stop" : "Voice input"}</span>
            </button>
            <div className="ml-auto flex items-center gap-3">
              {step > 0 && (
                <button type="button" onClick={handleBack} className="h-12 rounded-full border border-outline-variant px-6 font-label-sm text-[15px] text-on-surface transition-colors hover:bg-surface-container-low">Back</button>
              )}
              <button
                type="button"
                disabled={!canAdvance || submitting}
                onClick={handleNext}
                className="flex h-12 items-center gap-2 rounded-full bg-sunburst-gold px-6 font-label-sm text-[15px] font-bold text-ink shadow-md transition-all hover:brightness-105 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submitting ? "Saving..." : step === 3 ? "Confirm & choose mentor" : `Continue to ${cur.next}`}
                {!submitting && <Icon name={step === 3 ? "check_circle" : "arrow_forward"} filled={step === 3} />}
              </button>
            </div>
          </div>
        </footer>
      </section>
    </div>
  );
}
