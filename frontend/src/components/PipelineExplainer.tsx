"use client";

import { FileSearch, KeyRound, Library, ShieldAlert } from "lucide-react";

// The four stages every check runs through, in the order the engine actually
// runs them, with a pulse travelling the rail to show direction of flow.
//
// The copy here is structural, not verdict copy — it describes the pipeline,
// which is fixed, rather than any particular answer. Verdict wording still
// comes only from the API (spec §12.1).

const STAGES = [
  {
    Icon: FileSearch,
    name: "Read it",
    plain: "Open the file or message and take its fingerprints.",
    detail:
      "A byte fingerprint, plus a perceptual one that describes what a picture looks like or what a message says — not how its bytes happen to be arranged.",
  },
  {
    Icon: KeyRound,
    name: "Look for a signature",
    plain: "Check whether a registered issuer signed it.",
    detail:
      "Almost nothing forwarded through chat still carries one — forwarding strips it. That is exactly why the next step has to exist.",
  },
  {
    Icon: Library,
    name: "Compare with the record",
    plain: "Match it against everything issuers have published.",
    detail:
      "This is the step that survives WhatsApp. A re-saved photo has entirely different bytes but the same appearance, and the same message with emoji dropped in still reads the same.",
  },
  {
    Icon: ShieldAlert,
    name: "Weigh the warning signs",
    plain: "Look for the marks of a scam.",
    detail:
      "Imitation web addresses, look-alike company names, demands for payment, known campaigns. Any one of these is enough to call something a scam.",
  },
];

export function PipelineExplainer() {
  return (
    <div>
      {/* the rail, with a pulse travelling left to right */}
      <div className="relative mb-5 hidden h-px w-full bg-hairline md:block" aria-hidden>
        <span
          className="tr-travel absolute -top-[3px] h-[7px] w-[7px] rounded-full bg-seal"
          style={{ ["--tr-delay" as string]: "0ms" }}
        />
        <span
          className="tr-travel absolute -top-[3px] h-[7px] w-[7px] rounded-full bg-seal/40"
          style={{ ["--tr-delay" as string]: "800ms" }}
        />
      </div>

      <ol className="grid gap-4 md:grid-cols-4">
        {STAGES.map(({ Icon, name, plain, detail }, i) => (
          <li
            key={name}
            className="tr-rise rounded border border-hairline bg-card p-4"
            style={{ ["--tr-delay" as string]: `${i * 110}ms` }}
          >
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-paper">
                <Icon className="h-4 w-4 text-seal" aria-hidden />
              </span>
              <span className="font-mono text-[11px] text-info">step {i + 1}</span>
            </div>
            <h3 className="mt-3 font-display text-base font-bold tracking-tight text-ink">
              {name}
            </h3>
            <p className="mt-1.5 text-sm leading-relaxed text-ink">{plain}</p>
            <p className="mt-2 border-t border-hairline pt-2 text-xs leading-relaxed text-info">
              {detail}
            </p>
          </li>
        ))}
      </ol>

      <p className="mt-4 rounded border-l-2 border-seal bg-card px-4 py-3 text-sm leading-relaxed text-info">
        <span className="font-medium text-ink">The rule that ties it together:</span> only the
        first two steps can ever produce &ldquo;genuine&rdquo;. Naming a real company and looking
        official prove nothing on their own, so a message that does both but matches nothing
        published gets &ldquo;we cannot confirm this&rdquo; — never a green tick.
      </p>
    </div>
  );
}
