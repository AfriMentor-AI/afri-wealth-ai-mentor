"use client";

import { useEffect, useRef, useState } from "react";
import { fetchChatMessages, sendMessageStream, stripThinkTags, tagCommitment, createGoal, fetchGoals } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { startAudioRecording, playTextToSpeech, stopCurrentSpeech, type ActiveRecording } from "@/lib/voice";
import { useAppDispatch, useAppState } from "@/lib/store";

function cleanTextForSpeech(text: string): string {
  return stripThinkTags(text)
    .replace(/[#*_`~]/g, "")
    .replace(/\|[-:\s|]+\|/g, "")
    .replace(/\|/g, ", ")
    .replace(/\n+/g, ". ")
    .trim();
}

/**
 * All chat behaviour (streaming, voice recording, text-to-speech, commitment
 * tagging) lives here, unchanged in logic from the previous UI. The layout
 * components only render what this returns.
 */
export function useChatController() {
  const { chatMessages, chatDraft, profile, chatSessionId, activeGoalId, selectedPersona } = useAppState();
  const dispatch = useAppDispatch();

  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [playingAudioMessageId, setPlayingAudioMessageId] = useState<string | null>(null);
  const activeRecordingRef = useRef<ActiveRecording | null>(null);
  const [commitmentTagged, setCommitmentTagged] = useState(false);
  const [goalPickerGoals, setGoalPickerGoals] = useState<{ id: string; title: string }[] | null>(null);
  const [newGoalInput, setNewGoalInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const lastSentRef = useRef<string>("");
  const abortStreamRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!isRecording) { setRecordSeconds(0); return; }
    const t = setInterval(() => setRecordSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [isRecording]);

  // Opening a conversation whose messages haven't been loaded yet.
  useEffect(() => {
    if (chatSessionId && chatMessages.length === 0) {
      fetchChatMessages(chatSessionId).then((messages) => dispatch({ type: "SET_CHAT_MESSAGES", messages }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatSessionId]);

  // Switching conversation resets transient state.
  useEffect(() => {
    abortStreamRef.current?.();
    abortStreamRef.current = null;
    setIsTyping(false); setStreamingContent(null); setCommitmentTagged(false);
    setGoalPickerGoals(null); setSendError(null);
    stopCurrentSpeech(); setPlayingAudioMessageId(null);
  }, [chatSessionId]);

  async function toggleVoiceRecording() {
    if (isRecording) {
      setIsRecording(false);
      setIsTranscribing(true);
      try {
        if (activeRecordingRef.current) {
          const text = await activeRecordingRef.current.stop();
          activeRecordingRef.current = null;
          if (text && text.trim()) send(text.trim(), true);
        }
      } catch (err) {
        console.error("Voice transcription error:", err);
      } finally {
        setIsTranscribing(false);
      }
    } else {
      try {
        const recording = await startAudioRecording((interim) => {
          if (interim) dispatch({ type: "SET_CHAT_DRAFT", draft: interim });
        });
        activeRecordingRef.current = recording;
        setIsRecording(true);
      } catch (err) {
        console.error("Microphone access error:", err);
        alert("Please enable microphone permissions in your browser to record voice notes.");
      }
    }
  }

  function cancelRecording() {
    try { activeRecordingRef.current?.cancel(); } catch { /* ignore */ }
    activeRecordingRef.current = null;
    setIsRecording(false);
    dispatch({ type: "SET_CHAT_DRAFT", draft: "" });
  }

  async function handlePlayTTS(messageId: string, text: string) {
    if (playingAudioMessageId === messageId) {
      stopCurrentSpeech();
      setPlayingAudioMessageId(null);
      return;
    }
    const clean = cleanTextForSpeech(text);
    if (!clean) return;
    try {
      setPlayingAudioMessageId(messageId);
      await playTextToSpeech(clean, selectedPersona?.id || "chioma", () => setPlayingAudioMessageId(null));
    } catch (err) {
      console.error("TTS playback error:", err);
      setPlayingAudioMessageId(null);
    }
  }

  function stopSpeaking() {
    stopCurrentSpeech();
    setPlayingAudioMessageId(null);
  }

  function send(customText?: string | React.MouseEvent, autoPlayVoiceReply = false) {
    const textToSend = (typeof customText === "string" ? customText : chatDraft).trim();
    if (!textToSend || !chatSessionId || isTyping) return;

    abortStreamRef.current?.();
    setSendError(null);
    lastSentRef.current = textToSend;

    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      userId: profile?.userId ?? "local-user",
      sender: "user",
      content: textToSend,
      created_at: new Date().toISOString(),
    };
    dispatch({ type: "APPEND_CHAT_MESSAGE", message: userMessage });
    dispatch({ type: "SET_CHAT_DRAFT", draft: "" });

    setIsTyping(true);
    setStreamingContent(null);

    const abort = sendMessageStream(
      chatSessionId,
      userMessage.content,
      (chunk) => {
        setIsTyping(false);
        setStreamingContent((prev) => (prev ?? "") + chunk);
      },
      (assistantMessage) => {
        setStreamingContent(null);
        setIsTyping(false);
        dispatch({ type: "APPEND_CHAT_MESSAGE", message: assistantMessage });
        setCommitmentTagged(false);
        abortStreamRef.current = null;
        if (autoPlayVoiceReply && assistantMessage.content) handlePlayTTS(assistantMessage.id, assistantMessage.content);
      },
      (error) => {
        console.error("Stream error:", error);
        setStreamingContent(null);
        setIsTyping(false);
        abortStreamRef.current = null;
        setSendError("Message not sent. Check your connection and try again.");
      },
    );
    abortStreamRef.current = abort;
  }

  function retryLast() {
    const text = lastSentRef.current;
    if (!text) return;
    setSendError(null);
    send(text);
  }

  async function confirmTagWithGoal(goalId: string) {
    if (!chatSessionId || chatMessages.length === 0) return;
    const lastMessage = chatMessages[chatMessages.length - 1];
    setGoalPickerGoals(null);
    setNewGoalInput("");
    try {
      await tagCommitment(chatSessionId, lastMessage.id, goalId);
      dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId });
      setCommitmentTagged(true);
    } catch (error) {
      console.error("Failed to tag commitment:", error);
    }
  }

  async function handleTagCommitment() {
    if (!chatSessionId || chatMessages.length === 0) return;
    const lastMessage = chatMessages[chatMessages.length - 1];
    if (lastMessage.sender !== "mentor" || !lastMessage.is_commitment_candidate) return;

    if (activeGoalId) { await confirmTagWithGoal(activeGoalId); return; }
    try {
      const goals = await fetchGoals();
      if (goals.length === 1) {
        dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: goals[0].id });
        await confirmTagWithGoal(goals[0].id);
      } else if (goals.length > 1) {
        setGoalPickerGoals(goals.map((g) => ({ id: g.id, title: g.title })));
      } else {
        const newGoal = await createGoal({ title: "My Financial Goal", description: undefined });
        dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: newGoal.id });
        await confirmTagWithGoal(newGoal.id);
      }
    } catch (e) {
      console.warn("Could not retrieve goals:", e);
    }
  }

  const last = chatMessages[chatMessages.length - 1];
  const showCommitmentPrompt = Boolean(last && last.sender === "mentor" && last.is_commitment_candidate && !commitmentTagged);

  return {
    chatMessages, chatDraft, chatSessionId, profile, selectedPersona, dispatch,
    isRecording, isTranscribing, recordSeconds, playingAudioMessageId,
    isTyping, streamingContent, sendError, setSendError,
    goalPickerGoals, setGoalPickerGoals, newGoalInput, setNewGoalInput, showCommitmentPrompt,
    toggleVoiceRecording, cancelRecording, handlePlayTTS, stopSpeaking, send, retryLast,
    handleTagCommitment, confirmTagWithGoal,
  };
}
export type ChatController = ReturnType<typeof useChatController>;
