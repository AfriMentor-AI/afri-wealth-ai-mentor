"use client";

import React, { createContext, useContext, useEffect, useMemo, useReducer } from "react";
import type { ChatMessage, Persona, Profile, ThemeName } from "./types";

// Theme is persisted to localStorage, scoped to this browser/device — there's
// no backend user account yet (that's G1.3's job). Once real auth exists,
// this preference should sync to the user's account too, so it follows them
// across devices, not just live in this browser's storage.
const THEME_STORAGE_KEY = "afrimentor-theme";

interface AppState {
  theme: ThemeName;
  profile: Profile | null;
  selectedPersona: Persona | null;
  chatMessages: ChatMessage[];
  chatDraft: string;
  feedbackModalOpen: boolean;
  dailyActionDone: boolean;
  libraryFavorites: Set<string>;
  libraryFilter: string | null;
}

type Action =
  | { type: "SET_THEME"; theme: ThemeName }
  | { type: "TOGGLE_THEME" }
  | { type: "SET_PROFILE"; profile: Profile }
  | { type: "SET_PERSONA"; persona: Persona }
  | { type: "SET_CHAT_MESSAGES"; messages: ChatMessage[] }
  | { type: "APPEND_CHAT_MESSAGE"; message: ChatMessage }
  | { type: "SET_CHAT_DRAFT"; draft: string }
  | { type: "OPEN_FEEDBACK_MODAL" }
  | { type: "CLOSE_FEEDBACK_MODAL" }
  | { type: "MARK_DAILY_ACTION_DONE" }
  | { type: "TOGGLE_LIBRARY_FAVORITE"; id: string }
  | { type: "SET_LIBRARY_FILTER"; category: string | null };

const initialState: AppState = {
  theme: "heritage",
  profile: null,
  selectedPersona: null,
  chatMessages: [],
  chatDraft: "",
  feedbackModalOpen: false,
  dailyActionDone: false,
  libraryFavorites: new Set(),
  libraryFilter: null,
};

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "SET_THEME":
      return { ...state, theme: action.theme };
    case "TOGGLE_THEME":
      return { ...state, theme: state.theme === "heritage" ? "nocturnal" : "heritage" };
    case "SET_PROFILE":
      return { ...state, profile: action.profile };
    case "SET_PERSONA":
      return { ...state, selectedPersona: action.persona };
    case "SET_CHAT_MESSAGES":
      return { ...state, chatMessages: action.messages };
    case "APPEND_CHAT_MESSAGE":
      return { ...state, chatMessages: [...state.chatMessages, action.message] };
    case "SET_CHAT_DRAFT":
      return { ...state, chatDraft: action.draft };
    case "OPEN_FEEDBACK_MODAL":
      return { ...state, feedbackModalOpen: true };
    case "CLOSE_FEEDBACK_MODAL":
      return { ...state, feedbackModalOpen: false };
    case "MARK_DAILY_ACTION_DONE":
      return { ...state, dailyActionDone: true };
    case "TOGGLE_LIBRARY_FAVORITE": {
      const next = new Set(state.libraryFavorites);
      if (next.has(action.id)) next.delete(action.id);
      else next.add(action.id);
      return { ...state, libraryFavorites: next };
    }
    case "SET_LIBRARY_FILTER":
      return { ...state, libraryFilter: action.category };
    default:
      return state;
  }
}

const AppStateContext = createContext<AppState | null>(null);
const AppDispatchContext = createContext<React.Dispatch<Action> | null>(null);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState, (init) => {
    // Lazy init runs during the client's first render pass. Guarded for SSR
    // (no window there) — this doesn't cause a hydration mismatch since
    // `theme` never changes what the server-rendered DOM structure looks
    // like, only a `data-theme` attribute applied after mount (see below),
    // which the blocking inline script in app/layout.tsx already set
    // correctly before first paint anyway. This just brings React's state
    // in sync with what's already on the page.
    if (typeof window === "undefined") return init;
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as ThemeName | null;
    return stored === "heritage" || stored === "nocturnal" ? { ...init, theme: stored } : init;
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", state.theme);
    window.localStorage.setItem(THEME_STORAGE_KEY, state.theme);
  }, [state.theme]);

  const memoState = useMemo(() => state, [state]);

  return (
    <AppStateContext.Provider value={memoState}>
      <AppDispatchContext.Provider value={dispatch}>{children}</AppDispatchContext.Provider>
    </AppStateContext.Provider>
  );
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used within AppStateProvider");
  return ctx;
}

export function useAppDispatch() {
  const ctx = useContext(AppDispatchContext);
  if (!ctx) throw new Error("useAppDispatch must be used within AppStateProvider");
  return ctx;
}
