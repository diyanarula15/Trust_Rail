"use client";

import { useState } from "react";
import { HeartHandshake, ShieldAlert } from "lucide-react";
import { pairCircleComplete } from "@/lib/api";
import { Reveal } from "@/components/Reveal";
import { Card, EmptyState, Page, PageHeader, SectionTitle } from "@/components/ui";

// Trust Circle links an elder's WhatsApp/Telegram/email identity — the one
// they already forward suspicious messages to this bot from — to a family
// member who gets alerted the moment something is flagged LIKELY_FAKE or
// OFFICIAL_CLAIM_UNVERIFIED. There's no login here (this app has none
// anywhere): the code from Step 1, plus the private link this form returns,
// are what stand in for an account.

export default function TrustCirclePage() {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [circleToken, setCircleToken] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await pairCircleComplete({
        code: code.trim(),
        guardianName: name.trim(),
        guardianEmail: email.trim(),
      });
      if (res.ok && res.data) {
        setCircleToken(res.data.circle_token);
      } else {
        setError(res.error?.message ?? "That code isn't valid or has expired.");
      }
    } catch {
      setError("Could not reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Page>
      <Reveal>
        <PageHeader
          eyebrow="Family protection"
          title="Trust Circle"
          lead="Link up with a family member's TrustRail bot so you're notified the moment something they receive is flagged as likely fake or unconfirmed — no need to wait for them to ask."
        />
      </Reveal>

      <Reveal delay={80} className="grid gap-6 sm:grid-cols-2">
        <Card className="p-5">
          <SectionTitle hint="They only need to do this once.">
            Step 1 — they get a code
          </SectionTitle>
          <p className="text-sm leading-relaxed text-info">
            Ask them to send <span className="rounded bg-paper px-1.5 py-0.5 font-mono text-ink">/circle</span>{" "}
            to the TrustRail bot on WhatsApp, Telegram, or by email — whichever
            one they already use to check suspicious messages. It replies with
            a 6-digit code good for 15 minutes.
          </p>
        </Card>

        <Card className="p-5">
          <SectionTitle hint="Do this part yourself, from your own device.">
            Step 2 — you enter it below
          </SectionTitle>
          <p className="text-sm leading-relaxed text-info">
            Enter the code plus your name and email. From then on, if
            something risky reaches them, you&apos;ll get an alert here — and
            directly on WhatsApp or Telegram too, if you also reply with{" "}
            <span className="rounded bg-paper px-1.5 py-0.5 font-mono text-ink">
              /circle &lt;code&gt;
            </span>{" "}
            from your own chat with the bot.
          </p>
        </Card>
      </Reveal>

      <Reveal delay={140} className="mt-8">
        {circleToken ? (
          <Card accent="border-l-verified" className="p-6">
            <div className="flex items-start gap-3">
              <HeartHandshake className="mt-0.5 h-5 w-5 shrink-0 text-verified" aria-hidden />
              <div>
                <h2 className="font-display text-lg font-bold text-ink">You&apos;re linked</h2>
                <p className="mt-1.5 text-sm leading-relaxed text-info">
                  Bookmark this private link — it&apos;s the only way to check
                  status or revoke this later, since nothing here requires an
                  account.
                </p>
                <a
                  href={`/trust-circle/${circleToken}`}
                  className="mt-3 inline-block break-all rounded bg-paper px-3 py-2 font-mono text-sm text-seal underline"
                >
                  /trust-circle/{circleToken}
                </a>
              </div>
            </div>
          </Card>
        ) : (
          <Card className="mx-auto max-w-md p-6">
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">6-digit code</label>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  required
                  className="w-full rounded border border-hairline bg-paper px-3 py-2 font-mono text-ink outline-none focus:border-seal"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">Your name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full rounded border border-hairline bg-paper px-3 py-2 text-ink outline-none focus:border-seal"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-ink">Your email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full rounded border border-hairline bg-paper px-3 py-2 text-ink outline-none focus:border-seal"
                />
              </div>
              {error && (
                <div className="flex items-start gap-2 rounded border border-fake/30 bg-fake/10 px-3 py-2 text-sm text-fake">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                  {error}
                </div>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded bg-ink px-4 py-2.5 text-sm font-semibold text-paper transition-opacity disabled:opacity-50"
              >
                {submitting ? "Linking…" : "Link as guardian"}
              </button>
            </form>
          </Card>
        )}
      </Reveal>

      <Reveal delay={200} className="mt-10">
        <EmptyState
          title="What a guardian can see"
          hint="Just enough to act: which platform flagged something, the plain-language verdict, and when. Never the message itself, never balances, never anything else they've sent."
        />
      </Reveal>
    </Page>
  );
}
