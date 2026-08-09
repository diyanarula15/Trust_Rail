"use client";

import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Radio } from "lucide-react";
import { getTelemetrySummary, type TelemetrySummary } from "@/lib/api";
import { Reveal } from "@/components/Reveal";
import { Card, EmptyState, Page, PageHeader, SectionTitle, Stat, TableWrap, Th } from "@/components/ui";

const GEO_URL = "/india_states.json";
const POLL_MS = 10_000;

// spec §14's 12 weighted states -> react-simple-maps' st_nm property
const STATE_CODE_TO_NAME: Record<string, string> = {
  "IN-MH": "Maharashtra", "IN-KA": "Karnataka", "IN-RJ": "Rajasthan",
  "IN-DL": "Delhi", "IN-UP": "Uttar Pradesh", "IN-GJ": "Gujarat",
  "IN-TN": "Tamil Nadu", "IN-TS": "Telangana", "IN-WB": "West Bengal",
  "IN-MP": "Madhya Pradesh", "IN-HR": "Haryana", "IN-PB": "Punjab",
};

const VERDICT_LABEL: Record<string, string> = {
  VERIFIED: "Genuine",
  VERIFIED_NOTICE: "Genuine, with notice",
  OFFICIAL_CLAIM_UNVERIFIED: "Unconfirmed",
  LIKELY_FAKE: "Likely fake",
  INFORMATIONAL: "No official claim",
};

// Verdicts worth a regulator's attention. "most common concern" is scoped to
// these so the KPI surfaces risk signal, not the base rate of benign,
// no-claim traffic (which dominates totals_by_verdict and would otherwise
// win every time).
const NOTABLE_VERDICTS = ["LIKELY_FAKE", "OFFICIAL_CLAIM_UNVERIFIED", "VERIFIED_NOTICE"];

function shade(count: number, max: number): string {
  if (count === 0) return "#F7F5F0";
  const t = max > 0 ? count / max : 0;
  const from = { r: 0xf7, g: 0xf5, b: 0xf0 };
  const to = { r: 0xc6, g: 0x36, b: 0x2b };
  const mix = (a: number, b: number) => Math.round(a + (b - a) * t);
  return `rgb(${mix(from.r, to.r)},${mix(from.g, to.g)},${mix(from.b, to.b)})`;
}

