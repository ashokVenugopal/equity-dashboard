"use client";

import { useEffect, useRef } from "react";

/**
 * Updates the URL hash as sections scroll into view.
 * Uses Intersection Observer for Bloomberg-style hash switching.
 */
export function useHashObserver(sectionIds: string[], threshold = 0.5) {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const scrollingRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (scrollingRef.current) return; // Don't update hash during programmatic scroll
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

    // Scroll to hash on back/forward navigation
    function onHashChange() {
      const hash = window.location.hash.slice(1);
      if (hash) {
        const el = document.getElementById(hash);
        if (el) {
          scrollingRef.current = true;
          el.scrollIntoView({ behavior: "smooth" });
          setTimeout(() => { scrollingRef.current = false; }, 1000);
        }
      }
    }

    window.addEventListener("hashchange", onHashChange);

    // Scroll to initial hash on mount
    if (window.location.hash) {
      setTimeout(onHashChange, 100);
    }

    return () => {
      observerRef.current?.disconnect();
      window.removeEventListener("hashchange", onHashChange);
    };
  }, [sectionIds, threshold]);
}
