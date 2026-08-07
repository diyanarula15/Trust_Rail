"use client";

import { useEffect, useRef, useState } from "react";

// Counts from 0 to `value` on mount and on change. Eased rather than linear
// so it decelerates into the final number instead of stopping dead.
//
// Honours prefers-reduced-motion by jumping straight to the value — a
// count-up is decoration, and the number is the information.

const DURATION_MS = 900;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

export function CountUp({
  value,
  className = "",
  suffix = "",
}: {
  value: number;
  className?: string;
  suffix?: string;
}) {
  const [shown, setShown] = useState(0);
  const frame = useRef<number | null>(null);
  const from = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setShown(value);
      return;
    }
    const start = performance.now();
    const origin = from.current;
    const delta = value - origin;

    function step(now: number) {
      const t = Math.min(1, (now - start) / DURATION_MS);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setShown(Math.round(origin + delta * eased));
      if (t < 1) frame.current = requestAnimationFrame(step);
      else from.current = value;
    }
    frame.current = requestAnimationFrame(step);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      from.current = value;
    };
  }, [value]);

  return (
    <span className={className}>
      {shown.toLocaleString()}
      {suffix}
    </span>
  );
}