export default function SupervisionPage() {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const r = await getTelemetrySummary();
      if (!cancelled && r.ok && r.data) setSummary(r.data);
    }
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const totals = summary?.totals_by_verdict ?? {};
  const total = Object.values(totals).reduce((a, b) => a + b, 0);
  const flagged = (totals["LIKELY_FAKE"] ?? 0) + (totals["OFFICIAL_CLAIM_UNVERIFIED"] ?? 0);
  const pctFlagged = total > 0 ? Math.round((flagged / total) * 100) : 0;
  const topConcern = Object.entries(totals)
    .filter(([verdict]) => NOTABLE_VERDICTS.includes(verdict))
    .sort((a, b) => b[1] - a[1])[0]?.[0];

  const byNameCount = useMemo(() => {
    const map: Record<string, number> = {};
    for (const row of summary?.by_state ?? []) {
      const name = STATE_CODE_TO_NAME[row.state_code];
      if (name) map[name] = row.count_flagged;
    }
    return map;
  }, [summary]);
  const maxCount = Math.max(1, ...Object.values(byNameCount));

  return (
    <Page wide>
      <Reveal>
        <PageHeader
          eyebrow="Regulator view"
          title="Supervision"
          lead="Where impersonation attempts are landing across the country, which brands are being imitated most, and which scam campaigns are running right now. Built from real verifications as they happen."
          actions={
            <span className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-card px-3 py-1.5 text-xs text-info">
              <Radio className="h-3.5 w-3.5 text-verified" aria-hidden />
              live · refreshes every 10s
            </span>
          }
        />
      </Reveal>

      <Reveal delay={80} className="grid gap-3 sm:grid-cols-3">
        <Stat value={total} label="checks in the last 14 days" />
        <Stat value={`${pctFlagged}%`} label="unconfirmed or fake" tone="text-fake" />
        <Stat
          value={topConcern ? VERDICT_LABEL[topConcern] ?? topConcern : "None flagged"}
          label="most common concern"
        />
      </Reveal>

      <Reveal delay={140} className="mt-6 grid gap-5 lg:grid-cols-2">
        <Card className="p-4">
          <SectionTitle hint="Darker means more messages flagged as unconfirmed or fake were checked from that state.">
            Where flags are landing
          </SectionTitle>
          <div className="mx-auto max-w-sm">
            <ComposableMap
              projection="geoMercator"
              projectionConfig={{ center: [82, 22], scale: 900 }}
              width={380}
              height={420}
              style={{ width: "100%", height: "auto" }}
            >
              <Geographies geography={GEO_URL}>
                {({ geographies }) =>
                  geographies.map((geo) => {
                    const name = geo.properties.st_nm as string;
                    const count = byNameCount[name] ?? 0;
                    return (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        onMouseEnter={() => setHover(`${name}: ${count} flagged`)}
                        onMouseLeave={() => setHover(null)}
                        style={{
                          default: {
                            fill: shade(count, maxCount),
                            stroke: "#E4E0D6",
                            strokeWidth: 0.5,
                            outline: "none",
                          },
                          hover: { fill: "#8A6D1D", outline: "none", cursor: "pointer" },
                          pressed: { outline: "none" },
                        }}
                      />
                    );
                  })
                }
              </Geographies>
            </ComposableMap>
          </div>
          <div className="h-6 text-center text-sm text-ink">{hover}</div>
        </Card>

        <Card className="p-4">
          <SectionTitle hint="Whose name scammers are putting on messages most often.">
            Most imitated entities
          </SectionTitle>
          {(summary?.top_impersonated ?? []).length === 0 ? (
            <EmptyState title="No impersonation attempts recorded yet" />
          ) : (
            <ResponsiveContainer width="100%" height={340}>
              <BarChart
                data={summary?.top_impersonated ?? []}
                layout="vertical"
                margin={{ left: 8, right: 16 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#E4E0D6" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#5B6B7C" }} />
                <YAxis
                  type="category"
                  dataKey="entity"
                  width={150}
                  tick={{ fontSize: 11, fill: "#0A1B2E" }}
                />
                <RechartsTooltip
                  cursor={{ fill: "rgba(10,27,46,0.04)" }}
                  contentStyle={{
                    border: "1px solid #E4E0D6",
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill="#C6362B" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </Reveal>

      <Reveal delay={0} className="mt-6">
        <SectionTitle hint="Groups of messages that share a fake domain, image or phrase: the same operation, seen repeatedly.">
          Active scam campaigns
        </SectionTitle>
        {(summary?.campaigns ?? []).length === 0 ? (
          <EmptyState
            title="No campaign clusters yet"
            hint="When several flagged messages share a domain, phrase or image, they are grouped here as one campaign."
          />
        ) : (
          <TableWrap>
            <table className="w-full text-sm">
              <thead className="border-b border-hairline bg-paper">
                <tr>
                  <Th>Campaign</Th>
                  <Th>Times seen</Th>
                  <Th>Last seen</Th>
                  <Th>Channels</Th>
                </tr>
              </thead>
              <tbody>
                {(summary?.campaigns ?? []).map((c) => (
                  <tr key={c.campaign} className="border-b border-hairline last:border-0 hover:bg-paper">
                    <td className="px-4 py-3 font-mono font-medium text-fake">{c.campaign}</td>
                    <td className="px-4 py-3 font-mono text-ink">{c.count}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-info">
                      {c.last_seen.slice(0, 16).replace("T", " ")}
                    </td>
                    <td className="px-4 py-3 text-info">{c.channels.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Reveal>
    </Page>
  );
}
