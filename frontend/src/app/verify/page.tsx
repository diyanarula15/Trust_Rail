"use client";

import { useEffect, useRef, useState } from "react";
import { Composer } from "@/components/Composer";
import { LiveCheck } from "@/components/LiveCheck";
import { TryThese } from "@/components/TryThese";
import { VerdictCard } from "@/components/VerdictCard";
import type { CardPayload, VerifyInput } from "@/lib/api";
import { useLiveVerification } from "@/lib/useLiveVerification";
import { useLocaleStore } from "@/lib/store";
import { UI_COPY } from "@/lib/uiCopy";

type Entry = {
  id: string;
  label: string;
  submittedImageUrl: string | null;
  submittedText: string | null;
  card?: CardPayload;
  error?: string;
};

export default function VerifyPage() {
  const { locale, setLocale } = useLocaleStore();
  const [history, setHistory] = useState<Entry[]>([]);
  const [current, setCurrent] = useState<Entry | null>(null);
  const live = useLiveVerification();
  const copy = UI_COPY[locale];

  async function handleSubmit(input: Omit<VerifyInput, "locale">) {
    const label = input.file
      ? input.file.name
      : input.text
        ? input.text.slice(0, 160)
        : (input.url ?? "");

    // Held in the browser only — the submitted file is never uploaded for
    // storage, so the side-by-side comparison uses this local object URL.
    const submittedImageUrl =
      input.file && input.file.type.startsWith("image/")
        ? URL.createObjectURL(input.file)
        : null;

    const entry: Entry = {
      id: crypto.randomUUID(),
      label,
      submittedImageUrl,
      submittedText: input.text ?? null,
    };
    setCurrent(entry);

    await live.run({ ...input, locale });
  }

  // Once a run settles, fold it into history so the next one starts clean.
  // The ref guards against re-folding the same run if this effect re-fires
  // before `reset()` has cleared the hook's state.
  const settling = useRef(false);
  useEffect(() => {
    if (!current || live.busy || (!live.card && !live.error)) return;
    if (settling.current) return;
    settling.current = true;

    setHistory((h) => [
      ...h,
      { ...current, card: live.card ?? undefined, error: live.error?.message },
    ]);
    setCurrent(null);
    live.reset();
    settling.current = false;
  }, [current, live]);

  const isEmpty = history.length === 0 && !current;

  return (
    <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-3xl flex-col px-6 py-10 sm:py-14">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-hairline pb-6">
        <div className="min-w-0">
          <div className="font-mono text-xs uppercase tracking-[0.18em] text-seal">
            Check anything you were sent
          </div>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            {copy.verifyTitle}
          </h1>
          <p className="mt-2.5 max-w-2xl text-[15px] leading-relaxed text-info">
            {copy.verifySubtitle}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setLocale(locale === "en" ? "hi" : "en")}
          className="shrink-0 rounded border border-hairline bg-card px-3.5 py-2 text-sm font-medium text-ink hover:bg-paper"
        >
          {copy.toggleLabel}
        </button>
      </div>

      {/* Without this, testing a real-world message reads as a bug: a genuine
          notice from a real company comes back "cannot confirm" simply because
          that company isn't in this prototype's fictional registry. */}
      <div className="mt-4 rounded border-l-2 border-seal bg-card px-4 py-3 text-sm leading-relaxed text-info">
        <span className="font-medium text-ink">Testing with a real message?</span>{" "}
        It will come back as <span className="text-ink">cannot confirm</span>, and
        that is the correct answer. This prototype&rsquo;s registry holds 12
        made-up demo companies, so nothing a real company published is in it to
        match against. Only the demo issuers can verify. Scam detection works on
        any message, real or not.
      </div>

      <div className="mt-6 flex-1 space-y-4">
        {isEmpty && <TryThese onRun={handleSubmit} busy={live.busy} />}

        {history.map((entry) => (
          <div key={entry.id} className="space-y-3">
            <div className="ml-auto max-w-[80%] rounded bg-ink px-4 py-2 text-sm text-paper">
              {entry.label}
            </div>
            {entry.card && (
              <VerdictCard
                card={entry.card}
                submittedImageUrl={entry.submittedImageUrl}
                submittedText={entry.submittedText}
              />
            )}
            {entry.error && (
              <div className="rounded border border-fake bg-card px-4 py-2 text-sm text-fake">
                {entry.error}
              </div>
            )}
          </div>
        ))}

        {current && (
          <div className="space-y-3">
            <div className="ml-auto max-w-[80%] rounded bg-ink px-4 py-2 text-sm text-paper">
              {current.label}
            </div>
            <LiveCheck
              stages={live.stages}
              pending={live.pending}
              done={!live.busy && !!live.card}
            />
          </div>
        )}
      </div>

      <div className="sticky bottom-4 mt-6">
        <Composer onSubmit={handleSubmit} busy={live.busy} copy={copy} />
      </div>
    </div>
  );
}
