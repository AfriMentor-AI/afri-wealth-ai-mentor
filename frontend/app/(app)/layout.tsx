"use client";

import { useEffect } from "react";
import { TopNav } from "@/components/TopNav";
import { FeedbackSurveyModal } from "@/components/FeedbackSurveyModal";
import { useAppDispatch, useAppState } from "@/lib/store";
import { fetchChatMessages, fetchProfile } from "@/lib/api";

export default function AppShellLayout({ children }: { children: React.ReactNode }) {
  const { chatMessages, profile } = useAppState();
  const dispatch = useAppDispatch();

  // Hydrate cross-tab data once at the shell level, not per-tab, so
  // switching tabs never re-fetches or loses state.
  useEffect(() => {
    if (chatMessages.length === 0) {
      fetchChatMessages().then((messages) => dispatch({ type: "SET_CHAT_MESSAGES", messages }));
    }
    if (!profile) {
      fetchProfile().then((p) => dispatch({ type: "SET_PROFILE", profile: p }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-surface">
      <TopNav />
      {/* pt clears the fixed top-left nav cluster; its real height varies
          slightly by breakpoint (icon+label stacked vs. inline), so this
          is intentionally generous rather than pixel-matched to it. */}
      <div className="mx-auto max-w-2xl pt-16 md:pt-20">{children}</div>
      <FeedbackSurveyModal />
    </div>
  );
}
