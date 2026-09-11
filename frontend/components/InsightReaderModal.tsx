"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import type { InsightItem } from "@/lib/types";
import { playTextToSpeech, stopCurrentSpeech } from "@/lib/voice";
import { recordAction, upsertInsightProgress } from "@/lib/api";
import { useAppDispatch, useAppState } from "@/lib/store";

interface InsightReaderModalProps {
  item: InsightItem | null;
  isFavorite: boolean;
  onClose: () => void;
  onToggleFavorite: () => void;
  onCompleted?: () => void;
}

function formatAudioTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface LessonContent {
  headline: string;
  mentorTip: string;
  audioNarration: string;
  overview: string;
  practicalSteps: Array<{ title: string; detail: string }>;
  keyTakeaway: string;
  formulaOrTool?: { label: string; formula: string; example: string };
}

const LESSON_CURRICULUM: Record<string, LessonContent> = {
  "How to price your trade": {
    headline: "The 3-Layer Pricing Formula for African Micro-Enterprises",
    mentorTip:
      "Never compete purely on being the cheapest in the market. Compete on reliability, freshness, and trust. Cheap without a true margin will quietly starve your working capital.",
    audioNarration:
      "Welcome to this micro-lesson on pricing your trade. Many traders calculate profit simply as the selling price minus the market purchase price. But what about the bus fare, the market toll, the mobile money cash-out fee, and the spoilage? To stay in business long-term, you must account for your true unit cost, local demand, and a healthy reinvestment margin.",
    overview:
      "Setting the right price is the difference between surviving day-to-day and building generational wealth. This lesson walks you through calculating your true cost of goods sold (including hidden transaction costs) and setting prices that customers respect while keeping your business cash-flow positive.",
    practicalSteps: [
      {
        title: "1. Calculate your True Unit Cost",
        detail:
          "Take the wholesale purchase cost, then add apportioned transport costs, plastic carrier bags, electricity, and MoMo withdrawal fees (usually 1% to 1.5%). This is your break-even floor.",
      },
      {
        title: "2. Benchmark against Local Market Reality",
        detail:
          "Survey at least 3 nearby sellers. If your price is higher, be ready to justify it with superior packaging, credit trust, or delivery speed. If you are cheaper, ensure you aren't sacrificing your rent fund.",
      },
      {
        title: "3. Build in a 20-30% Reinvestment Buffer",
        detail:
          "Wholesale prices fluctuate due to inflation and seasonal supply shocks. Your price must generate surplus cash to absorb the next inventory price hike without eating your capital.",
      },
      {
        title: "4. Test Value Bundling",
        detail:
          "Instead of giving discounts on single items, sell bundles: 'Buy 3 for ₵50 instead of ₵18 each.' This moves volume faster and secures upfront cash flow.",
      },
    ],
    formulaOrTool: {
      label: "Unit Price Target Formula",
      formula: "Target Price = (Direct Cost + Allocated Daily Overhead) ÷ (1 - Desired Net Margin %)",
      example:
        "Example: If an item costs ₵30 to acquire and ₵5 in transport/fees, aiming for a 20% margin: ₵35 ÷ 0.80 = ₵43.75 selling price.",
    },
    keyTakeaway:
      "If you do not price for profit, you are merely providing free labor to your community. Price with pride and protect your capital.",
  },

  "Saving during lean seasons": {
    headline: "Building & Protecting Your Cash Buffer for Dry Months",
    mentorTip:
      "In the harvest and festive months, live like lean season starts next week. The best time to fix your roof is when the sun is shining.",
    audioNarration:
      "Hello! Let's talk about saving during lean seasons. In almost every African trade, revenue fluctuates with weather, harvests, school-fee cycles, or holidays. The key to financial peace is not earning the same every month, but smoothing your consumption so that slow months never force you into predatory emergency loans.",
    overview:
      "Every enterprise has seasonal peaks and troughs. By mapping your annual sales cycle and automating your lean-season lockbox during boom months, you protect your household from stress and position yourself to buy distressed inventory when others run out of cash.",
    practicalSteps: [
      {
        title: "1. Map your Enterprise Calendar",
        detail:
          "Identify your 2-3 slowest turnover months (often January-February post-festivities, or the peak rainy season). Mark them clearly on your calendar.",
      },
      {
        title: "2. Implement the '30% Harvest Skim'",
        detail:
          "During peak revenue months, automatically divert 30% of net profits into a locked savings account or high-yield fund that requires 24-hour notice to withdraw.",
      },
      {
        title: "3. Pre-Negotiate Supplier & Landlord Terms",
        detail:
          "Communicate with your suppliers and landlord while business is booming. Arrange lower minimum orders or flexible payment schedules for your expected slow season.",
      },
      {
        title: "4. Pivot to Inelastic Daily Staples",
        detail:
          "When discretionary spending drops in your neighborhood, introduce high-turnover essential goods (cooking oil, mobile airtime, grains) that people must purchase daily regardless of season.",
      },
    ],
    formulaOrTool: {
      label: "Buffer Target Rule",
      formula: "Minimum Buffer = (Monthly Fixed Overheads + Basic Household Sustenance) × 2.5 Months",
      example:
        "If shop rent is ₵400 and home food is ₵800 per month: (400 + 800) × 2.5 = ₵3,000 target lean-season reserve.",
    },
    keyTakeaway:
      "A disciplined cash buffer turns emergencies into minor inconveniences and keeps you in business when competitors close.",
  },

  "Bookkeeping with Mobile Money": {
    headline: "Turning Your Mobile Money Statement into a Daily Ledger",
    mentorTip:
      "If your household soup money and your business stock purchases sit in the same mobile money wallet, you will never know whether you are making profit or eating your capital.",
    audioNarration:
      "Welcome! Mobile money has revolutionized African commerce, but it can also hide cash leaks if you do not track transaction fees and transfers. In this lesson, we look at segregating your personal and merchant wallets, and running a simple 5-minute evening reconciliation that gives you total control of your money.",
    overview:
      "Mobile money creates a digital paper trail for every transaction. With a structured 5-minute daily habit, you can transform transaction alerts into clean financial statements that qualify you for bank loans and trade credit.",
    practicalSteps: [
      {
        title: "1. Dedicated Business SIM / Merchant Till",
        detail:
          "Register a dedicated business SIM or Merchant Merchant Till (Paybill / Till Number). Never accept customer payments onto your personal family SIM card.",
      },
      {
        title: "2. The 5-Minute Evening Ledger",
        detail:
          "At the close of each business day, record three numbers: Starting MoMo Balance, Total MoMo Inflows from sales, and Ending Balance. Any difference must be accounted for.",
      },
      {
        title: "3. Explicitly Track MoMo Charges & E-Levy",
        detail:
          "Cash-out fees, transfer fees, and government levies are legitimate operating expenses. Write them in a dedicated 'Financial Charges' column so they don't eat your margins unseen.",
      },
      {
        title: "4. Download Monthly PDF Statements",
        detail:
          "At the end of every month, export your mobile money statement. Store it in a folder — this is your official business credit score when applying for supplier credit.",
      },
    ],
    keyTakeaway:
      "Every cedi or naira that passes through your phone without a record is wealth slipping through your fingers. Keep your ledger clean.",
  },

  "Negotiating with suppliers": {
    headline: "Securing Favorable Trade Terms Without Straining Relationships",
    mentorTip:
      "Your word is your real collateral. A supplier will forgive a delayed payment if you call them 48 hours early, but they will terminate your credit forever if you avoid their calls.",
    audioNarration:
      "Hello entrepreneur! Supplier negotiation is not about aggressively squeezing prices down until the other party makes a loss. It is about building a trusted partnership where the supplier extends 14 to 30-day inventory credit, knowing your word is dependable.",
    overview:
      "Suppliers need reliable, repeat buyers just as much as you need affordable inventory. By demonstrating volume consistency and impeccable payment discipline, you can secure credit terms that dramatically reduce your working capital requirements.",
    practicalSteps: [
      {
        title: "1. Build Credit With 3 Cash Runs First",
        detail:
          "Never ask for payment terms on your first order. Complete 3 to 5 transactions with prompt cash payment. Establish that you are serious and easy to work with.",
      },
      {
        title: "2. Propose a 50/50 Split Payment Structure",
        detail:
          "When you are ready to transition to credit, offer: 50% cash on delivery, and the remaining 50% in 14 days after you have sold the first batch. This lowers the supplier's risk.",
      },
      {
        title: "3. Share Your Re-order Forecast",
        detail:
          "Suppliers love predictability. Tell them: 'I sell 20 crates every Thursday.' In exchange for this consistent demand, request bulk pricing or priority dispatch.",
      },
      {
        title: "4. Over-Communicate on Cash Delays",
        detail:
          "If a customer delays paying you, contact your supplier 48 hours BEFORE the payment due date. Offer a partial payment immediately and commit to a firm final settlement date.",
      },
    ],
    keyTakeaway:
      "Suppliers are your most affordable bank. Treat their invoices with sacred respect and they will finance your growth.",
  },

  "Reading your first loan agreement": {
    headline: "Demystifying Interest Rates, Hidden Fees & Collateral Clauses",
    mentorTip:
      "Never sign a financial agreement under pressure or urgency. Take the document home, read every line in quietness, or share the terms with me in chat so we can dissect the real cost together.",
    audioNarration:
      "Welcome to this critical guide on reading loan agreements. Micro-credit can accelerate your enterprise, but deceptive lending terms can quickly trap you in a debt spiral. Let's learn how to spot flat versus reducing interest rates, hidden administrative charges, and aggressive default penalties.",
    overview:
      "A loan document is a legally binding contract. Lenders frequently quote low 'monthly flat rates' that disguise exorbitant annual APRs. Knowing what questions to ask protects your hard-earned assets from unfair seizure.",
    practicalSteps: [
      {
        title: "1. Distinguish 'Flat Rate' from 'Reducing Balance'",
        detail:
          "A 4% monthly flat rate sounds cheap, but because you pay interest on the full initial amount even after repaying half, the real Effective APR is over 45%! Always demand the Effective Annual Rate in writing.",
      },
      {
        title: "2. Scrutinize Upfront Processing Fees",
        detail:
          "Check for 'facility fees', 'loan insurance', 'application charges', and 'disbursement fees'. If a ₵5,000 loan has ₵500 in fees deducted upfront, your usable capital is only ₵4,500.",
      },
      {
        title: "3. Check Early Repayment Penalties",
        detail:
          "If your business has a great month, you should be allowed to clear your loan early to save on future interest. Ensure there are no penalty fees for settling ahead of schedule.",
      },
      {
        title: "4. Clarify Collateral and Personal Guarantees",
        detail:
          "Verify exactly what assets are pledged. Beware of blanket liens that allow seizing personal household items or family property for small commercial micro-loans.",
      },
    ],
    keyTakeaway:
      "A good loan grows your profit faster than the interest rate. A bad loan transfers your profit directly to the lender. Read before you sign.",
  },
};

