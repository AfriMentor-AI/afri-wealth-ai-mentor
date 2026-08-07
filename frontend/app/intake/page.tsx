"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Chip } from "@/components/ui/Chip";
import { Button } from "@/components/ui/Button";
import { useAppDispatch } from "@/lib/store";
import { submitIntake } from "@/lib/api";

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

const STEPS = [
  { tag: "Intake", headline: "To start, what sector do you work in?", sub: "This helps me tailor my financial advice to your specific business reality." },
  { tag: "Intake", headline: "How much time and schooling do you bring to this?", sub: "There's no wrong answer — this just shapes how I explain things." },
  { tag: "Intake", headline: "Anything working against you right now?", sub: "Tap any that apply. This stays between us." },
  { tag: "Intake", headline: "Last thing — what should I call you?", sub: "So I can make this feel like it's actually yours." },
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
    (step === 3 && answers.name !== "" && answers.businessName !== "");

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

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col bg-surface">
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
              <input
                value={answers.name}
                onChange={(e) => setAnswers((a) => ({ ...a, name: e.target.value }))}
                className="w-full rounded border border-outline-variant bg-surface-container-lowest p-md font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
                placeholder="Your name, e.g. Kofi Mensah"
              />
              <input
                value={answers.businessName}
                onChange={(e) => setAnswers((a) => ({ ...a, businessName: e.target.value }))}
                className="w-full rounded border border-outline-variant bg-surface-container-lowest p-md font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
                placeholder="Business name, e.g. Poultry Business - Kumasi"
              />
              <input
                value={answers.location}
                onChange={(e) => setAnswers((a) => ({ ...a, location: e.target.value }))}
                className="w-full rounded border border-outline-variant bg-surface-container-lowest p-md font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
                placeholder="Location, e.g. Kumasi, Ghana"
              />
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
  );
}
