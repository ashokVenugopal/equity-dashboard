"use client";

import { useEffect, useRef } from "react";

/**
 * Updates the URL hash as sections scroll into view.
 * Uses Intersection Observer for Bloomberg-style hash switching.
 */
export function useHashObserver(sectionIds: string[], threshold = 0.5) {
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const id = entry.target.id;
            if (id && window.location.hash !== `#${id}`) {
              history.pushState(null, "", `#${id}`);
            }
          }
        }
      },
      { threshold }
    );

    for (const id of sectionIds) {
      const el = document.getElementById(id);
      if (el) observerRef.current.observe(el);
    }

    return () => {
      observerRef.current?.disconnect();
    };
  }, [sectionIds, threshold]);
}
