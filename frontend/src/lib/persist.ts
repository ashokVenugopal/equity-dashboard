"use client";

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

/*
 * UI-position persistence (sessionStorage, per browser tab).
 *
 * Only view state is remembered — selected tab, filters, drill-down,
 * chart anchors. Data itself is refetched from the backend on every
 * mount, so restored positions always show current data (the pipeline
 * refreshes it on the nightly schedule). Entries expire after 20h so a
 * long-abandoned tab starts fresh.
 */

const TTL_MS = 20 * 60 * 60 * 1000;
const PREFIX = "eqdash:";

export function loadState<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = sessionStorage.getItem(PREFIX + key);
    if (!raw) return fallback;
    const { t, v } = JSON.parse(raw);
    if (typeof t !== "number" || Date.now() - t > TTL_MS) return fallback;
    return v as T;
  } catch {
    return fallback;
  }
}

export function saveState(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(PREFIX + key, JSON.stringify({ t: Date.now(), v: value }));
  } catch {
    /* storage full/blocked — persistence is best-effort */
  }
}

/**
 * Drop-in useState replacement that survives tab switches and page
 * navigation. Hydration-safe: first render uses `initial` (matching
 * SSR), the stored value is applied on mount, and saves only begin
 * after that restore so the stored value is never clobbered.
 */
export function usePersistentState<T>(
  key: string,
  initial: T,
): [T, Dispatch<SetStateAction<T>>] {
  const [state, setState] = useState<T>(initial);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    setState(loadState(key, initial));
    setRestored(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (restored) saveState(key, state);
  }, [restored, key, state]);

  return [state, setState];
}
