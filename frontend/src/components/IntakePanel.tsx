"use client";

import { useState } from "react";
import { Building2, MessageSquare, PenLine, Play, RefreshCw } from "lucide-react";
import { runIngest, type IngestStatus } from "@/lib/api";
import { Card } from "@/components/ui";

// How communications get into the record in the first place. This is the
// half of the product people miss: verification is only possible because
// something authoritative was published first, and the argument for this
// being a rail rather than another portal is that the two feeds below are
// infrastructure that already exists.

const SOURCE_META: Record<
  string,
  { Icon: typeof Building2; label: string; what: string; accent: string }
> = {
  exchange_filings: {
    Icon: Building2,
    label: "Exchange filings",
    what:
      "Corporate announcements as exchanges already publish them. Companies file these today; nothing new is asked of them.",
    accent: "border-l-seal",
  },
  dlt_sms: {
    Icon: MessageSquare,
    label: "DLT SMS registry",
    what:
      "Every commercial SMS sender header and message template is pre-registered under TRAI's DLT rules. That registry is the authoritative wording — we sign it so a received SMS can be checked against it.",
    accent: "border-l-info",
  },
  issuer_console: {
    Icon: PenLine,
    label: "Issuer console",
    what:
      "Manual publishing with maker-checker approval, for anything not covered by a feed.",
    accent: "border-l-ink",
  },
};

export function IntakePanel({
  status,
  onRefresh,
}: {
  status: IngestStatus | null;
  onRefresh: () => void;
}) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function poll() {
    setRunning(true);
    setResult(null);
    const r = await runIngest();
    setRunning(false);
    if (r.ok && r.data) {
      setResult(
        r.data.published > 0
          ? `Published ${r.data.published} new communication${r.data.published === 1 ? "" : "s"}.`
          : "Nothing new — everything in the feeds is already published."
      );
      onRefresh();
    } else {
      setResult("Could not poll the feeds.");
    }
  }

  // The three intake paths are a fixed property of the system, not something
  // discovered from a response — so they render immediately and fill in their
  // counts when data arrives, rather than the section appearing empty on first
  // paint and popping into existence a moment later.
  const rows = [
    {
      key: "exchange_filings",
      count: status?.feeds.find((f) => f.name === "exchange_filings")?.ingested ?? 0,
      origin: status?.feeds.find((f) => f.name === "exchange_filings")?.origin ?? "",
      live: status?.feeds.find((f) => f.name === "exchange_filings")?.live ?? false,
    },
    {
      key: "dlt_sms",
      count: status?.feeds.find((f) => f.name === "dlt_sms")?.ingested ?? 0,
      origin: status?.feeds.find((f) => f.name === "dlt_sms")?.origin ?? "",
      live: status?.feeds.find((f) => f.name === "dlt_sms")?.live ?? false,
    },
    {
      key: "issuer_console",
      count: status?.by_source?.issuer_console ?? 0,
      origin: "manual, maker-checker",
      live: true,
    },
  ];

  return (
    <div>
      <div className="grid gap-3 md:grid-cols-3">
        {rows.map(({ key, count, origin, live }, i) => {
          const meta = SOURCE_META[key];
          if (!meta) return null;
          const { Icon, label, what, accent } = meta;
          return (
            <Card
              key={key}
              accent={accent}
              className="tr-rise p-4"
              {...{ style: { ["--tr-delay" as string]: `${i * 90}ms` } }}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-info" aria-hidden />
                  <span className="font-display text-sm font-bold text-ink">{label}</span>
                </span>
                <span className="font-mono text-lg text-ink">{count}</span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-info">{what}</p>
              <p className="mt-2 truncate border-t border-hairline pt-2 font-mono text-[10px] text-info">
                {!origin ? "…" : live ? origin : `sample feed · ${origin.split("/").pop()}`}
              </p>
            </Card>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 rounded border border-hairline bg-card px-4 py-3">
        <button
          type="button"
          onClick={poll}
          disabled={running}
          className="inline-flex items-center gap-1.5 rounded bg-ink px-3.5 py-2 text-sm font-semibold text-paper hover:opacity-90 disabled:opacity-40"
        >
          {running ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          Poll the feeds now
        </button>
        <p className="flex-1 text-xs leading-relaxed text-info">
          {result ?? (
            <>
              Safe to run repeatedly — content that is already published is recognised and skipped.
              Point <span className="font-mono text-ink">EXCHANGE_FEED_URL</span> or{" "}
              <span className="font-mono text-ink">DLT_SMS_FEED_URL</span> at a real endpoint and
              the same code polls that instead.
            </>
          )}
        </p>
      </div>
    </div>
  );
}
