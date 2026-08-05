import type { Milestone } from "@/lib/types";

// Per DESIGN.md Financial Visualization spec: "A simple, vertical 2px
// dashed line connecting circular nodes. Active nodes are filled with
// Gold; upcoming nodes are hollow with a 2px stroke." "Gold" per the
// Colors section is Confident Gold (#C8922A) = the `primary-container`
// token, not the darker `primary` token.
//
// Two extensions beyond the literal spec, both flagged: (1) completed
// nodes/segments get a distinct filled-secondary/solid-line treatment,
// since the spec only defines active/upcoming, not done — green success
// styling is consistent with how "done" is used everywhere else in the
// app; (2) a "blocked" state, needed for the real Goal Milestone Path
// screen's blocked commitments, styled with the existing error tokens.
//
// Simplified to a single-column vertical layout — the reference design's
// left/right zig-zag only works for exactly 3 fixed milestones and breaks
// for goals with a different milestone count.
export function MilestoneRoad({ milestones }: { milestones: Milestone[] }) {
  return (
    <ol className="flex flex-col">
      {milestones.map((m, i) => {
        const isLast = i === milestones.length - 1;
        const nodeClasses =
          m.status === "done"
            ? "bg-secondary text-on-secondary border-2 border-secondary"
            : m.status === "in_progress"
              ? "bg-primary-container text-on-primary-container border-2 border-primary-container"
              : m.status === "blocked"
                ? "bg-error-container text-on-error-container border-2 border-error"
                : "bg-surface text-on-surface-variant border-2 border-outline-variant"; // hollow

        return (
          <li key={m.id} className="relative flex gap-md pb-lg last:pb-0">
            {!isLast && (
              <span
                aria-hidden
                className={`absolute left-[19px] top-10 h-full w-0.5 ${
                  m.status === "done" ? "bg-secondary" : "border-l-2 border-dashed border-outline-variant"
                }`}
              />
            )}
            <div className={`z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-headline-lg-mobile text-[16px] ${nodeClasses}`}>
              {m.status === "done" ? "✓" : i + 1}
            </div>
            <div className="pt-1.5">
              <p
                className={`font-title-md text-title-md leading-tight ${
                  m.status === "in_progress" ? "text-primary" : "text-on-surface"
                }`}
              >
                {m.title}
              </p>
              <p className="text-xs text-on-surface-variant">{statusLabel[m.status]}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const statusLabel: Record<Milestone["status"], string> = {
  done: "Done",
  in_progress: "You are here",
  blocked: "Blocked",
  upcoming: "Upcoming",
};
