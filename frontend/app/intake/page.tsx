"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";
import { useAppDispatch } from "@/lib/store";
import { submitIntake } from "@/lib/api";

const SECTORS_LIST = [
  { name: "Trader", icon: "storefront", desc: "Retail shops, market trading, imports/exports" },
  { name: "Tech", icon: "computer", desc: "Software, digital services, web development" },
  { name: "Fashion/Retail", icon: "checkroom", desc: "Apparel, textiles, boutiques, tailoring" },
  { name: "Agriculture", icon: "agriculture", desc: "Farming, agro-processing, livestock" },
  { name: "Creative", icon: "palette", desc: "Design, crafts, media, content creation" },
];

const SECTORS = ["Trader", "Tech", "Fashion/Retail", "Agriculture", "Creative"];
const EDUCATION_LEVELS = ["No formal schooling", "Primary school", "Secondary school", "Vocational training", "University"];
const TIME_OPTIONS = ["Under 5 hours", "6-10 hours", "11-20 hours", "20+ hours"];
const CONSTRAINT_OPTIONS = [
  "Limited startup capital",
  "No reliable internet",
  "No smartphone data plan at home",
  "Limited business network",
  "Family/caregiving responsibilities",
];

const CONSTRAINT_ITEMS = [
  { label: "Limited startup capital", icon: "savings" },
  { label: "No reliable internet", icon: "wifi_off" },
  { label: "No smartphone data plan at home", icon: "signal_cellular_off" },
  { label: "Limited business network", icon: "group_off" },
  { label: "Family/caregiving responsibilities", icon: "family_restroom" },
];

const STEPS = [
  { tag: "Intake", headline: "To start, what sector do you work in?", sub: "This helps me tailor my financial advice to your specific business reality." },
  { tag: "Intake", headline: "How much time and schooling do you bring to this?", sub: "There's no wrong answer — this just shapes how I explain things." },
  { tag: "Intake", headline: "Anything working against you right now?", sub: "Tap any that apply. This stays between us." },
  { tag: "Intake", headline: "Last thing — what should I call you?", sub: "So I can make this feel like it's actually yours." },
];

