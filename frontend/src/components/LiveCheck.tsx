"use client";

import { Check, Loader2 } from "lucide-react";
import type { StageEvent } from "@/lib/api";
import { VERIFY_STAGES } from "@/lib/api";

// The check as it happens. Rows are known up front and shown greyed out, so
// the reader can see what is *about* to be looked at rather than having rows
// appear from nowhere.
//
// Honesty note: stage arrival is genuinely driven by the server finishing
// each stage — nothing here invents progress. The *reveal* is paced by
// useLiveStages (a minimum dwell so a 3ms stage is still readable), but the
// duration printed on each row is the real measured server time.

const STAGE_HINT: Record<StageEvent["stage"], string> = {
  reading: "Reading it the way a computer sees it",
  signature: "Official files can carry a tamper-proof signature",
  registry: "Every issuer publishes into a public record",
  risk: "Scam messages share tell-tale patterns",
};

export function LiveCheck({
  stages,
  done,
  pending,
}: {
  stages: StageEvent[];
  /** true once the verdict has arrived */
  done: boolean;
  /** stage currently being worked on, if any */
  pending: StageEvent["stage"] | null;
}) {
  return (
    <div className="rounded border border-hairline bg-card p-4">
      <div className="flex items-center gap-2">
        {!done && <Loader2 className="h-4 w-4 animate-spin text-seal" aria-hidden />}
        <h3 className="font-display text-sm font-semibold text-ink">
          {done ? "Checked" : "Checking…"}
        </h3>
      </div>

      <ol className="mt-3 space-y-2.5">
        {VERIFY_STAGES.map((name) => {
          const stage = stages.find((s) => s.stage === name);
          const isPending = pending === name;
          const state = stage ? "done" : isPending ? "running" : "waiting";

          return (
            <li key={name} className="flex gap-3">
              <div className="mt-0.5 shrink-0">
                {state === "done" ? (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-verified/10">
                    <Check className="h-3.5 w-3.5 text-verified" aria-hidden />
                  </span>
                ) : state === "running" ? (
                  <span className="flex h-5 w-5 items-center justify-center">
                    <Loader2 className="h-4 w-4 animate-spin text-seal" aria-hidden />
                  </span>
                ) : (
                  <span className="flex h-5 w-5 items-center justify-center">
                    <span className="h-1.5 w-1.5 rounded-full bg-hairline" />
                  </span>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div
                  className={`text-sm transition-colors ${
                    state === "waiting" ? "text-hairline" : "text-ink"
                  }`}
                >
                  {stage?.label ?? STAGE_LABEL_FALLBACK[name]}
                  {stage && (
                    <span className="ml-2 font-mono text-[11px] text-info">{stage.ms}ms</span>
                  )}
                </div>
                <div
                  className={`mt-0.5 text-xs ${
                    state === "waiting" ? "text-hairline" : "text-info"
                  }`}
                >
                  {stage?.detail || STAGE_HINT[name]}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

// Only used before the server has told us a stage's real label (i.e. while
// the row is still greyed out and waiting).
const STAGE_LABEL_FALLBACK: Record<StageEvent["stage"], string> = {
  reading: "Opening what you sent",
  signature: "Looking for an official digital signature",
  registry: "Comparing it with everything issuers have published",
  risk: "Checking for scam warning signs",
};
