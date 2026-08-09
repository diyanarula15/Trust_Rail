"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Info,
  Library,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import {
  getIngestStatus,
  getLogRoot,
  getRecentChecks,
  getTelemetrySummary,
  listEntities,
  type IngestStatus,
  type LogRoot,
  type RecentCheck,
  type TelemetrySummary,
} from "@/lib/api";
import { IntakePanel } from "@/components/IntakePanel";
import { CountUp } from "@/components/CountUp";
import { PipelineExplainer } from "@/components/PipelineExplainer";
import { Reveal } from "@/components/Reveal";
import { Card, EmptyState, Page, PageHeader, SectionTitle } from "@/components/ui";

const POLL_MS = 10_000;

// The five answers, in severity order, each with what it actually means.
const VERDICTS = [
  {
    key: "VERIFIED",
    label: "Genuine",
    meaning: "Matches something a registered issuer really published.",
    tone: "text-verified",
    bar: "bg-verified",
    Icon: ShieldCheck,
  },
  {
    key: "VERIFIED_NOTICE",
    label: "Genuine, with a warning",
    meaning: "Really was published, but the signing key was later reported stolen.",
    tone: "text-notice",
    bar: "bg-notice",
    Icon: ShieldAlert,
  },
  {
    key: "OFFICIAL_CLAIM_UNVERIFIED",
    label: "Cannot confirm",
    meaning: "Claims to be official, but nothing published matches it. Not an accusation.",
    tone: "text-notice",
    bar: "bg-notice",
    Icon: AlertTriangle,
  },
  {
    key: "LIKELY_FAKE",
    label: "Likely a scam",
    meaning: "Carries active fraud signals: fake addresses, payment demands, known campaigns.",
    tone: "text-fake",
    bar: "bg-fake",
    Icon: AlertTriangle,
  },
  {
    key: "INFORMATIONAL",
    label: "Nothing official",
    meaning: "Makes no official claim at all. Most forwarded messages land here.",
    tone: "text-info",
    bar: "bg-info",
    Icon: Info,
  },
];

const KIND_LABEL: Record<string, string> = {
  image: "picture",
  video: "video",
  pdf: "document",
  text: "message",
  eml: "email",
  url: "link",
};

