"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { BellRing, ShieldOff } from "lucide-react";
import { getCircleStatus, revokeCircle, type CircleStatusOut } from "@/lib/api";
import { Badge, Card, EmptyState, Page, PageHeader, SectionTitle } from "@/components/ui";

const CHANNEL_LABEL: Record<string, string> = {
  whatsapp: "WhatsApp",
  telegram: "Telegram",
  email: "Email",
};

export default function TrustCircleStatusPage() {
  const token = useParams<{ token: string }>().token;
  const [status, setStatus] = useState<CircleStatusOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [revoking, setRevoking] = useState(false);

  useEffect(() => {
    getCircleStatus(token)
      .then((r) => {
        if (r.ok && r.data) setStatus(r.data);
        else setNotFound(true);
      })
      .finally(() => setLoading(false));
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
      <PageHeader
        eyebrow="Family protection"
        title="Trust Circle status"
        actions={
          <Badge tone={isActive ? "verified" : status.status === "pending" ? "notice" : "fake"}>
            {status.status}
          </Badge>
        }
      />

      <div className="grid gap-6 sm:grid-cols-2">
        <Card className="p-5">
          <SectionTitle>Linked identity</SectionTitle>
          <div className="text-sm text-info">
            {CHANNEL_LABEL[status.elder_channel] ?? status.elder_channel}
          </div>
          <div className="mt-1 font-mono text-sm text-ink">{status.elder_masked}</div>
        </Card>

        <Card className="p-5">
          <SectionTitle>Guardian</SectionTitle>
          <div className="text-sm text-ink">{status.guardian_name ?? "—"}</div>
          <div className="mt-1 font-mono text-xs text-info">{status.guardian_email ?? "—"}</div>
          {status.guardian_channel && (
            <div className="mt-2 text-xs text-info">
              Also linked on {CHANNEL_LABEL[status.guardian_channel] ?? status.guardian_channel} for
              direct alerts.
            </div>
          )}
        </Card>
      </div>

      <div className="mt-8">
        <SectionTitle hint="Most recent first. Only what's needed to act on — never the message itself.">
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
      </div>

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
