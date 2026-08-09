"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  BellRing,
  Check,
  Copy,
  RefreshCw,
  Send,
  ShieldOff,
  Smartphone,
} from "lucide-react";
import {
  disableGuard,
  enableGuard,
  getCircleStatus,
  regenerateGuard,
  revokeCircle,
  sendGuardTestMessage,
  type CircleStatusOut,
} from "@/lib/api";
import { Reveal } from "@/components/Reveal";
import { Badge, Card, EmptyState, Page, PageHeader, SectionTitle } from "@/components/ui";

const CHANNEL_LABEL: Record<string, string> = {
  whatsapp: "WhatsApp",
  telegram: "Telegram",
  email: "Email",
  sms: "SMS",
};

const TEST_MESSAGES = [
  {
    label: "A scam text",
    from: "+91 90000 00001 (test)",
    body: "MERIDN IPO allotment confirmed! Pay allotment fee now to http://rneridianbroking-refunds.top/claim. Pay via UPI meridianrefund@okpay",
  },
  {
    label: "An ordinary text",
    from: "+91 90000 00002 (test)",
    body: "Reminder: your electricity bill payment is due on the 15th.",
  },
];

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(value).catch(() => {});
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="inline-flex shrink-0 items-center gap-1 rounded border border-hairline bg-card px-2 py-1 text-xs font-medium text-ink hover:bg-paper"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-verified" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function AutoGuardPanel({
  token,
  status,
  onChanged,
}: {
  token: string;
  status: CircleStatusOut;
  onChanged: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [customBody, setCustomBody] = useState("");
  const [lastSent, setLastSent] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    await fn();
    await onChanged();
    setBusy(false);
  }

  async function sendTest(id: string, from: string, body: string) {
    if (!status.guard_webhook_url) return;
    setSendingId(id);
    setLastSent(null);
    await sendGuardTestMessage(status.guard_webhook_url, from, body);
    // The alert (if any) is written by the same request handler that
    // answers this call, but the guardian dashboard learns about it through
    // a separate GET — one beat's grace before refetching avoids a race
    // against the webhook's own commit.
    await new Promise((r) => setTimeout(r, 600));
    await onChanged();
    setSendingId(null);
    setLastSent(id);
  }

  if (!status.guard_enabled || !status.guard_webhook_url) {
    return (
      <Card accent="border-l-seal" className="p-5">
        <div className="flex items-start gap-3">
          <Smartphone className="mt-0.5 h-5 w-5 shrink-0 text-seal" aria-hidden />
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-lg font-bold text-ink">Auto-Guard</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-info">
              Turn this on and every text message that arrives on their phone gets checked
              automatically, before they ever open it. No forwarding, nothing for them to do.
              If something dangerous gets through, you&apos;re alerted here the moment it does.
            </p>
            <button
              type="button"
              onClick={() => act(() => enableGuard(token))}
              disabled={busy}
              className="mt-4 rounded bg-ink px-4 py-2 text-sm font-semibold text-paper transition-opacity disabled:opacity-50"
            >
              {busy ? "Enabling…" : "Enable Auto-Guard"}
            </button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card accent="border-l-verified" className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Smartphone className="mt-0.5 h-5 w-5 shrink-0 text-verified" aria-hidden />
          <div>
            <h2 className="font-display text-lg font-bold text-ink">Auto-Guard is on</h2>
            <p className="mt-1 text-sm leading-relaxed text-info">
              Every message reaching their phone is being scanned automatically.
            </p>
          </div>
        </div>
        <Badge tone="verified">active</Badge>
      </div>

      <div className="mt-4 rounded border border-hairline bg-paper p-3">
        <div className="text-xs font-medium uppercase tracking-wide text-info">
          Webhook address to configure
        </div>
        <div className="mt-1.5 flex items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded bg-card px-2 py-1.5 font-mono text-xs text-ink">
            {status.guard_webhook_url}
          </code>
          <CopyButton value={status.guard_webhook_url} />
        </div>
      </div>

      <details className="mt-3 text-sm text-info">
        <summary className="cursor-pointer font-medium text-ink">How to actually connect a phone</summary>
        <div className="mt-2 space-y-3 border-l-2 border-hairline pl-3">
          <div>
            <div className="font-medium text-ink">Their own phone (Android)</div>
            <p className="mt-1 leading-relaxed">
              Install an SMS-forwarding app (search &ldquo;SMS Forwarder&rdquo; or &ldquo;SMS
              Gateway&rdquo; on the Play Store), paste the address above as the forward
              destination, and every text that arrives from then on is mirrored here
              automatically as it happens.
            </p>
          </div>
          <div>
            <div className="font-medium text-ink">A dedicated number instead</div>
            <p className="mt-1 leading-relaxed">
              Point a Twilio phone number&apos;s inbound-message webhook at the same address.
              Every text sent to that number is scanned the same way.
            </p>
          </div>
        </div>
      </details>

      <div className="mt-4 flex flex-wrap gap-2 border-t border-hairline pt-4">
        <button
          type="button"
          onClick={() => act(() => regenerateGuard(token))}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded border border-hairline px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper disabled:opacity-50"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Regenerate address
        </button>
        <button
          type="button"
          onClick={() => act(() => disableGuard(token))}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded border border-fake/30 bg-fake/10 px-3 py-1.5 text-xs font-medium text-fake hover:bg-fake/15 disabled:opacity-50"
        >
          <ShieldOff className="h-3.5 w-3.5" /> Turn off
        </button>
      </div>

      <div className="mt-5 border-t border-hairline pt-4">
        <div className="text-xs font-medium uppercase tracking-wide text-info">
          See it work right now
        </div>
        <p className="mt-1 text-sm leading-relaxed text-info">
          This sends a real message to the address above, through the exact same route a
          phone would use: watch it land in your alerts below.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {TEST_MESSAGES.map((m) => (
            <button
              key={m.label}
              type="button"
              onClick={() => sendTest(m.label, m.from, m.body)}
              disabled={sendingId !== null}
              className="inline-flex items-center gap-1.5 rounded border border-hairline bg-card px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
              {sendingId === m.label ? "Sending…" : m.label}
            </button>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <input
            value={customBody}
            onChange={(e) => setCustomBody(e.target.value)}
            placeholder="Or type your own test message…"
            className="min-w-0 flex-1 rounded border border-hairline bg-paper px-2.5 py-1.5 text-xs text-ink outline-none focus:border-seal"
          />
          <button
            type="button"
            onClick={() => customBody.trim() && sendTest("custom", "custom test", customBody.trim())}
            disabled={sendingId !== null || !customBody.trim()}
            className="shrink-0 rounded bg-ink px-3 py-1.5 text-xs font-semibold text-paper disabled:opacity-40"
          >
            Send
          </button>
        </div>
        {lastSent && (
          <p className="mt-2 text-xs text-verified">
            Sent. If it was flagged, the alert appears below.
          </p>
        )}
      </div>
    </Card>
  );
}

export default function TrustCircleStatusPage() {
  const token = useParams<{ token: string }>().token;
  const [status, setStatus] = useState<CircleStatusOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [revoking, setRevoking] = useState(false);

  async function refresh() {
    const r = await getCircleStatus(token);
    if (r.ok && r.data) setStatus(r.data);
    else setNotFound(true);
  }

  useEffect(() => {
    refresh().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleRevoke() {
    setRevoking(true);
    const r = await revokeCircle(token);
    if (r.ok) {
      setStatus((s) => (s ? { ...s, status: "revoked" } : s));
    }
    setRevoking(false);
  }

  if (loading) {
    return (
      <Page>
        <EmptyState title="Loading…" />
      </Page>
    );
  }

  if (notFound || !status) {
    return (
      <Page>
        <EmptyState
          title="No such Trust Circle"
          hint="This link may be mistyped, or the circle no longer exists."
        />
      </Page>
    );
  }

  const isActive = status.status === "active";

  return (
    <Page>
      <Reveal>
        <PageHeader
          eyebrow="Family protection"
          title="Trust Circle status"
          actions={
            <Badge tone={isActive ? "verified" : status.status === "pending" ? "notice" : "fake"}>
              {status.status}
            </Badge>
          }
        />
      </Reveal>

      <Reveal delay={80} className="grid gap-6 sm:grid-cols-2">
        <Card className="p-5">
          <SectionTitle>Linked identity</SectionTitle>
          <div className="text-sm text-info">
            {CHANNEL_LABEL[status.elder_channel] ?? status.elder_channel}
          </div>
          <div className="mt-1 font-mono text-sm text-ink">{status.elder_masked}</div>
        </Card>

        <Card className="p-5">
          <SectionTitle>Guardian</SectionTitle>
          <div className="text-sm text-ink">{status.guardian_name ?? "N/A"}</div>
          <div className="mt-1 font-mono text-xs text-info">{status.guardian_email ?? "N/A"}</div>
          {status.guardian_channel && (
            <div className="mt-2 text-xs text-info">
              Also linked on {CHANNEL_LABEL[status.guardian_channel] ?? status.guardian_channel} for
              direct alerts.
            </div>
          )}
        </Card>
      </Reveal>

      {isActive && (
        <Reveal delay={140} className="mt-6">
          <AutoGuardPanel token={token} status={status} onChanged={refresh} />
        </Reveal>
      )}

      <Reveal delay={200} className="mt-8">
        <SectionTitle hint="Most recent first. Only what's needed to act on: never the message itself.">
          Recent alerts
        </SectionTitle>
        {status.alerts.length === 0 ? (
          <EmptyState
            title="No alerts yet"
            hint="Nothing flagged as likely fake or unconfirmed has reached them so far."
            icon={<BellRing className="h-6 w-6" />}
          />
        ) : (
          <div className="space-y-2">
            {status.alerts.map((a, i) => (
              <Card key={i} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-ink">{a.plain_headline}</span>
                  <Badge tone={a.verdict === "LIKELY_FAKE" ? "fake" : "notice"}>{a.verdict}</Badge>
                </div>
                <div className="mt-1 font-mono text-xs text-info">
                  {new Date(a.created_at).toLocaleString()} · delivered via {a.delivered_via}
                  {a.campaign ? ` · ${a.campaign}` : ""}
                </div>
              </Card>
            ))}
          </div>
        )}
      </Reveal>

      {isActive && (
        <div className="mt-8">
          <button
            type="button"
            onClick={handleRevoke}
            disabled={revoking}
            className="inline-flex items-center gap-2 rounded border border-fake/30 bg-fake/10 px-4 py-2 text-sm font-medium text-fake transition-opacity disabled:opacity-50"
          >
            <ShieldOff className="h-4 w-4" aria-hidden />
            {revoking ? "Revoking…" : "Revoke this Trust Circle"}
          </button>
        </div>
      )}
    </Page>
  );
}
