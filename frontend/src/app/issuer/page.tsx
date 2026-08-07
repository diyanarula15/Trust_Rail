"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileSignature, PenLine, Plus, ShieldOff, X } from "lucide-react";
import {
  cosignAndPublish,
  createCommunication,
  listCommunications,
  listEntities,
  makerSign,
  revokeCommunication,
  revokeKey,
  type CommOut,
  type EntityOut,
  type KeyOut,
} from "@/lib/api";
import { Badge, Card, EmptyState, Page, PageHeader, TableWrap, Th } from "@/components/ui";

const CHANNELS = ["filing", "sms", "email", "video", "image", "pdf", "social"];

const STATUS: Record<string, { label: string; tone: string; hint: string }> = {
  draft: { label: "Draft", tone: "neutral", hint: "Created, not signed yet" },
  maker_signed: { label: "Awaiting approval", tone: "notice", hint: "Signed once, needs a second person" },
  published: { label: "Published", tone: "verified", hint: "In the public record" },
  revoked: { label: "Withdrawn", tone: "fake", hint: "Withdrawn by the issuer" },
};

export default function IssuerPage() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [entityId, setEntityId] = useState("");
  const [personaKeyId, setPersonaKeyId] = useState("");
  const [comms, setComms] = useState<CommOut[]>([]);
  const [rootDelta, setRootDelta] = useState<{ old: string; next: string } | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const [title, setTitle] = useState("");
  const [channel, setChannel] = useState("filing");
  const [impact, setImpact] = useState<"standard" | "market_moving">("standard");
  const [file, setFile] = useState<File | null>(null);
  const [canonicalText, setCanonicalText] = useState("");

  const entity = entities.find((e) => e.id === entityId);
  const persona = entity?.keys.find((k) => k.id === personaKeyId) ?? null;

  useEffect(() => {
    listEntities().then((r) => {
      if (r.ok && r.data) {
        setEntities(r.data);
        const featured = r.data.find((e) => e.keys.length > 1) ?? r.data[0];
        if (featured) {
          setEntityId(featured.id);
          setPersonaKeyId(featured.keys[0]?.id ?? "");
        }
      }
    });
  }, []);

  useEffect(() => {
    if (!entityId) return;
    listCommunications(entityId).then((r) => {
      if (r.ok && r.data) setComms(r.data);
    });
    const keys = entities.find((e) => e.id === entityId)?.keys ?? [];
    if (!keys.some((k) => k.id === personaKeyId)) setPersonaKeyId(keys[0]?.id ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityId, entities]);

  async function refreshComms() {
    if (!entityId) return;
    const r = await listCommunications(entityId);
    if (r.ok && r.data) setComms(r.data);
  }

  async function act<T>(fn: () => Promise<{ ok: boolean; data: T | null; error: { message: string } | null }>,
                        onOk?: (data: T) => void, fallback = "That didn't work.") {
    setBusy(true);
    const r = await fn();
    setBusy(false);
    if (r.ok && r.data) onOk?.(r.data);
    else setBanner(r.error?.message ?? fallback);
    await refreshComms();
  }

  async function handleCreate() {
    if (!entityId || !personaKeyId || !title) return;
    setBusy(true);
    const r = await createCommunication({
      entityId, title, channel, impact,
      file: file ?? undefined,
      canonicalText: file ? undefined : canonicalText,
      personaKeyId,
    });
    setBusy(false);
    if (r.ok) {
      setDrawerOpen(false);
      setTitle("");
      setFile(null);
      setCanonicalText("");
      await refreshComms();
    } else {
      setBanner(r.error?.message ?? "Could not create the draft.");
    }
  }

  async function handleSimulateCompromise(key: KeyOut) {
    setBusy(true);
    const r = await revokeKey(key.id, "Simulated key compromise (demo)");
    setBusy(false);
    if (r.ok) {
      setBanner(
        `Key "${key.label}" is now revoked. Anything signed before this moment stays verified but carries a warning; anything signed after it will not validate at all.`
      );
      const rr = await listEntities();
      if (rr.ok && rr.data) setEntities(rr.data);
    } else {
      setBanner(r.error?.message ?? "Could not revoke the key.");
    }
  }

  const personaOptions = useMemo(() => entity?.keys ?? [], [entity]);
  const selectCls =
    "rounded border border-hairline bg-card px-3 py-2 text-sm text-ink outline-none focus:border-ink";

  return (
    <Page wide>
      <PageHeader
        eyebrow="How a company publishes"
        title="Issuer console"
        lead="Nothing reaches the public record on one person's say-so. One person drafts and signs, a second approves, and only then is it published — and the record's fingerprint visibly changes at that moment."
        actions={
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            disabled={!entityId}
            className="inline-flex items-center gap-1.5 rounded bg-ink px-4 py-2 text-sm font-semibold text-paper hover:opacity-90 disabled:opacity-40"
          >
            <Plus className="h-4 w-4" /> New communication
          </button>
        }
      />

      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs uppercase tracking-wide text-info">
              Publishing as
            </span>
            <select
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              className={`w-full ${selectCls}`}
            >
              {entities.map((e) => (
                <option key={e.id} value={e.id}>{e.name}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs uppercase tracking-wide text-info">
              Acting as (who is at the keyboard)
            </span>
            <select
              value={personaKeyId}
              onChange={(e) => setPersonaKeyId(e.target.value)}
              className={`w-full ${selectCls}`}
            >
              {personaOptions.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.label} — {k.role}, {k.status}
                </option>
              ))}
            </select>
          </label>
        </div>

        {persona && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-hairline pt-3">
            <p className="text-xs leading-relaxed text-info">
              Switch the second dropdown between the maker and the checker to play both roles.
            </p>
            <button
              type="button"
              onClick={() => handleSimulateCompromise(persona)}
              disabled={persona.status === "revoked" || busy}
              className="inline-flex items-center gap-1.5 rounded border border-fake px-3 py-1.5 text-xs font-semibold text-fake hover:bg-fake/5 disabled:opacity-40"
            >
              <ShieldOff className="h-3.5 w-3.5" />
              {persona.status === "revoked" ? "Key already revoked" : "Simulate key compromise"}
            </button>
          </div>
        )}
      </Card>

      {rootDelta && (
        <Card accent="border-l-verified" className="mb-4 p-4">
          <div className="text-xs uppercase tracking-wide text-info">
            The public record just changed
          </div>
          <div className="mt-1.5 font-mono text-sm text-ink">
            {rootDelta.old.slice(0, 16)}… <span className="text-verified">→</span>{" "}
            {rootDelta.next.slice(0, 16)}…
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-info">
            That fingerprint covers every entry ever made. It changed on this publish, and it can
            never change back.
          </p>
        </Card>
      )}

      {banner && (
        <Card accent="border-l-notice" className="mb-4 flex items-start gap-3 p-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-notice" aria-hidden />
          <p className="flex-1 text-sm leading-relaxed text-ink">{banner}</p>
          <button
            type="button"
            onClick={() => setBanner(null)}
            aria-label="Dismiss"
            className="shrink-0 rounded p-1 text-info hover:bg-paper"
          >
            <X className="h-4 w-4" />
          </button>
        </Card>
      )}

      {comms.length === 0 ? (
        <EmptyState
          title="Nothing published by this entity yet"
          hint="Use “New communication” to create a draft, sign it as the maker, then switch to the checker to approve and publish."
          icon={<FileSignature className="h-6 w-6" />}
        />
      ) : (
        <TableWrap>
          <table className="w-full text-sm">
            <thead className="border-b border-hairline bg-paper">
              <tr>
                <Th>Title</Th>
                <Th>Type</Th>
                <Th>Impact</Th>
                <Th>Status</Th>
                <Th className="text-right">Next step</Th>
              </tr>
            </thead>
            <tbody>
              {comms.map((c) => {
                const s = STATUS[c.status] ?? { label: c.status, tone: "neutral", hint: "" };
                return (
                  <tr key={c.id} className="border-b border-hairline last:border-0 hover:bg-paper">
                    <td className="px-4 py-3">
                      <div className="font-medium text-ink">{c.title}</div>
                      {c.log_seq !== null && (
                        <div className="mt-0.5 font-mono text-xs text-info">
                          record entry {c.log_seq}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-info">{c.channel}</td>
                    <td className="px-4 py-3">
                      {c.impact === "market_moving" ? (
                        <Badge tone="notice">market moving</Badge>
                      ) : (
                        <span className="text-info">standard</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={s.tone}>{s.label}</Badge>
                      <div className="mt-0.5 text-xs text-info">{s.hint}</div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {c.status === "draft" && (
                        <button
                          type="button"
                          onClick={() => act(() => makerSign(c.id, personaKeyId), undefined, "Signing failed.")}
                          disabled={busy}
                          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded border border-hairline px-2.5 py-1.5 text-xs font-semibold text-ink hover:bg-paper disabled:opacity-40"
                        >
                          <PenLine className="h-3.5 w-3.5" /> Sign as maker
                        </button>
                      )}
                      {c.status === "maker_signed" && (
                        <button
                          type="button"
                          onClick={() =>
                            act(
                              () => cosignAndPublish(c.id, personaKeyId),
                              (d) => setRootDelta({ old: d.old_root, next: d.new_root }),
                              "Publishing failed."
                            )
                          }
                          disabled={busy}
                          className="whitespace-nowrap rounded bg-ink px-2.5 py-1.5 text-xs font-semibold text-paper hover:opacity-90 disabled:opacity-40"
                        >
                          Approve &amp; publish
                        </button>
                      )}
                      {c.status === "published" && (
                        <button
                          type="button"
                          onClick={() => act(() => revokeCommunication(c.id, personaKeyId), undefined, "Withdrawal failed.")}
                          disabled={busy}
                          className="whitespace-nowrap rounded border border-hairline px-2.5 py-1.5 text-xs font-semibold text-fake hover:bg-fake/5 disabled:opacity-40"
                        >
                          Withdraw
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableWrap>
      )}

      {drawerOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
          onClick={() => setDrawerOpen(false)}
        >
          <div
            className="w-full max-w-md rounded border border-hairline bg-card p-5 shadow-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display text-lg font-bold tracking-tight text-ink">
              New communication
            </h2>
            <p className="mt-1 text-sm text-info">
              This creates a draft. It is not public until it has been signed and approved.
            </p>

            <div className="mt-4 space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs uppercase tracking-wide text-info">Title</span>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Q1 results filing"
                  className={`w-full ${selectCls}`}
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="mb-1 block text-xs uppercase tracking-wide text-info">Type</span>
                  <select value={channel} onChange={(e) => setChannel(e.target.value)} className={`w-full ${selectCls}`}>
                    {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs uppercase tracking-wide text-info">Impact</span>
                  <select
                    value={impact}
                    onChange={(e) => setImpact(e.target.value as "standard" | "market_moving")}
                    className={`w-full ${selectCls}`}
                  >
                    <option value="standard">standard</option>
                    <option value="market_moving">market moving</option>
                  </select>
                </label>
              </div>
              <p className="rounded bg-paper px-3 py-2 text-xs leading-relaxed text-info">
                Market-moving items require a second person to approve before publishing. Standard
                ones can be published by the same person who signed.
              </p>
              <label className="block">
                <span className="mb-1 block text-xs uppercase tracking-wide text-info">File</span>
                <input
                  type="file"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-info file:mr-3 file:rounded file:border file:border-hairline file:bg-paper file:px-3 file:py-1.5 file:text-sm file:text-ink"
                />
              </label>
              <div className="text-center text-xs text-info">or</div>
              <label className="block">
                <span className="mb-1 block text-xs uppercase tracking-wide text-info">
                  Message text (for SMS or email)
                </span>
                <textarea
                  value={canonicalText}
                  onChange={(e) => setCanonicalText(e.target.value)}
                  rows={3}
                  className={`w-full resize-none ${selectCls}`}
                />
              </label>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="rounded border border-hairline px-3 py-2 text-sm font-medium text-ink hover:bg-paper"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCreate}
                disabled={busy || !title || (!file && !canonicalText)}
                className="rounded bg-ink px-4 py-2 text-sm font-semibold text-paper hover:opacity-90 disabled:opacity-40"
              >
                Create draft
              </button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}