function timeAgo(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${Math.floor(secs)}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function Tile({
  value,
  label,
  hint,
  tone = "text-ink",
  loading,
  delay,
}: {
  value: number;
  label: string;
  hint: string;
  tone?: string;
  loading: boolean;
  delay: number;
}) {
  return (
    <Card
      className="tr-rise relative overflow-hidden px-4 py-4"
      // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
      {...{ style: { ["--tr-delay" as string]: `${delay}ms` } }}
    >
      {loading ? (
        <div className="tr-sweep relative h-9 w-20 rounded bg-paper" />
      ) : (
        <CountUp value={value} className={`font-mono text-3xl font-medium ${tone}`} />
      )}
      <div className="mt-1 text-sm font-medium text-ink">{label}</div>
      <div className="mt-0.5 text-xs leading-relaxed text-info">{hint}</div>
    </Card>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null);
  const [recent, setRecent] = useState<RecentCheck[]>([]);
  const [root, setRoot] = useState<LogRoot | null>(null);
  const [ingest, setIngest] = useState<IngestStatus | null>(null);
  const [entityCount, setEntityCount] = useState(0);
  const [keyCount, setKeyCount] = useState(0);
  const [loading, setLoading] = useState(true);
  // bumped by the intake panel so a manual poll refreshes immediately
  // rather than waiting out the 10s interval
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [s, r, l, g] = await Promise.all([
        getTelemetrySummary(),
        getRecentChecks(10),
        getLogRoot(),
        getIngestStatus(),
      ]);
      if (cancelled) return;
      if (s.ok && s.data) setSummary(s.data);
      if (r.ok && r.data) setRecent(r.data);
      if (l.ok && l.data) setRoot(l.data);
      if (g.ok && g.data) setIngest(g.data);
      setLoading(false);
    }
    load();
    listEntities().then((r) => {
      if (!cancelled && r.ok && r.data) {
        setEntityCount(r.data.length);
        setKeyCount(r.data.reduce((n, e) => n + e.keys.length, 0));
      }
    });
    const id = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [refreshTick]);

  const totals = summary?.totals_by_verdict ?? {};
  const total = Object.values(totals).reduce((a, b) => a + b, 0);
  const flagged = (totals["LIKELY_FAKE"] ?? 0) + (totals["OFFICIAL_CLAIM_UNVERIFIED"] ?? 0);
  const campaigns = summary?.campaigns ?? [];

  return (
    <Page wide>
      <Reveal>
        <PageHeader
          eyebrow="System overview"
          title="Dashboard"
          lead="What TrustRail is doing right now: how many messages have been checked, what the answers were, which scam campaigns are running, and the state of the tamper-proof record everything is checked against."
          actions={
            <span className="inline-flex items-center gap-2 rounded-full border border-hairline bg-card px-3 py-1.5 text-xs text-info">
              <span className="tr-breathe h-1.5 w-1.5 rounded-full bg-verified" aria-hidden />
              live · refreshes every 10s
            </span>
          }
        />
      </Reveal>

      {/* --- headline numbers --- */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          value={total}
          label="Messages checked"
          hint="In the last 14 days"
          loading={loading}
          delay={0}
        />
        <Tile
          value={flagged}
          label="Flagged"
          hint="Unconfirmed or likely a scam"
          tone="text-fake"
          loading={loading}
          delay={80}
        />
        <Tile
          value={entityCount}
          label="Registered issuers"
          hint="Companies we can verify against"
          loading={loading}
          delay={160}
        />
        <Tile
          value={root?.tree_size ?? 0}
          label="Entries in the record"
          hint="Every publication and withdrawal"
          loading={loading}
          delay={240}
        />
      </div>

      {/* --- what this actually is --- */}
      <section className="mt-12">
        <Card accent="border-l-seal" className="tr-rise p-5 sm:p-6">
          <h2 className="font-display text-xl font-bold tracking-tight text-ink sm:text-2xl">
            Detection guesses. Provenance proves.
          </h2>
          <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-info">
            Most anti-fraud tools look at a message and estimate how suspicious it seems.
            TrustRail asks a different question with a definite answer:{" "}
            <span className="font-medium text-ink">
              did a registered company actually publish this?
            </span>{" "}
            Issuers sign what they put out, it lands in a record that cannot be rewritten, and
            anyone can check a forwarded copy against it, even after the platform it travelled
            through stripped every byte of metadata and re-saved the file.
          </p>
          <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-info">
            Guessing can never produce a green tick here. Looking official and naming a real
            company are not evidence, and the engine refuses to call anything genuine without
            either a valid signature or a match against the published record.
          </p>
        </Card>
      </section>

      {/* --- how content gets in --- */}
      <section className="mt-12">
        <Reveal>
          <SectionTitle hint="Verification is only possible because something authoritative was published first. These are the ways that happens: two of them are infrastructure that already exists, so issuers are not asked to do anything new.">
            Where the record comes from
          </SectionTitle>
        </Reveal>
        <IntakePanel status={ingest} onRefresh={() => setRefreshTick((n) => n + 1)} />
      </section>

      {/* --- how a check actually works --- */}
      <section className="mt-12">
        <Reveal>
          <SectionTitle hint="Every message goes through these four steps, in this order, and stops at the first one that proves something.">
            How a check works
          </SectionTitle>
        </Reveal>
        <PipelineExplainer />
      </section>

      {/* --- what the answers mean, with live counts --- */}
      <section className="mt-12">
        <Reveal>
          <SectionTitle hint="Five possible answers. The counts are from the last 14 days.">
            What the answers mean
          </SectionTitle>
        </Reveal>
        <div className="space-y-2">
          {VERDICTS.map((v, i) => {
            const count = totals[v.key] ?? 0;
            const pct = total > 0 ? (count / total) * 100 : 0;
            return (
              <Card
                key={v.key}
                className="tr-rise p-4"
                {...{ style: { ["--tr-delay" as string]: `${i * 70}ms` } }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <v.Icon className={`mt-0.5 h-5 w-5 shrink-0 ${v.tone}`} aria-hidden />
                    <div className="min-w-0">
                      <div className={`font-display text-sm font-bold ${v.tone}`}>{v.label}</div>
                      <p className="mt-0.5 text-sm leading-relaxed text-info">{v.meaning}</p>
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="font-mono text-xl text-ink">{count}</div>
                    <div className="text-xs text-info">{pct.toFixed(0)}%</div>
                  </div>
                </div>
                <div className="mt-3 h-1.5 w-full overflow-hidden rounded bg-paper">
                  <div
                    className={`tr-grow h-full ${v.bar}`}
                    style={{
                      width: `${Math.max(pct, count > 0 ? 2 : 0)}%`,
                      ["--tr-delay" as string]: `${i * 70 + 150}ms`,
                    }}
                  />
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* --- live feed + threats --- */}
      <section className="mt-12 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <Reveal>
            <SectionTitle hint="The most recent checks. What people sent is never stored, so only the outcome is shown.">
              Live activity
            </SectionTitle>
          </Reveal>
          {recent.length === 0 ? (
            <EmptyState
              title="Nothing checked yet"
              hint="Verify a message and it will appear here within ten seconds."
              icon={<Activity className="h-6 w-6" />}
            />
          ) : (
            <Card className="divide-y divide-hairline">
              {recent.map((c, i) => {
                const v = VERDICTS.find((x) => x.key === c.verdict);
                return (
                  <div
                    key={c.id}
                    className="tr-rise flex items-center justify-between gap-3 px-4 py-2.5"
                    {...{ style: { ["--tr-delay" as string]: `${i * 45}ms` } }}
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${v?.bar ?? "bg-info"}`} />
                      <span className={`truncate text-sm font-medium ${v?.tone ?? "text-info"}`}>
                        {v?.label ?? c.verdict}
                      </span>
                      <span className="shrink-0 text-xs text-info">
                        {KIND_LABEL[c.input_kind] ?? c.input_kind}
                      </span>
                      {c.campaign && (
                        <span className="hidden shrink-0 rounded bg-fake/10 px-1.5 py-0.5 font-mono text-[10px] text-fake sm:inline">
                          {c.campaign}
                        </span>
                      )}
                    </div>
                    <span className="shrink-0 font-mono text-xs text-info">
                      {timeAgo(c.created_at)}
                    </span>
                  </div>
                );
              })}
            </Card>
          )}
        </div>

        <div>
          <Reveal>
            <SectionTitle hint="Groups of messages sharing a fake address, image or phrase: one operation seen repeatedly.">
              Scam campaigns running now
            </SectionTitle>
          </Reveal>
          {campaigns.length === 0 ? (
            <EmptyState title="No campaigns detected" />
          ) : (
            <div className="space-y-2">
              {campaigns.map((c, i) => (
                <Card
                  key={c.campaign}
                  accent="border-l-fake"
                  className="tr-rise flex items-center justify-between gap-3 p-4"
                  {...{ style: { ["--tr-delay" as string]: `${i * 70}ms` } }}
                >
                  <div className="min-w-0">
                    <div className="truncate font-mono text-sm font-medium text-fake">
                      {c.campaign}
                    </div>
                    <div className="mt-0.5 text-xs text-info">
                      seen on {c.channels.join(", ")} · last {c.last_seen.slice(0, 10)}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="font-mono text-xl text-ink">{c.count}</div>
                    <div className="text-xs text-info">sightings</div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          <div className="mt-6">
            <Reveal>
              <SectionTitle hint="Whose name scammers put on messages most often.">
                Most imitated
              </SectionTitle>
            </Reveal>
            {(summary?.top_impersonated ?? []).length === 0 ? (
              <EmptyState title="No impersonation recorded" />
            ) : (
              <Card className="p-4">
                {(summary?.top_impersonated ?? []).slice(0, 5).map((e, i) => {
                  const max = summary?.top_impersonated?.[0]?.count || 1;
                  return (
                    <div key={e.entity} className="py-1.5">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="truncate text-ink">{e.entity}</span>
                        <span className="shrink-0 font-mono text-info">{e.count}</span>
                      </div>
                      <div className="mt-1 h-1 w-full overflow-hidden rounded bg-paper">
                        <div
                          className="tr-grow h-full bg-fake"
                          style={{
                            width: `${(e.count / max) * 100}%`,
                            ["--tr-delay" as string]: `${i * 60}ms`,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </Card>
            )}
          </div>
        </div>
      </section>

      {/* --- the record everything is checked against --- */}
      <section className="mt-12">
        <Reveal>
          <SectionTitle hint="Issuers publish into an append-only record. Nothing can be altered or removed after the fact without its fingerprint changing.">
            The record behind every answer
          </SectionTitle>
        </Reveal>
        <Card accent="border-l-ink" className="p-5">
          <div className="grid gap-5 sm:grid-cols-3">
            <div>
              <div className="font-mono text-2xl text-ink">
                <CountUp value={root?.tree_size ?? 0} />
              </div>
              <div className="mt-0.5 text-xs text-info">entries, append-only</div>
            </div>
            <div>
              <div className="font-mono text-2xl text-ink">
                <CountUp value={entityCount} />
              </div>
              <div className="mt-0.5 text-xs text-info">registered issuers</div>
            </div>
            <div>
              <div className="font-mono text-2xl text-ink">
                <CountUp value={keyCount} />
              </div>
              <div className="mt-0.5 text-xs text-info">signing keys tracked</div>
            </div>
          </div>

          {root && (
            <div className="mt-5 border-t border-hairline pt-4">
              <div className="text-xs uppercase tracking-wide text-info">
                Current fingerprint of the whole record
              </div>
              <div className="mt-1.5 break-all font-mono text-sm text-ink">{root.root_hash}</div>
              <p className="mt-2 text-xs leading-relaxed text-info">
                Change any entry and this fingerprint changes with it. Your browser checks it
                independently on the public record page.
              </p>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href="/log"
              className="inline-flex items-center gap-1.5 rounded border border-hairline px-3.5 py-2 text-sm font-semibold text-ink hover:bg-paper"
            >
              <Library className="h-4 w-4" /> Inspect the record
            </a>
            <a
              href="/verify"
              className="inline-flex items-center gap-1.5 rounded bg-ink px-3.5 py-2 text-sm font-semibold text-paper hover:opacity-90"
            >
              Check a message <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Card>
      </section>
    </Page>
  );
}
