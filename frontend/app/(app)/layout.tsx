"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Image from "next/image";
import { BottomTabNav } from "@/components/BottomTabNav";
import { ThemeToggle } from "@/components/ThemeToggle";
import { NotificationPopover } from "@/components/NotificationPopover";
import { FeedbackSurveyModal } from "@/components/FeedbackSurveyModal";
import { useAppDispatch, useAppState } from "@/lib/store";
import { fetchChatMessages, fetchProfile } from "@/lib/api";
import { isIntakeCompleted } from "@/lib/session";

export default function AppShellLayout({ children }: { children: React.ReactNode }) {
  const { chatMessages, profile, chatSessionId } = useAppState();
  const dispatch = useAppDispatch();
  const pathname = usePathname();
  const router = useRouter();
  const hasOwnHeader = pathname?.startsWith("/chat") || pathname === "/goals/action" || pathname?.startsWith("/research/personas");


  // Route guard: the app shell (chat/goals/library/progress) is only reachable
  // after intake + persona selection. If this device hasn't completed intake,
  // send it back to the intake flow rather than dropping a user straight into
  // the app (deep link / stale bookmark / cleared flag). Reads localStorage in
  // an effect so the initial render stays hydration-safe.
  useEffect(() => {
    if (!isIntakeCompleted()) {
      router.replace("/intake");
    }
  }, [router]);

  useEffect(() => {
    if (chatSessionId && chatMessages.length === 0) {
      fetchChatMessages(chatSessionId).then((messages) => dispatch({ type: "SET_CHAT_MESSAGES", messages }));
    }
    if (!profile) {
      fetchProfile().then((p) => dispatch({ type: "SET_PROFILE", profile: p }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatSessionId]);

  // Fixed-viewport flex shell — no `fixed`/`calc(100vh-Nrem)` positioning
  // anywhere. Nav is a normal flex sibling (bottom row on mobile, left
  // sidebar on desktop) sized by its own content, and the content area is
  // the ONE scrollable region (flex-1 min-h-0 overflow-y-auto). This is
  // what actually fixes "content overflows/gets cut off" as a category —
  // the previous approach (fixed nav + guessing how much padding clears
  // it) breaks any time the nav's real height doesn't match the guess.
  return (
    <div className="flex h-screen w-full flex-col bg-surface md:flex-row-reverse">
      <div className="flex min-h-0 flex-1 flex-col">
        {!hasOwnHeader && (
          <header className="flex shrink-0 items-center justify-between px-margin-mobile py-md md:hidden">
            <div className="flex items-center gap-sm">
              <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-full border-2 border-primary">
                <Image src="/images/chioma-avatar.png" alt="Chioma" fill className="object-cover" />
              </div>
              <p className="font-title-md text-title-md text-on-surface">AfriMentor AI</p>
            </div>
            <div className="flex items-center gap-xs">
              <NotificationPopover />
              <ThemeToggle />
            </div>
          </header>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
      <BottomTabNav />
      <FeedbackSurveyModal />
    </div>
  );
}
