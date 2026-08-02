"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  VERIFY_STAGES,
  verifyStream,
  type ApiError,
  type CardPayload,
  type StageEvent,
  type VerifyInput,
} from "@/lib/api";

/**
 * Drives a streamed verification and paces its reveal.
 *
 * The stages themselves arrive when the server actually finishes them — this
 * hook never fabricates progress, and the `ms` on each stage is the real
 * server measurement. What it does add is a floor on how fast rows appear:
 * the image pipeline finishes in ~40ms end to end, which would flash past
 * unreadably. So events queue up and are revealed no faster than
 * MIN_DWELL_MS apart, and the verdict is held until the last stage has been
 * shown.
 *
 * The result is honest about *what* happened and readable about *when* it is
 * shown. For a video (~1s of ffmpeg on the first stage) the queue is empty
 * most of the time and the pacing does nothing at all — you are watching the
 * real thing.
 */
const MIN_DWELL_MS = 420;
const POLL_MS = 60;

export interface LiveVerification {
  stages: StageEvent[];
  pending: StageEvent["stage"] | null;
  card: CardPayload | null;
  error: ApiError | null;
  busy: boolean;
  run: (input: VerifyInput) => Promise<void>;
  reset: () => void;
}

export function useLiveVerification(): LiveVerification {
  const [stages, setStages] = useState<StageEvent[]>([]);
  const [pending, setPending] = useState<StageEvent["stage"] | null>(null);
  const [card, setCard] = useState<CardPayload | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const queue = useRef<StageEvent[]>([]);
  const finalCard = useRef<CardPayload | null>(null);
  const finalError = useRef<ApiError | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const reset = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    queue.current = [];
    finalCard.current = null;
    finalError.current = null;
    setStages([]);
    setPending(null);
    setCard(null);
    setError(null);
    setBusy(false);
  }, []);

  const drain = useCallback(() => {
    if (!alive.current) return;

    const next = queue.current.shift();
    if (next) {
      setStages((prev) => [...prev, next]);
      const i = VERIFY_STAGES.indexOf(next.stage);
      setPending(VERIFY_STAGES[i + 1] ?? null);
      timer.current = setTimeout(drain, MIN_DWELL_MS);
      return;
    }

    // queue empty: finish if the server is done, otherwise keep waiting
    if (finalError.current) {
      setError(finalError.current);
      setPending(null);
      setBusy(false);
      return;
    }
    if (finalCard.current) {
      setCard(finalCard.current);
      setPending(null);
      setBusy(false);
      return;
    }
    timer.current = setTimeout(drain, POLL_MS);
  }, []);

  const run = useCallback(
    async (input: VerifyInput) => {
      reset();
      setBusy(true);
      setPending(VERIFY_STAGES[0]);
      alive.current = true;
      timer.current = setTimeout(drain, MIN_DWELL_MS);

      try {
        await verifyStream(input, {
          onStage: (s) => queue.current.push(s),
          onResult: (c) => {
            finalCard.current = c;
          },
          onError: (e) => {
            finalError.current = e;
          },
        });
      } catch {
        finalError.current = {
          code: "network",
          message: "Could not reach the server.",
        };
      }
    },
    [drain, reset]
  );

  return { stages, pending, card, error, busy, run, reset };
}
