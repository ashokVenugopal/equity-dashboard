"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

interface ScrollSectionProps {
  id: string;
  title?: string;
  children: React.ReactNode;
  pin?: boolean;
}

/**
 * GSAP ScrollTrigger wrapper for section-based scrolling.
 * Supports pinning (section stays locked while content transitions)
 * and snap behavior for Bloomberg-style controlled navigation.
 */
export function ScrollSection({ id, title, children, pin = false }: ScrollSectionProps) {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!sectionRef.current || !pin) return;

    const trigger = ScrollTrigger.create({
      trigger: sectionRef.current,
      start: "top top",
      end: "bottom top",
      pin: true,
      pinSpacing: true,
    });

    return () => {
      trigger.kill();
    };
  }, [pin]);

  return (
    <section
      ref={sectionRef}
      id={id}
      className="snap-section min-h-[50vh] py-4"
    >
      {title && (
        <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-4">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}
