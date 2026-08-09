"use client";

import { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { CardPayload } from "@/lib/api";
import { MatchEvidence } from "./MatchEvidence";
import { PipelineTrace } from "./PipelineTrace";

// Plain language leads. Everything technical — reason codes, the formal §11
// copy, the pipeline trace, the hash comparison — sits behind one disclosure,
// so an investor gets a sentence they understand and a judge is two clicks
// from the full working. Neither register is invented here: both come from
// the API's localized render (spec §12.1).

const VERDICT_STYLE: Record<
  string,
  { color: string; border: string; bg: string; Icon: typeof ShieldCheck }
> = {
  VERIFIED: {
    color: "text-verified",
    border: "border-verified",
    bg: "bg-verified/5",
    Icon: ShieldCheck,
  },
  VERIFIED_NOTICE: {
    color: "text-notice",
    border: "border-notice",
    bg: "bg-notice/5",
    Icon: ShieldAlert,
  },
  OFFICIAL_CLAIM_UNVERIFIED: {
    color: "text-notice",
    border: "border-notice",
    bg: "bg-notice/5",
    Icon: AlertTriangle,
  },
  LIKELY_FAKE: {
    color: "text-fake",
    border: "border-fake",
    bg: "bg-fake/5",
    Icon: AlertTriangle,
  },
  INFORMATIONAL: {
    color: "text-info",
    border: "border-info",
    bg: "bg-paper",
    Icon: Info,
  },
};

export function VerdictCard({
  card,
  submittedImageUrl,
  submittedText,
}: {
  card: CardPayload;
  /** Object URL of the file just sent, for the side-by-side comparison.
   * Absent on a re-render — the server never keeps what was submitted. */
  submittedImageUrl?: string | null;
  /** The message just sent, for the wording comparison on a text result. */
  submittedText?: string | null;
}) {
  const [detailOpen, setDetailOpen] = useState(false);
  const style = VERDICT_STYLE[card.verdict] ?? VERDICT_STYLE.INFORMATIONAL;
  const { Icon } = style;
  const traceButton = card.buttons.find((b) => b.kind === "expand_trace");
  // "#" is SEBI_CHECK_URL's unset-placeholder value (this prototype has no
  // real target for it) — rendering it as a clickable link would be a dead
  // button; the same reminder already appears in `card.advice` as plain text.
  const otherButtons = card.buttons.filter((b) => b.kind !== "expand_trace" && b.url !== "#");
  const plainReasons =
    card.plain_reason_strings?.length > 0 ? card.plain_reason_strings : card.reason_strings;

  return (
    <div className={`overflow-hidden rounded border border-l-4 border-hairline ${style.border} bg-card shadow-sm`}>
      <div className={`px-5 py-4 ${style.bg}`}>
        <div className="flex items-start gap-3">
          <Icon className={`mt-0.5 h-7 w-7 shrink-0 ${style.color}`} aria-hidden />
          <div className="min-w-0">
            <h3 className="font-display text-xl font-bold leading-tight tracking-tight text-ink">
              {card.plain_headline || card.headline}
            </h3>
            <p className="mt-1.5 text-[15px] leading-relaxed text-ink">
              {card.plain_body || card.body}
            </p>
          </div>
        </div>
      </div>

      <div className="px-5 py-4">
        {plainReasons.length > 0 && (
          <ul className="space-y-1.5">
            {plainReasons.map((line, i) => (
              <li key={i} className="flex gap-2 text-sm text-info">
                <span className={`mt-[7px] h-1 w-1 shrink-0 rounded-full ${style.color} bg-current`} />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}

        {card.why?.explanation && (
          <div className="mt-3 rounded border border-hairline bg-paper px-3 py-2.5">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-info">
              {card.why.label}
            </div>
            <p className="mt-1 text-sm leading-relaxed text-ink">{card.why.explanation}</p>

            {card.why.escalated_by.length > 0 && (
              <div className="mt-2">
                <span className="text-xs font-medium text-info">
                  {card.why.escalated_by_label}
                </span>
                <ul className="mt-1 space-y-0.5">
                  {card.why.escalated_by.map((line, i) => (
                    <li key={i} className={`flex gap-1.5 text-xs ${style.color}`}>
                      <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full bg-current" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {card.why.strict_note && (
              <p className="mt-2 border-t border-hairline pt-2 text-xs leading-relaxed text-info">
                {card.why.strict_note}
              </p>
            )}
          </div>
        )}

        {(card.matched_entity || card.matched_communication) && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-hairline pt-3 font-mono text-xs text-info">
            {card.matched_entity && <span>{card.matched_entity.sebi_reg_no}</span>}
            {card.matched_communication?.published_at && (
              <span>published {card.matched_communication.published_at.slice(0, 10)}</span>
            )}
            {card.matched_communication?.log_seq !== null &&
              card.matched_communication?.log_seq !== undefined && (
                <span>public record #{card.matched_communication.log_seq}</span>
              )}
          </div>
        )}

        {card.advice.length > 0 && (
          <ul className="mt-3 space-y-1 rounded bg-paper px-3 py-2 text-sm text-ink">
            {card.advice.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {otherButtons.map((b) => (
            <a
              key={b.kind}
              href={b.url}
              className={`rounded px-3 py-1.5 text-sm font-medium ${
                b.kind === "certificate"
                  ? "bg-ink text-paper hover:opacity-90"
                  : "border border-hairline text-ink hover:bg-paper"
              }`}
            >
              {b.label}
            </a>
          ))}
          {traceButton && (
            <button
              type="button"
              onClick={() => setDetailOpen((v) => !v)}
              aria-expanded={detailOpen}
              className="flex items-center gap-1 rounded border border-hairline px-3 py-1.5 text-sm font-medium text-ink hover:bg-paper"
            >
              {traceButton.label}
              {detailOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
          )}
        </div>

        {detailOpen && (
          <div className="mt-4 space-y-4 border-t border-hairline pt-4">
            {card.match_evidence && card.evidence_copy && (
              <MatchEvidence
                evidence={card.match_evidence}
                copy={card.evidence_copy}
                submittedImageUrl={submittedImageUrl}
                submittedText={submittedText}
              />
            )}
            <div>
              <div className="mb-2 font-display text-xs font-semibold uppercase tracking-wide text-info">
                Steps we ran
              </div>
              <PipelineTrace trace={card.pipeline_trace} />
            </div>
            <details className="group">
              <summary className="cursor-pointer list-none font-display text-xs font-semibold uppercase tracking-wide text-info hover:text-ink">
                Formal result codes
              </summary>
              <div className="mt-2 rounded bg-paper p-3">
                <p className="text-sm text-ink">{card.body}</p>
                <ul className="mt-2 space-y-1">
                  {card.reasons.map((code, i) => (
                    <li key={code} className="text-xs text-info">
                      <span className="font-mono text-ink">{code}</span>
                      {card.reason_strings[i] ? `: ${card.reason_strings[i]}` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
