"use client";

import { useState, useEffect, useCallback } from "react";
import { getDataFreshness, type DataFreshness } from "./api";

let cachedFreshness: DataFreshness | null = null;
let cachedAt: number = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

/**
 * Shared hook for data freshness. Fetches once and caches globally.
 * All pages share the same cached result.
 */
export function useDataFreshness() {
  const [freshness, setFreshness] = useState<DataFreshness | null>(cachedFreshness);

  const refresh = useCallback(async () => {
    try {
      const data = await getDataFreshness();
      cachedFreshness = data;
      cachedAt = Date.now();
      setFreshness(data);
    } catch {
      // Silently fail — freshness is informational
    }
  }, []);

  useEffect(() => {
    if (cachedFreshness && Date.now() - cachedAt < CACHE_TTL) {
      setFreshness(cachedFreshness);
      return;
    }
    refresh();
  }, [refresh]);

  return freshness;
}