export function InsightReaderModal({
  item,
  isFavorite,
  onClose,
  onToggleFavorite,
  onCompleted,
}: InsightReaderModalProps) {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const { selectedPersona } = useAppState();

  const [isPlaying, setIsPlaying] = useState(false);
  const [playProgress, setPlayProgress] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isCompleting, setIsCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [completionBanner, setCompletionBanner] = useState<{
    streakDays: number;
    badgeUnlocked?: string;
  } | null>(null);

  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Reset state whenever a new item opens
    setIsPlaying(false);
    setPlayProgress(0);
    setElapsedSeconds(0);
    setCompleted(false);
    setCompletionBanner(null);
    stopCurrentSpeech();

    return () => {
      stopCurrentSpeech();
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, [item?.id]);

  if (!item) return null;

  // Resolve curriculum data, item content, or tailored fallback
  const baseLesson = LESSON_CURRICULUM[item.title];
  const audioNarrationText =
    item.audioNarration ||
    baseLesson?.audioNarration ||
    `${item.title}. ${item.summary}. Take your time to study these key principles and apply them to your daily business decisions.`;

  const lesson: LessonContent = baseLesson ?? {
    headline: item.title,
    mentorTip:
      "Every small action you take to structure your enterprise adds up to substantial long-term independence. Focus on cash discipline today.",
    audioNarration: audioNarrationText,
    overview: item.content || item.summary,
    practicalSteps: [
      {
        title: "1. Evaluate your current operational reality",
        detail: `Review how ${item.title.toLowerCase()} impacts your daily sales, inventory, or operational costs.`,
      },
      {
        title: "2. Implement one concrete test for 7 days",
        detail: `Pick a single action from this ${item.category.toLowerCase()} insight and measure the financial result before scaling it.`,
      },
      {
        title: "3. Build trust through consistent records",
        detail: "Keep clean daily records of cash flow, inventory movement, and customer credit to stay resilient.",
      },
    ],
    keyTakeaway: item.summary,
  };

  const personaName = selectedPersona?.name.toLowerCase() === "kwame" ? "kwame" : "chioma";
  const personaDisplay = personaName === "kwame" ? "Kwame (Accra, GH)" : "Chioma (Lagos, NG)";

  // Calculate actual speech duration from narration text (~140 wpm = ~2.3 words/sec)
  const wordCount = (lesson.audioNarration || "").trim().split(/\s+/).filter(Boolean).length;
  const audioDurationSeconds = Math.max(10, Math.round(wordCount / 2.3));

  const handleToggleAudio = async () => {
    if (isPlaying) {
      stopCurrentSpeech();
      setIsPlaying(false);
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      return;
    }

    setIsPlaying(true);
    setPlayProgress(0);
    setElapsedSeconds(0);

    const startTime = Date.now();
    const intervalMs = 150;

    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    progressIntervalRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      if (elapsed >= audioDurationSeconds) {
        setElapsedSeconds(audioDurationSeconds);
        setPlayProgress(100);
      } else {
        setElapsedSeconds(elapsed);
        setPlayProgress((elapsed / audioDurationSeconds) * 100);
      }
    }, intervalMs);

    try {
      await playTextToSpeech(lesson.audioNarration, personaName, () => {
        setIsPlaying(false);
        setElapsedSeconds(audioDurationSeconds);
        setPlayProgress(100);
        if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        upsertInsightProgress(item.id, audioDurationSeconds, true).catch(() => {});
      });
    } catch (err) {
      console.warn("Audio playback failed:", err);
      setIsPlaying(false);
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    }
  };

  const handleMarkComplete = async () => {
    if (completed || isCompleting) return;
    setIsCompleting(true);
    try {
      const res = await recordAction("insight_completed");
      setCompleted(true);
      const newlyEarned = res.newlyEarnedBadges?.[0]?.label;
      setCompletionBanner({
        streakDays: res.streak.currentStreakDays,
        badgeUnlocked: newlyEarned,
      });
      onCompleted?.();
      upsertInsightProgress(item.id, audioDurationSeconds, true).catch(() => {});
    } catch (err) {
      console.warn("Could not log insight completion:", err);
      setCompleted(true);
      setCompletionBanner({ streakDays: 1 });
    } finally {
      setIsCompleting(false);
    }
  };

  const handleAskMentor = () => {
    stopCurrentSpeech();
    onClose();
    dispatch({
      type: "SET_CHAT_DRAFT",
      draft: `I just studied the lesson "${item.title}". Can you give me practical advice on how to apply this to my business?`,
    });
    router.push("/chat");
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="insight-title"
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-sm backdrop-blur-sm md:p-md animate-fadeIn"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          stopCurrentSpeech();
          onClose();
        }
      }}
    >
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col rounded-2xl border border-outline-variant/30 bg-surface text-on-surface shadow-2xl">
        {/* Modal Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-outline-variant/20 bg-surface/95 px-md py-sm backdrop-blur-md md:px-lg md:py-md">
          <div className="flex items-center gap-sm">
            <span className="inline-flex items-center gap-xs rounded-full bg-primary/10 px-sm py-1 font-label-sm text-xs font-bold uppercase tracking-wider text-primary">
              <Icon name={item.isAudio ? "headphones" : "auto_stories"} size={16} />
              {item.category}
            </span>
            <span className="flex items-center gap-1 font-label-sm text-xs text-on-surface-variant">
              <Icon name="schedule" size={14} />
              {item.durationMinutes} min read
            </span>
          </div>

          <div className="flex items-center gap-xs">
            <button
              onClick={onToggleFavorite}
              aria-label={isFavorite ? "Remove from bookmarks" : "Bookmark this lesson"}
              className="tap-target flex h-9 w-9 items-center justify-center rounded-full text-primary transition-colors hover:bg-surface-container"
            >
              <Icon name="favorite" filled={isFavorite} size={20} />
            </button>
            <button
              onClick={() => {
                stopCurrentSpeech();
                onClose();
              }}
              aria-label="Close reader"
              className="tap-target flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
            >
              <Icon name="close" size={20} />
            </button>
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 space-y-md overflow-y-auto px-md py-md md:space-y-lg md:px-lg md:py-lg">
          {/* Title & Headline */}
          <div>
            <h1 id="insight-title" className="font-headline-sm text-2xl font-bold leading-tight text-on-surface md:text-3xl">
              {item.title}
            </h1>
            <p className="mt-xs font-title-sm text-sm font-semibold text-primary">
              {lesson.headline}
            </p>
          </div>

          {/* Interactive Audio Player Bar */}
          <div className="rounded-xl border border-primary/20 bg-primary-container/30 p-md transition-all duration-300">
            <div className="flex flex-col gap-sm sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-md">
                <button
                  onClick={handleToggleAudio}
                  aria-label={isPlaying ? "Pause voice narration" : "Play voice narration"}
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary shadow-md transition-transform hover:scale-105 active:scale-95"
                >
                  <Icon name={isPlaying ? "pause" : "play_arrow"} filled size={28} />
                </button>
                <div>
                  <p className="font-label-md text-sm font-bold text-on-surface">
                    {isPlaying ? "Narration Playing" : "Listen to Lesson"}
                  </p>
                  <p className="font-body-sm text-xs text-on-surface-variant">
                    Voice of Mentor {personaDisplay} • {formatAudioTime(audioDurationSeconds)} audio
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-xs text-xs font-medium text-primary">
                <Icon name="volume_up" size={16} />
                <span>{item.isAudio ? "Audio Masterclass" : "Audio Guide Available"}</span>
              </div>
            </div>

            {/* Audio Progress Scrubber */}
            <div className="mt-sm">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-outline-variant/30">
                <div
                  className="h-full bg-primary transition-all duration-300 ease-out"
                  style={{ width: `${playProgress}%` }}
                />
              </div>
              <div className="mt-1 flex justify-between font-label-sm text-[11px] text-on-surface-variant">
                <span>
                  {isPlaying
                    ? `Playing (${formatAudioTime(elapsedSeconds)})`
                    : playProgress >= 100
                    ? "Completed"
                    : playProgress > 0
                    ? `Paused (${formatAudioTime(elapsedSeconds)})`
                    : "Ready to listen"}
                </span>
                <span>{formatAudioTime(audioDurationSeconds)}</span>
              </div>
            </div>
          </div>

          {/* Completion Celebration Banner */}
          {completionBanner && (
            <div className="flex items-start gap-md rounded-xl border border-secondary/30 bg-secondary-container/50 p-md animate-fadeIn">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-secondary text-on-secondary">
                <Icon name="emoji_events" filled size={22} />
              </div>
              <div>
                <p className="font-title-sm text-sm font-bold text-on-secondary-container">
                  Lesson Completed! Action Recorded!
                </p>
                <div className="font-body-sm text-xs text-on-secondary-container/90">
                  Your daily streak is now at <strong>{completionBanner.streakDays} days</strong>.
                  {completionBanner.badgeUnlocked && (
                    <span className="block mt-1 font-bold text-primary">
                      🏆 Badge Unlocked: {completionBanner.badgeUnlocked}!
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Overview */}
          <div className="space-y-xs">
            <h2 className="font-title-sm text-sm font-bold uppercase tracking-wider text-on-surface-variant">
              Executive Overview
            </h2>
            <p className="font-body-md text-base leading-relaxed text-on-surface">
              {lesson.overview}
            </p>
          </div>

          {/* Practical Framework Steps */}
          <div className="space-y-sm">
            <h2 className="font-title-sm text-sm font-bold uppercase tracking-wider text-on-surface-variant">
              Practical Action Steps
            </h2>
            <div className="space-y-sm">
              {lesson.practicalSteps.map((step, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-outline-variant/20 bg-surface-container-low p-md"
                >
                  <p className="font-title-sm text-sm font-bold text-on-surface">
                    {step.title}
                  </p>
                  <p className="mt-xs font-body-sm text-sm leading-relaxed text-on-surface-variant">
                    {step.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Formula or Example Box (if applicable) */}
          {lesson.formulaOrTool && (
            <div className="rounded-xl border border-tertiary/30 bg-surface-container p-md">
              <div className="flex items-center gap-xs font-label-md text-xs font-bold uppercase tracking-wider text-tertiary">
                <Icon name="calculate" size={16} />
                {lesson.formulaOrTool.label}
              </div>
              <div className="mt-xs rounded bg-surface p-sm font-mono text-xs font-semibold text-on-surface">
                {lesson.formulaOrTool.formula}
              </div>
              <p className="mt-xs font-body-sm text-xs text-on-surface-variant">
                {lesson.formulaOrTool.example}
              </p>
            </div>
          )}

          {/* Mentor Golden Rule Quote */}
          <div className="relative rounded-xl border-l-4 border-primary bg-primary/5 p-md">
            <div className="flex items-center gap-xs font-label-sm text-xs font-bold uppercase text-primary">
              <Icon name="psychology" size={16} />
              Mentor {selectedPersona?.name ?? "Chioma"}&apos;s Golden Rule
            </div>
            <p className="mt-xs font-body-md text-sm italic leading-relaxed text-on-surface">
              &ldquo;{lesson.mentorTip}&rdquo;
            </p>
          </div>

          {/* Key Takeaway */}
          <div className="rounded-xl bg-surface-container-high p-md">
            <div className="flex items-center gap-xs font-label-sm text-xs font-bold uppercase text-on-surface">
              <Icon name="lightbulb" size={16} className="text-secondary" />
              Key Takeaway
            </div>
            <p className="mt-xs font-body-md text-sm font-medium text-on-surface-variant">
              {lesson.keyTakeaway}
            </p>
          </div>
        </div>

        {/* Modal Bottom Actions */}
        <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-sm border-t border-outline-variant/20 bg-surface/95 px-md py-sm backdrop-blur-md md:px-lg md:py-md">
          <button
            onClick={handleAskMentor}
            className="flex items-center gap-xs rounded-lg border border-outline-variant/40 px-md py-2 font-label-md text-xs font-semibold text-on-surface transition-colors hover:bg-surface-container"
          >
            <Icon name="chat" size={16} />
            Ask in Chat
          </button>

          <button
            onClick={handleMarkComplete}
            disabled={completed || isCompleting}
            className={`flex items-center gap-xs rounded-lg px-lg py-2 font-label-md text-xs font-bold transition-all shadow-sm ${
              completed
                ? "bg-secondary text-on-secondary"
                : "bg-primary text-on-primary hover:bg-primary/90 active:scale-95"
            }`}
          >
            <Icon name={completed ? "check_circle" : "task_alt"} filled={completed} size={16} />
            {completed ? "Completed!" : isCompleting ? "Saving..." : "Mark Lesson Complete"}
          </button>
        </div>
      </div>
    </div>
  );
}
