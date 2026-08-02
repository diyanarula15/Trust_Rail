"use client";

import { useEffect, useRef, useState } from "react";
import { Composer } from "@/components/Composer";
import { LiveCheck } from "@/components/LiveCheck";
import { VerdictCard } from "@/components/VerdictCard";
import type { CardPayload, VerifyInput } from "@/lib/api";
import { useLiveVerification } from "@/lib/useLiveVerification";
import { useLocaleStore } from "@/lib/store";
import { UI_COPY } from "@/lib/uiCopy";

type Entry = {
  id: string;
  label: string;
  submittedImageUrl: string | null;
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

    const entry: Entry = { id: crypto.randomUUID(), label, submittedImageUrl };
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
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-2xl flex-col px-4 py-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">
            {copy.verifyTitle}
          </h1>
          <p className="mt-1 text-sm text-info">{copy.verifySubtitle}</p>
        </div>
        <button
          type="button"
          onClick={() => setLocale(locale === "en" ? "hi" : "en")}
          className="shrink-0 rounded border border-hairline px-3 py-1.5 text-sm font-medium text-ink hover:bg-paper"
        >
          {copy.toggleLabel}
        </button>
      </div>

      <div className="mt-6 flex-1 space-y-4">
        {isEmpty && (
          <div className="rounded border border-dashed border-hairline p-8 text-center">
            <p className="font-display text-lg font-semibold text-ink">{copy.emptyTitle}</p>
            <p className="mt-2 text-sm text-info">{copy.emptyHint}</p>
          </div>
        )}

        {history.map((entry) => (
          <div key={entry.id} className="space-y-3">
            <div className="ml-auto max-w-[80%] rounded bg-ink px-4 py-2 text-sm text-paper">
              {entry.label}
            </div>
            {entry.card && (
              <VerdictCard card={entry.card} submittedImageUrl={entry.submittedImageUrl} />
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
