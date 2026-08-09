"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, Loader2, ScrollText, ShieldCheck } from "lucide-react";
import {
  getInclusionProof,
  getLogRoot,
  listLogEntries,
  type InclusionProof,
  type LogEntryOut,
  type LogRoot,
} from "@/lib/api";
import { verifyInclusion, verifySth } from "@/lib/merkle";
import { Reveal } from "@/components/Reveal";
import { Badge, Card, EmptyState, Page, PageHeader, TableWrap, Th } from "@/components/ui";

type CheckState = "checking" | "valid" | "invalid";

const KIND_LABEL: Record<string, { label: string; tone: string }> = {
  publish: { label: "Published", tone: "verified" },
  key_revocation: { label: "Key revoked", tone: "fake" },
  communication_revocation: { label: "Withdrawn", tone: "notice" },
};

function StateLine({ state, labels }: { state: CheckState; labels: Record<CheckState, string> }) {
  return (
    <span className="flex items-center gap-1.5 text-sm">
      {state === "checking" && <Loader2 className="h-4 w-4 animate-spin text-info" aria-hidden />}
      {state === "valid" && <CheckCircle2 className="h-4 w-4 text-verified" aria-hidden />}
      {state === "invalid" && <XCircle className="h-4 w-4 text-fake" aria-hidden />}
      <span className={state === "invalid" ? "text-fake" : state === "valid" ? "text-ink" : "text-info"}>
        {labels[state]}
      </span>
    </span>
  );
}

export default function LogPage() {
  const [root, setRoot] = useState<LogRoot | null>(null);
  const [sthState, setSthState] = useState<CheckState>("checking");
  const [entries, setEntries] = useState<LogEntryOut[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [proof, setProof] = useState<InclusionProof | null>(null);
  const [proofState, setProofState] = useState<CheckState>("checking");

  useEffect(() => {
    getLogRoot().then((r) => {
      if (r.ok && r.data) {
        setRoot(r.data);
        if (r.data.sth_sig && r.data.timestamp) {
          setSthState(
            verifySth(
              r.data.tree_size,
              r.data.root_hash,
              r.data.timestamp,
              r.data.sth_sig,
              r.data.registry_public_key
            )
              ? "valid"
              : "invalid"
          );
        }
      }
    });
    listLogEntries(50).then((r) => {
      if (r.ok && r.data) setEntries(r.data);
    });
  }, []);

  async function verifyEntry(seq: number) {
    setSelected(seq);
    setProof(null);
    setProofState("checking");
    const r = await getInclusionProof(seq);
    if (!r.ok || !r.data) {
      setProofState("invalid");
      return;
    }
    setProof(r.data);
    const ok = await verifyInclusion(
      r.data.leaf_hash,
      r.data.leaf_index,
      r.data.audit_path,
      r.data.tree_size,
      r.data.root_hash
    );
    setProofState(ok ? "valid" : "invalid");
  }

  return (
    <Page wide>
      <Reveal>
        <PageHeader
          eyebrow="Append-only, tamper-evident"
          title="Public record"
          lead="Every publication and every withdrawal, in the order it happened. Entries cannot be altered or removed after the fact without the record's fingerprint changing, and your browser checks that mathematically rather than taking our word for it."
        />
      </Reveal>

      {root && (
        <Reveal delay={80}>
        <Card accent="border-l-ink" className="mb-6 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-wide text-info">
                Current fingerprint of the whole record
              </div>
              <div className="mt-1.5 break-all font-mono text-sm text-ink">{root.root_hash}</div>
              <div className="mt-1 font-mono text-xs text-info">
                {root.tree_size} entries
                {root.timestamp ? ` · sealed ${root.timestamp.slice(0, 19).replace("T", " ")}` : ""}
              </div>
            </div>
            <div className="shrink-0 rounded bg-paper px-3 py-2">
              <StateLine
                state={sthState}
                labels={{
                  checking: "Checking the seal…",
                  valid: "Seal verified in your browser",
                  invalid: "Seal FAILED to verify",
                }}
              />
              <p className="mt-1 max-w-xs text-xs leading-relaxed text-info">
                Signed by the registry. Your browser re-checked the signature itself.
              </p>
            </div>
          </div>
        </Card>
        </Reveal>
      )}

      <Reveal delay={140} className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div>
          {entries.length === 0 ? (
            <EmptyState
              title="The record is empty"
              hint="Publish something from the issuer console and it will appear here."
              icon={<ScrollText className="h-6 w-6" />}
            />
          ) : (
            <TableWrap>
              <table className="w-full text-sm">
                <thead className="border-b border-hairline bg-paper">
                  <tr>
                    <Th>#</Th>
                    <Th>Event</Th>
                    <Th>Fingerprint</Th>
                    <Th>When</Th>
                    <Th />
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => {
                    const kind = typeof e.entry.kind === "string" ? e.entry.kind : "publish";
                    const meta = KIND_LABEL[kind] ?? { label: kind, tone: "neutral" };
                    return (
                      <tr
                        key={e.seq}
                        className={`border-b border-hairline last:border-0 ${
                          selected === e.seq ? "bg-paper" : ""
                        }`}
                      >
                        <td className="px-4 py-3 font-mono text-ink">{e.seq}</td>
                        <td className="px-4 py-3">
                          <Badge tone={meta.tone}>{meta.label}</Badge>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-info">
                          {e.leaf_hash.slice(0, 12)}…
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-xs text-info">
                          {e.created_at.slice(0, 10)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => verifyEntry(e.seq)}
                            className="whitespace-nowrap rounded border border-hairline px-2.5 py-1 text-xs font-medium text-ink hover:bg-paper"
                          >
                            Check it
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </TableWrap>
          )}
        </div>

        <div className="lg:sticky lg:top-20 lg:self-start">
          {selected === null ? (
            <EmptyState
              title="Check any entry"
              hint="Pick “Check it” on a row. Your browser will re-derive the record's fingerprint from that entry and prove it is genuinely part of the record."
              icon={<ShieldCheck className="h-6 w-6" />}
            />
          ) : (
            <Card className="p-5">
              <h2 className="font-display text-lg font-bold tracking-tight text-ink">
                Proof for entry {selected}
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-info">
                Starting from this entry and combining it with the hashes below, your browser
                should arrive at exactly the record fingerprint shown above.
              </p>

              <div className="mt-4 rounded bg-paper px-3 py-2.5">
                <StateLine
                  state={proofState}
                  labels={{
                    checking: "Working through the hashes…",
                    valid: "It checks out: this entry is provably in the record",
                    invalid: "Proof failed to verify",
                  }}
                />
              </div>

              {proof && (
                <div className="mt-4 space-y-3 font-mono text-xs">
                  <div>
                    <div className="text-info">this entry</div>
                    <div className="mt-0.5 break-all text-ink">{proof.leaf_hash}</div>
                  </div>
                  <div>
                    <div className="text-info">
                      combined with {proof.audit_path.length} sibling hash
                      {proof.audit_path.length === 1 ? "" : "es"}
                    </div>
                    <ul className="mt-1 space-y-0.5">
                      {proof.audit_path.map((h, i) => (
                        <li key={i} className="truncate text-ink">
                          {h}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="text-info">position</div>
                    <div className="mt-0.5 text-ink">
                      {proof.leaf_index} of {proof.tree_size}
                    </div>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      </Reveal>
    </Page>
  );
}
