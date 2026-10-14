"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppDispatch, useAppState } from "@/lib/store";
import { fetchProfile } from "@/lib/api";
import { isIntakeCompleted } from "@/lib/session";
import { CreateGoalModal } from "@/components/goals/GoalModals";

/**
 * Route guard + profile bootstrap for the signed-in app (chat, goals, library,
 * progress, research). Each screen draws its own shell (sidebar, rail or tabs).
 */
export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  const { profile } = useAppState();
  const dispatch = useAppDispatch();
  const router = useRouter();

  // Reaching the app before intake sends the device back to intake.
  useEffect(() => {
    if (!isIntakeCompleted()) router.replace("/intake");
  }, [router]);

  useEffect(() => {
    if (!profile) fetchProfile().then((p) => dispatch({ type: "SET_PROFILE", profile: p })).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      {children}
      <CreateGoalModal />
    </>
  );
}
