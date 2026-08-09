"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Fades and rises its children in once they scroll into view, then leaves
 * them alone — a one-shot reveal, not a re-triggering scroll-jack. Content
 * already in the viewport on first paint (nothing above the fold needs a
 * scroll to reach) still gets the same transition, just fired immediately.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -10% 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`tr-reveal ${visible ? "is-visible" : ""} ${className}`}
      style={{ ["--tr-delay" as string]: `${delay}ms` }}
    >
      {children}
    </div>
  );
}
