"use client";

import { useEffect, useState } from "react";
import { BookMarked, KeyRound, Search } from "lucide-react";
import { getEntity, listEntities, type EntityDetailOut, type EntityOut } from "@/lib/api";
import { Reveal } from "@/components/Reveal";
import { Badge, Card, EmptyState, Page, PageHeader, SectionTitle } from "@/components/ui";

const KIND_LABEL: Record<string, string> = {
  regulator: "Regulator",
  exchange: "Exchange",
  listed_company: "Listed company",
  broker: "Broker",
  mutual_fund: "Mutual fund",
  ria: "Investment adviser",
};

export default function RegistryPage() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [selected, setSelected] = useState<EntityDetailOut | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listEntities()
      .then((r) => {
        if (r.ok && r.data) setEntities(r.data);
      })
      .finally(() => setLoading(false));
  }, []);

  async function select(id: string) {
    const r = await getEntity(id);
    if (r.ok && r.data) setSelected(r.data);
  }

  const filtered = entities.filter((e) =>
    `${e.name} ${e.sebi_reg_no} ${e.kind}`.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <Page wide>
      <Reveal>
        <PageHeader
          eyebrow="Who we recognise"
          title="Registry"
          lead="The companies, exchanges, brokers and funds this system can verify against, along with the web addresses and SMS sender IDs that genuinely belong to them, and the current state of every signing key they hold. If an issuer is not on this list, nothing they send can be confirmed."
        />
      </Reveal>

      <Reveal delay={80} className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div>
          <div className="mb-3 flex items-center gap-2 rounded border border-hairline bg-card px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-info" aria-hidden />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, type or registration number"
              className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-info"
            />
            <span className="shrink-0 font-mono text-xs text-info">{filtered.length}</span>
          </div>

          {loading ? (
            <EmptyState title="Loading the registry…" />
          ) : filtered.length === 0 ? (
            <EmptyState
              title="Nothing matches that"
              hint="Try part of a company name or a registration number."
              icon={<BookMarked className="h-6 w-6" />}
            />
          ) : (
            <div className="space-y-2">
              {filtered.map((e) => {
                const active = selected?.id === e.id;
                return (
                  <button
                    key={e.id}
                    type="button"
                    onClick={() => select(e.id)}
                    className={`flex w-full items-center justify-between gap-3 rounded border border-l-4 bg-card px-4 py-3 text-left transition-colors ${
                      active
                        ? "border-hairline border-l-seal bg-paper"
                        : "border-hairline border-l-hairline hover:bg-paper"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-display text-sm font-semibold text-ink">
                        {e.name}
                      </span>
                      <span className="mt-0.5 block font-mono text-xs text-info">
                        {e.sebi_reg_no} · {KIND_LABEL[e.kind] ?? e.kind}
                      </span>
                    </span>
                    <Badge tone={e.status === "active" ? "verified" : "fake"}>{e.status}</Badge>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="lg:sticky lg:top-20 lg:self-start">
          {!selected ? (
            <EmptyState
              title="Pick an entity"
              hint="Its official domains, SMS sender IDs and signing keys will appear here."
              icon={<BookMarked className="h-6 w-6" />}
            />
          ) : (
            <Card accent="border-l-seal" className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="font-display text-xl font-bold tracking-tight text-ink">
                    {selected.name}
                  </h2>
                  <div className="mt-1 font-mono text-xs text-info">
                    {selected.sebi_reg_no} · {KIND_LABEL[selected.kind] ?? selected.kind}
                  </div>
                </div>
                <Badge tone={selected.status === "active" ? "verified" : "fake"}>
                  {selected.status}
                </Badge>
              </div>

              <div className="mt-5">
                <SectionTitle hint="Anything claiming to be from this entity should come from one of these.">
                  Official web addresses
                </SectionTitle>
                <ul className="space-y-1">
                  {selected.domains.map((d) => (
                    <li
                      key={d.domain}
                      className="rounded bg-paper px-2.5 py-1.5 font-mono text-sm text-ink"
                    >
                      {d.domain}
                    </li>
                  ))}
                  {selected.domains.length === 0 && (
                    <li className="text-sm text-info">None recorded.</li>
                  )}
                </ul>
              </div>

              <div className="mt-5">
                <SectionTitle hint="The six-character sender ID their SMS messages arrive from.">
                  SMS sender IDs
                </SectionTitle>
                <div className="flex flex-wrap gap-1.5">
                  {selected.sms_headers.map((h) => (
                    <span
                      key={h.header}
                      className="rounded bg-paper px-2.5 py-1 font-mono text-sm text-ink"
                    >
                      {h.header}
                    </span>
                  ))}
                  {selected.sms_headers.length === 0 && (
                    <span className="text-sm text-info">None recorded.</span>
                  )}
                </div>
              </div>

              <div className="mt-5">
                <SectionTitle hint="A revoked key means anything signed with it after the revocation date cannot be trusted.">
                  Signing keys
                </SectionTitle>
                <div className="space-y-2">
                  {selected.keys.map((k) => (
                    <div
                      key={k.id}
                      className={`rounded border border-l-2 border-hairline p-3 ${
                        k.status === "active" ? "border-l-verified" : "border-l-fake"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="flex items-center gap-1.5 text-sm font-medium text-ink">
                          <KeyRound className="h-3.5 w-3.5 text-info" aria-hidden />
                          {k.label}
                        </span>
                        <Badge tone={k.status === "active" ? "verified" : "fake"}>
                          {k.status}
                        </Badge>
                      </div>
                      <div className="mt-1.5 font-mono text-xs text-info">
                        role {k.role} · since {k.valid_from.slice(0, 10)}
                      </div>
                      {k.revoked_at && (
                        <div className="mt-1 rounded bg-fake/5 px-2 py-1 font-mono text-xs text-fake">
                          revoked {k.revoked_at.slice(0, 10)}
                          {k.revocation_reason ? `: ${k.revocation_reason}` : ""}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      </Reveal>
    </Page>
  );
}