const DESKTOP_STEPS = [
  { tag: "Sector", headline: "To start, what sector do you work in?", sub: "This helps me tailor my financial advice to your specific business reality." },
  { tag: "Background", headline: "How much time and schooling do you bring to this?", sub: "There's no wrong answer — this just shapes how I explain things." },
  { tag: "Constraints", headline: "Anything working against you right now?", sub: "Tap any that apply. This stays between us." },
  { tag: "Profile", headline: "Last thing — what should I call you?", sub: "So I can make this feel like it's actually yours." },
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

export default function IntakePage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [step, setStep] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<IntakeAnswers>({
    sector: "",
    educationLevel: "",
    timeAvailablePerWeek: "",
    constraints: [],
    name: "",
    businessName: "",
    location: "",
  });

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
      router.push("/persona");
    } catch {
      setSubmitError("Couldn't save that — check your connection and try again.");
      setSubmitting(false);
    }
  }

  function handleBack() {
    if (step > 0) {
      setStep((s) => s - 1);
    } else {
      router.push("/");
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* ========================================================================= */}
      {/* MOBILE VIEW (md:hidden) — 100% original mobile design & layout */}
      {/* ========================================================================= */}
      <div className="mx-auto flex min-h-screen max-w-md flex-col bg-surface md:hidden">
        <header className="flex items-center justify-between px-margin-mobile py-md">
          <div>
            <p className="font-headline-lg-mobile text-[18px] leading-none text-primary">CHIOMA</p>
            <p className="font-label-sm text-label-sm text-on-surface-variant">AfriMentor AI</p>
          </div>
          <ThemeToggle />
        </header>

        <div className="px-margin-mobile">
          <div className="flex items-center gap-sm">
            <span className="rounded-full bg-primary-container px-sm py-xs font-label-sm text-label-sm text-on-primary-container">
              Step {step + 1} of 4
            </span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">{STEPS[step].tag}</span>
          </div>
          <div className="mt-sm flex gap-1">
            {[0, 1, 2, 3].map((i) => (
              <span key={i} className={`h-1 flex-1 rounded-full ${i <= step ? "bg-primary" : "bg-outline-variant"}`} />
            ))}
          </div>
        </div>

        <main className="flex-1 px-margin-mobile pt-lg">
          <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-on-background">{STEPS[step].headline}</h1>
          <p className="mt-xs font-body-md text-body-md text-on-surface-variant">{STEPS[step].sub}</p>

          <div className="mt-lg">
            {step === 0 && (
              <div className="flex flex-wrap gap-sm">
                {SECTORS.map((s) => (
                  <Chip key={s} label={s} active={answers.sector === s} onClick={() => setAnswers((a) => ({ ...a, sector: s }))} />
                ))}
              </div>
            )}

            {step === 1 && (
              <div className="flex flex-col gap-lg">
                <div>
                  <p className="mb-sm font-label-sm text-label-sm text-on-surface-variant">Highest level of education</p>
                  <div className="flex flex-wrap gap-sm">
                    {EDUCATION_LEVELS.map((e) => (
                      <Chip key={e} label={e} active={answers.educationLevel === e} onClick={() => setAnswers((a) => ({ ...a, educationLevel: e }))} />
                    ))}
                  </div>
                </div>
                <div>
                  <p className="mb-sm font-label-sm text-label-sm text-on-surface-variant">Time available per week</p>
                  <div className="flex flex-wrap gap-sm">
                    {TIME_OPTIONS.map((t) => (
                      <Chip key={t} label={t} active={answers.timeAvailablePerWeek === t} onClick={() => setAnswers((a) => ({ ...a, timeAvailablePerWeek: t }))} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-wrap gap-sm">
                {CONSTRAINT_OPTIONS.map((c) => (
                  <Chip key={c} label={c} active={answers.constraints.includes(c)} onClick={() => toggleConstraint(c)} />
                ))}
              </div>
            )}

            {step === 3 && (
              <div className="flex flex-col gap-md">
                <label className="flex flex-col gap-xs">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Your name</span>
                  <input
                    value={answers.name}
                    onChange={(e) => setAnswers((a) => ({ ...a, name: e.target.value }))}
                    className="w-full rounded border border-outline-variant bg-surface-container-lowest p-md font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
                    placeholder="e.g. Kofi Mensah"
                  />
                </label>
                <label className="flex flex-col gap-xs">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Business name</span>
                  <input
                    value={answers.businessName}
                    onChange={(e) => setAnswers((a) => ({ ...a, businessName: e.target.value }))}
                    className="w-full rounded border border-outline-variant bg-surface-container-lowest p-md font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
                    placeholder="e.g. Poultry Business - Kumasi"
                  />
                </label>
                <label className="flex flex-col gap-xs">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Location</span>
                  <input
                    value={answers.location}
                    onChange={(e) => setAnswers((a) => ({ ...a, location: e.target.value }))}
                    className="w-full rounded border border-outline-variant bg-surface-container-lowest p-md font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
                    placeholder="e.g. Kumasi, Ghana"
                  />
                </label>
              </div>
            )}
          </div>
        </main>

        <footer className="px-margin-mobile pb-lg pt-md">
          {submitError && (
            <p role="alert" className="mb-sm text-center font-label-sm text-label-sm text-error">
              {submitError}
            </p>
          )}
          {step === 3 ? (
            <Button
              variant="cta"
              className="h-14 w-full text-[20px]"
              disabled={!canAdvance || submitting}
              onClick={handleNext}
            >
              {submitting ? "Saving..." : "Confirm"}
              {!submitting && <Icon name="check_circle" filled />}
            </Button>
          ) : (
            <>
              <div className="flex items-center gap-sm rounded-full border border-outline-variant bg-surface-container-lowest px-sm py-xs">
                <button
                  aria-label={isRecording ? "Stop voice input" : "Answer with your voice"}
                  onClick={() => setIsRecording((r) => !r)}
                  className={`tap-target flex items-center justify-center rounded-full ${isRecording ? "animate-pulse bg-error text-on-error" : "bg-primary text-on-primary"}`}
                >
                  <Icon name={isRecording ? "graphic_eq" : "mic"} />
                </button>
                <span className="flex-1 font-body-md text-body-md text-on-surface-variant">
                  {answers.sector || answers.educationLevel || "Tap a chip or use your voice to respond."}
                </span>
                <button
                  aria-label="Continue"
                  disabled={!canAdvance}
                  onClick={handleNext}
                  className="tap-target flex items-center justify-center rounded-full bg-primary text-on-primary disabled:opacity-40"
                >
                  <Icon name="send" />
                </button>
              </div>
              <p className="mt-sm text-center font-label-sm text-label-sm text-on-surface-variant">
                Tap a chip or use your voice to respond.
              </p>
            </>
          )}
        </footer>
      </div>

      {/* ========================================================================= */}
      {/* DESKTOP VIEW (hidden md:flex) — Enhanced responsive desktop experience */}
      {/* ========================================================================= */}
      <div className="mx-auto hidden min-h-screen max-w-4xl flex-col justify-between px-xl py-lg md:flex">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-outline-variant/40 pb-md">
          <div className="flex items-center gap-md">
            <button
              onClick={handleBack}
              aria-label="Go back"
              className="tap-target -ml-2 flex items-center justify-center rounded-full p-2 text-on-surface-variant hover:bg-surface-container-low transition-colors"
            >
              <Icon name="arrow_back" />
            </button>
            <div className="relative h-10 w-10 overflow-hidden rounded-full border-2 border-primary">
              <Image src="/images/chioma-avatar.png" alt="Chioma" fill className="object-cover" />
            </div>
            <div>
              <p className="font-headline-lg-mobile text-[18px] font-bold leading-none text-primary">CHIOMA</p>
              <p className="font-label-sm text-label-sm text-on-surface-variant">AfriMentor AI • Intake</p>
            </div>
          </div>
          <div className="flex items-center gap-md">
            <span className="rounded-full bg-primary-container px-md py-xs font-label-sm text-label-sm text-on-primary-container">
              Step {step + 1} of 4: {DESKTOP_STEPS[step].tag}
            </span>
            <ThemeToggle />
          </div>
        </header>

        {/* Progress Tracker */}
        <div className="mt-md">
          <div className="flex gap-3">
            {DESKTOP_STEPS.map((s, i) => (
              <div key={i} className="flex flex-1 flex-col gap-1.5">
                <div className={`h-1.5 w-full rounded-full transition-all duration-300 ${i <= step ? "bg-primary" : "bg-outline-variant/60"}`} />
                <span className={`font-label-sm text-[12px] uppercase tracking-wider ${i === step ? "font-bold text-primary" : "text-on-surface-variant/60"}`}>
                  {s.tag}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Question & Interactive Body */}
        <main className="my-auto flex-1 py-xl">
          <div className="rounded-2xl border-l-4 border-primary bg-surface-container-low p-lg shadow-sm">
            <h1 className="font-headline-lg text-headline-lg text-on-surface">
              {DESKTOP_STEPS[step].headline}
            </h1>
            <p className="mt-xs font-body-lg text-body-lg text-on-surface-variant">
              {DESKTOP_STEPS[step].sub}
            </p>
          </div>

          <div className="mt-xl">
            {/* Step 0: Sector Selection */}
            {step === 0 && (
              <div className="grid grid-cols-2 gap-md lg:grid-cols-3">
                {SECTORS_LIST.map((s) => {
                  const active = answers.sector === s.name;
                  return (
                    <button
                      key={s.name}
                      onClick={() => setAnswers((a) => ({ ...a, sector: s.name }))}
                      className={`flex flex-col items-start gap-xs rounded-xl border p-lg text-left transition-all hover:shadow-sm active:scale-98 ${
                        active
                          ? "border-primary bg-primary-container/20 ring-2 ring-primary text-on-surface"
                          : "border-outline-variant bg-surface hover:bg-surface-container-low text-on-surface"
                      }`}
                    >
                      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${active ? "bg-primary text-on-primary" : "bg-secondary-container/40 text-on-secondary-container"}`}>
                        <Icon name={s.icon} />
                      </div>
                      <h3 className="font-title-md text-title-md font-bold text-on-surface mt-sm">{s.name}</h3>
                      <p className="font-body-md text-sm text-on-surface-variant">{s.desc}</p>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Step 1: Education & Time */}
            {step === 1 && (
              <div className="grid grid-cols-2 gap-xl">
                <div className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest p-lg shadow-sm">
                  <div className="mb-md flex items-center gap-sm">
                    <Icon name="school" className="text-primary" />
                    <h3 className="font-title-md text-title-md font-bold text-on-surface">Highest Level of Education</h3>
                  </div>
                  <div className="flex flex-wrap gap-sm">
                    {EDUCATION_LEVELS.map((e) => (
                      <Chip key={e} label={e} active={answers.educationLevel === e} onClick={() => setAnswers((a) => ({ ...a, educationLevel: e }))} />
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest p-lg shadow-sm">
                  <div className="mb-md flex items-center gap-sm">
                    <Icon name="schedule" className="text-primary" />
                    <h3 className="font-title-md text-title-md font-bold text-on-surface">Time Available Per Week</h3>
                  </div>
                  <div className="flex flex-wrap gap-sm">
                    {TIME_OPTIONS.map((t) => (
                      <Chip key={t} label={t} active={answers.timeAvailablePerWeek === t} onClick={() => setAnswers((a) => ({ ...a, timeAvailablePerWeek: t }))} />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Constraints Selection */}
            {step === 2 && (
              <div className="grid grid-cols-2 gap-md">
                {CONSTRAINT_ITEMS.map((c) => {
                  const active = answers.constraints.includes(c.label);
                  return (
                    <button
                      key={c.label}
                      onClick={() => toggleConstraint(c.label)}
                      className={`flex items-center gap-md rounded-xl border p-lg text-left transition-all hover:shadow-sm active:scale-98 ${
                        active
                          ? "border-primary bg-primary-container/20 ring-2 ring-primary text-on-surface"
                          : "border-outline-variant bg-surface hover:bg-surface-container-low text-on-surface"
                      }`}
                    >
                      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${active ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"}`}>
                        <Icon name={active ? "check_circle" : c.icon} filled={active} />
                      </div>
                      <span className="font-title-md text-title-md font-medium text-on-surface">{c.label}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Step 3: Business Information Form */}
            {step === 3 && (
              <div className="rounded-xl border border-outline-variant/60 bg-surface-container-lowest p-lg shadow-sm">
                <div className="grid grid-cols-2 gap-lg">
                  <label className="flex flex-col gap-xs">
                    <span className="font-label-sm text-label-sm font-semibold text-on-surface-variant">Your Name *</span>
                    <input
                      value={answers.name}
                      onChange={(e) => setAnswers((a) => ({ ...a, name: e.target.value }))}
                      className="w-full rounded-lg border border-outline-variant bg-surface p-md font-body-md text-body-md text-on-surface outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
                      placeholder="e.g. Kofi Mensah"
                    />
                  </label>

                  <label className="flex flex-col gap-xs">
                    <span className="font-label-sm text-label-sm font-semibold text-on-surface-variant">Business Name *</span>
                    <input
                      value={answers.businessName}
                      onChange={(e) => setAnswers((a) => ({ ...a, businessName: e.target.value }))}
                      className="w-full rounded-lg border border-outline-variant bg-surface p-md font-body-md text-body-md text-on-surface outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
                      placeholder="e.g. Kumasi Poultry & Agro"
                    />
                  </label>

                  <label className="flex flex-col gap-xs col-span-2">
                    <span className="font-label-sm text-label-sm font-semibold text-on-surface-variant">Location</span>
                    <input
                      value={answers.location}
                      onChange={(e) => setAnswers((a) => ({ ...a, location: e.target.value }))}
                      className="w-full rounded-lg border border-outline-variant bg-surface p-md font-body-md text-body-md text-on-surface outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"
                      placeholder="e.g. Kumasi, Ashanti Region, Ghana"
                    />
                  </label>
                </div>
              </div>
            )}
          </div>
        </main>

        {/* Footer & Navigation Controls */}
        <footer className="border-t border-outline-variant/40 pt-md">
          {submitError && (
            <p role="alert" className="mb-sm text-center font-label-sm text-label-sm text-error">
              {submitError}
            </p>
          )}

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-sm">
              <button
                type="button"
                aria-label={isRecording ? "Stop voice input" : "Answer with your voice"}
                onClick={() => setIsRecording((r) => !r)}
                className={`tap-target flex items-center gap-xs rounded-full px-md py-sm font-label-sm text-label-sm transition-all ${
                  isRecording ? "animate-pulse bg-error text-on-error" : "bg-secondary-container text-on-secondary-container hover:bg-secondary-container/80"
                }`}
              >
                <Icon name={isRecording ? "graphic_eq" : "mic"} />
                <span>{isRecording ? "Listening..." : "Voice Input"}</span>
              </button>

              <span className="text-sm text-on-surface-variant ml-sm">
                {step === 0 && answers.sector ? `Selected: ${answers.sector}` : "Select an option to proceed"}
              </span>
            </div>

            <div className="flex items-center gap-md">
              {step > 0 && (
                <Button variant="secondary" className="h-12 px-lg text-[16px]" onClick={handleBack}>
                  Back
                </Button>
              )}

              {step === 3 ? (
                <Button
                  variant="cta"
                  className="h-12 px-xl text-[18px]"
                  disabled={!canAdvance || submitting}
                  onClick={handleNext}
                >
                  {submitting ? "Saving..." : "Confirm & Choose Mentor"}
                  {!submitting && <Icon name="check_circle" filled />}
                </Button>
              ) : (
                <Button
                  variant="cta"
                  className="h-12 px-xl text-[18px]"
                  disabled={!canAdvance}
                  onClick={handleNext}
                >
                  Continue
                  <Icon name="arrow_forward" />
                </Button>
              )}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
