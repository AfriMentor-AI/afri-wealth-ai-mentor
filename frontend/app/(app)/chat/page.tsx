"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MobileTabs, MobileChrome } from "@/components/shell/AppSidebar";
import { ChatRail, ChatTopBar } from "@/components/chat/ChatChrome";
import { ConversationPanel, ConversationScreen } from "@/components/chat/Conversations";
import { useConversations } from "@/components/chat/useConversations";
import { useChatController } from "@/components/chat/useChatController";
import { NothingSelected, ThreadBody, ThreadHeader } from "@/components/chat/ThreadView";
import { CitationViewerModal } from "@/components/CitationViewerModal";
import { MENTORS, mentorFor } from "@/lib/mentors";
import { useMinWidth } from "@/lib/useMinWidth";
import { useAppDispatch } from "@/lib/store";

export default function ChatPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const isMd = useMinWidth(768);
  const isLg = useMinWidth(1024);
  const convo = useConversations();
  const ctrl = useChatController();
  const [panelOpen, setPanelOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mobileView, setMobileView] = useState<"list" | "thread">("thread");
  const [citation, setCitation] = useState<{ label: string; messageContext: string } | null>(null);

  const activeSession = convo.rows.find((r) => r.session.id === ctrl.chatSessionId) ?? null;
  const persona = ctrl.selectedPersona ?? activeSession?.persona ?? null;
  const mentor = mentorFor(persona ?? (activeSession?.session.personaId ? { id: activeSession.session.personaId } : null));
  const name = mentor.name;

  // Mobile starts on the conversation list unless a conversation was just opened
  // (for example straight after choosing a mentor).
  useEffect(() => { setMobileView(ctrl.chatSessionId ? "thread" : "list"); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Larger screens: with nothing open, pick up the most recent conversation.
  useEffect(() => {
    if (isMd && convo.loaded && !ctrl.chatSessionId && convo.rows[0]) convo.open(convo.rows[0].session.id);
  }, [isMd, convo.loaded, convo.rows.length, ctrl.chatSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // When the open conversation's persona is known, keep it as the selected persona (voice, labels).
  useEffect(() => {
    if (!ctrl.selectedPersona && activeSession?.persona) dispatch({ type: "SET_PERSONA", persona: activeSession.persona });
  }, [activeSession?.persona?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (isMd === null) return <div className="h-[var(--app-height)] bg-surface" />;

  const citationModal = (
    <CitationViewerModal
      citationLabel={citation?.label ?? null}
      messageContext={citation?.messageContext}
      onClose={() => setCitation(null)}
      onAskFollowUp={(prompt) => { setCitation(null); dispatch({ type: "SET_CHAT_DRAFT", draft: prompt }); }}
    />
  );

  /* ------------------------------ mobile ------------------------------ */
  if (!isMd) {
    if (mobileView === "list" || !ctrl.chatSessionId) {
      return (
        <div className="min-h-screen bg-surface">
          <MobileChrome title="Chat" />
          <main className="w-full pb-28 pt-16">
            <ConversationScreen convo={convo} onOpen={() => setMobileView("thread")} />
          </main>
          <MobileTabs />
          {citationModal}
        </div>
      );
    }
    return (
      <div className="flex h-[var(--app-height)] flex-col overflow-hidden bg-warm-white">
        <ThreadHeader mentor={mentor} name={name} ctrl={ctrl} variant="mobile" onBack={() => setMobileView("list")} />
        <ThreadBody ctrl={ctrl} mentor={mentor} name={name} variant="mobile" onCitation={(label, messageContext) => setCitation({ label, messageContext })} />
        {citationModal}
      </div>
    );
  }

  /* ------------------------- tablet and desktop ------------------------ */
  const showPanelInline = Boolean(isLg) && panelOpen;
  const hasThread = Boolean(ctrl.chatSessionId);
  return (
    <div className="h-[var(--app-height)] overflow-hidden bg-surface">
      <ChatRail />
      <ChatTopBar />
      <main className="h-full pl-[72px] pt-16">
        <div className="relative flex h-full w-full overflow-hidden bg-warm-white">
          {showPanelInline && <ConversationPanel convo={convo} onCollapse={() => setPanelOpen(false)} />}

          {!isLg && drawerOpen && (
            <>
              <div className="absolute inset-0 z-40 bg-brand-ink/20" onClick={() => setDrawerOpen(false)} aria-hidden />
              <ConversationPanel convo={convo} className="absolute inset-y-0 left-0 z-50 animate-rise shadow-[0_16px_48px_rgba(20,17,13,0.18)]" onSelect={() => setDrawerOpen(false)} onCollapse={() => setDrawerOpen(false)} />
            </>
          )}

          <section className="relative flex min-w-0 flex-1 flex-col bg-warm-white">
            {hasThread ? (
              <>
                <ThreadHeader mentor={mentor} name={name} ctrl={ctrl} variant="web" panelOpen={isLg ? panelOpen : drawerOpen} onTogglePanel={() => (isLg ? setPanelOpen(true) : setDrawerOpen(true))} />
                <ThreadBody ctrl={ctrl} mentor={mentor} name={name} variant="web" onCitation={(label, messageContext) => setCitation({ label, messageContext })} />
              </>
            ) : (
              <>
                {!(isLg && panelOpen) && (
                  <div className="flex h-16 items-center px-4">
                    <button type="button" onClick={() => (isLg ? setPanelOpen(true) : setDrawerOpen(true))} aria-label="Show conversations" className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-high"><span className="material-symbols-outlined text-[22px]">menu</span></button>
                  </div>
                )}
                <NothingSelected onStart={() => router.push("/persona")} mentors={Object.values(MENTORS)} />
              </>
            )}
          </section>
        </div>
      </main>
      {citationModal}
    </div>
  );
}
