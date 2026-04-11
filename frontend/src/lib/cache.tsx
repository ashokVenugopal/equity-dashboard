"use client";

import { createContext, useContext, useRef, useCallback, useState } from "react";

interface CacheEntry<T> {
  data: T;
  loadedAt: number; // Unix ms
  key: string;
}

interface CacheContextType {
  get: <T>(key: string) => CacheEntry<T> | null;
  set: <T>(key: string, data: T) => void;
  invalidate: (key: string) => void;
  isStale: (key: string, maxAgeMs: number) => boolean;
}

const CacheContext = createContext<CacheContextType | null>(null);

const DEFAULT_MAX_AGE_MS = 5 * 60 * 1000; // 5 minutes

export function CacheProvider({ children }: { children: React.ReactNode }) {
  const store = useRef<Map<string, CacheEntry<unknown>>>(new Map());

  const get = useCallback(<T,>(key: string): CacheEntry<T> | null => {
    const entry = store.current.get(key);
    if (!entry) return null;
    return entry as CacheEntry<T>;
  }, []);

  const set = useCallback(<T,>(key: string, data: T) => {
    store.current.set(key, { data, loadedAt: Date.now(), key });
  }, []);

  const invalidate = useCallback((key: string) => {
    store.current.delete(key);
  }, []);

  const isStale = useCallback((key: string, maxAgeMs: number = DEFAULT_MAX_AGE_MS) => {
    const entry = store.current.get(key);
    if (!entry) return true;
    return Date.now() - entry.loadedAt > maxAgeMs;
  }, []);

  return (
    <CacheContext.Provider value={{ get, set, invalidate, isStale }}>
      {children}
    </CacheContext.Provider>
  );
}

/**
 * Hook for cached data fetching.
 * Returns cached data on tab switch, fetches fresh data if stale.
 * Shows "loaded at" timestamp and supports manual refresh.
 */
export function useCachedData<T>(
  key: string,
  fetcher: () => Promise<T>,
  maxAgeMs: number = DEFAULT_MAX_AGE_MS,
): {
  data: T | null;
  loading: boolean;
  loadedAt: Date | null;
  refresh: () => void;
  error: string | null;
} {
  const cache = useContext(CacheContext);
  const [data, setData] = useState<T | null>(() => {
    return cache?.get<T>(key)?.data ?? null;
  });
  const [loading, setLoading] = useState(false);
  const [loadedAt, setLoadedAt] = useState<Date | null>(() => {
    const entry = cache?.get<T>(key);
    return entry ? new Date(entry.loadedAt) : null;
  });
  const [error, setError] = useState<string | null>(null);
  const fetchedRef = useRef(false);

  const doFetch = useCallback(async (force = false) => {
    if (!force && cache) {
      const entry = cache.get<T>(key);
      if (entry && !cache.isStale(key, maxAgeMs)) {
        setData(entry.data);
        setLoadedAt(new Date(entry.loadedAt));
        return;
      }
    }

    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
      const now = new Date();
      setLoadedAt(now);
      cache?.set(key, result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [key, fetcher, cache, maxAgeMs]);

  // Auto-fetch on first render if no cached data or stale
  if (!fetchedRef.current) {
    fetchedRef.current = true;
    const entry = cache?.get<T>(key);
    if (!entry || cache?.isStale(key, maxAgeMs)) {
      doFetch();
    }
  }

  const refresh = useCallback(() => {
    cache?.invalidate(key);
    doFetch(true);
  }, [doFetch, cache, key]);

  return { data, loading, loadedAt, refresh, error };
}
