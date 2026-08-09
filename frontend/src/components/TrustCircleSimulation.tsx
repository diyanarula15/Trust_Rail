"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BellRing,
  HeartHandshake,
  Info,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { simSms } from "@/lib/api";
import { Badge, Card, EmptyState } from "@/components/ui";

// A fully client-side stand-in for the real Trust Circle + Auto-Guard flow,
// for demoing without a live Telegram/WhatsApp/Twilio account or an actual
// second phone. It runs the real verification pipeline (via the same
// /api/sim/sms endpoint the Channels page uses) so every verdict shown here
// is genuine — but "linking a guardian" is local browser state only, never
// a real app.circle.pairing row, and nothing here can fire a real guardian
// alert. See app/api/sim.py's module docstring for why that boundary
// exists at all: this demo must never be able to touch the real thing.

const ALERT_VERDICTS = new Set(["LIKELY_FAKE", "OFFICIAL_CLAIM_UNVERIFIED"]);

// The first is the exact canonical text of a real seeded SMS communication
// (seed.py's PUBLISH_PLAN) — not paraphrased, because the match is on that
// literal wording. The second is the same scam text used elsewhere in this
// app (TryThese.tsx, the real Auto-Guard test-message panel).
const EXAMPLES = [
  {
    label: "Send a genuine notice",
    tone: "text-verified" as const,
    text: "MERIDN: Margin shortfall in your account. Add funds by T+1 via the official app. Never share OTPs. — Meridian Broking Ltd, SEBI reg DEMO-INZ-000123",
  },
  {
    label: "Send a likely-fake message",
    tone: "text-fake" as const,
    text: "MERIDN IPO allotment confirmed! Pay allotment fee now to http://rneridianbroking-refunds.top/claim. Pay via UPI meridianrefund@okpay",
  },
  {
    label: "Send an ordinary message",
    tone: "text-info" as const,
    text: "Benchmark indices ended higher today led by banking and IT stocks.",
  },
];

const VERDICT_ICON: Record<string, typeof ShieldCheck> = {
  VERIFIED: ShieldCheck,
  VERIFIED_NOTICE: ShieldAlert,
  OFFICIAL_CLAIM_UNVERIFIED: AlertTriangle,
  LIKELY_FAKE: AlertTriangle,
  INFORMATIONAL: Info,
};

const VERDICT_TONE: Record<string, string> = {
  VERIFIED: "text-verified",
  VERIFIED_NOTICE: "text-notice",
  OFFICIAL_CLAIM_UNVERIFIED: "text-notice",
  LIKELY_FAKE: "text-fake",
  INFORMATIONAL: "text-info",
};

interface SimMessage {
  id: string;
  text: string;
  headline?: string;
  verdict?: string;
  alerted: boolean;
  error?: string;
}

interface SimAlert {
  id: string;
  headline: string;
  verdict: string;
  time: string;
}

/** Same shape as the real backend's pairing.py::_generate_code — a plain
 * random 6-digit string, just generated client-side since this code never
 * needs to be checked against a database. */
function generateCode(): string {
  return String(Math.floor(100000 + Math.random() * 900000));
}

export function TrustCircleSimulation() {
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [codeInput, setCodeInput] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [guardianName, setGuardianName] = useState<string | null>(null);
  const [messages, setMessages] = useState<SimMessage[]>([]);
  const [alerts, setAlerts] = useState<SimAlert[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  function linkGuardian(e: React.FormEvent) {
    e.preventDefault();
    setLinkError(null);
    if (!codeInput.trim() || !pairingCode || codeInput.trim() !== pairingCode) {
      setLinkError("That code isn't valid or has expired. Send /circle again for a fresh one.");
      return;
    }
    setGuardianName(nameInput.trim());
  }

  async function sendMessage(body: string) {
    if (!body.trim() || busy) return;
    setBusy(true);
    const res = await simSms({ text: body });
    const card = res.data?.card;
    const verdict = card?.verdict;
    const alerted = !!verdict && ALERT_VERDICTS.has(verdict);
    const id = crypto.randomUUID();

    setMessages((m) => [
      ...m,
      { id, text: body, headline: card?.plain_headline, verdict, alerted, error: res.error?.message },
    ]);
    if (alerted && card) {
      setAlerts((a) => [
        {
          id,
          headline: card.plain_headline,
          verdict: verdict as string,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
        ...a,
      ]);
    }
    setText("");
    setBusy(false);
  }

  return (
    <div>
      <p className="mb-6 rounded border-l-2 border-seal bg-card px-4 py-3 text-sm leading-relaxed text-info">
        <span className="font-medium text-ink">Simulated end to end.</span> Every verdict below
        comes from the real verification pipeline, run the same way a real Auto-Guard message
        would be. Linking a guardian here is local to your browser only: no real Trust Circle is
        created, and no real guardian is ever alerted.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* -------- Their phone -------- */}
        <Card className="p-5">
          <div className="flex items-center gap-2 border-b border-hairline pb-3">
            <Smartphone className="h-4 w-4 text-seal" aria-hidden />
            <h3 className="font-display text-base font-bold text-ink">Their phone (SMS)</h3>
          </div>

          {!guardianName ? (
            <div className="mt-4">
              {!pairingCode ? (
                <>
                  <p className="text-sm leading-relaxed text-info">
                    On a real phone, they send <span className="rounded bg-paper px-1.5 py-0.5 font-mono text-ink">/circle</span>{" "}
                    to get a code. Simulate that here.
                  </p>
                  <button
                    type="button"
                    onClick={() => setPairingCode(generateCode())}
                    className="mt-3 rounded bg-ink px-4 py-2 text-sm font-semibold text-paper hover:opacity-90"
                  >
                    Send /circle
                  </button>
                </>
              ) : (
                <div className="rounded border border-hairline bg-paper p-3">
                  <div className="text-xs uppercase tracking-wide text-info">Bot reply</div>
                  <p className="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-ink">
                    {`Your Trust Circle code: ${pairingCode}\n\nGive this to a family member. This code expires in 15 minutes.`}
                  </p>
                  <p className="mt-2 text-xs text-info">
                    Waiting for a guardian to enter this code on the right.
                  </p>
                  <button
                    type="button"
                    onClick={() => setPairingCode(generateCode())}
                    className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-ink underline decoration-hairline decoration-2 underline-offset-2 hover:decoration-seal"
                  >
                    <RefreshCw className="h-3 w-3" aria-hidden />
                    Send /circle again for a fresh code
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="mt-3 flex items-center gap-1.5 text-xs text-info">
                <HeartHandshake className="h-3.5 w-3.5 text-verified" aria-hidden />
                Linked to {guardianName}
              </div>

              <div className="mt-4 max-h-80 space-y-3 overflow-y-auto">
                {messages.length === 0 && (
                  <p className="text-sm text-info">
                    Nothing has arrived yet. Try one of the examples below, or type your own.
                  </p>
                )}
                {messages.map((m) => {
                  const Icon = m.verdict ? VERDICT_ICON[m.verdict] : Info;
                  const tone = m.verdict ? VERDICT_TONE[m.verdict] : "text-info";
                  return (
                    <div key={m.id} className="rounded border border-hairline bg-paper p-3">
                      <p className="text-xs leading-relaxed text-ink">{m.text}</p>
                      {m.headline && (
                        <div className={`mt-2 flex items-center gap-1.5 border-t border-hairline pt-2 text-xs font-medium ${tone}`}>
                          <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                          {m.headline}
                        </div>
                      )}
                      {m.error && <p className="mt-2 text-xs text-fake">{m.error}</p>}
                      {m.alerted && (
                        <div className="mt-2">
                          <Badge tone="fake">Guardian alerted</Badge>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 flex flex-wrap gap-2 border-t border-hairline pt-4">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex.label}
                    type="button"
                    onClick={() => sendMessage(ex.text)}
                    disabled={busy}
                    className={`rounded border border-hairline bg-card px-3 py-1.5 text-xs font-medium hover:bg-paper disabled:opacity-50 ${ex.tone}`}
                  >
                    {ex.label}
                  </button>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendMessage(text)}
                  disabled={busy}
                  placeholder="Or type your own message…"
                  className="min-w-0 flex-1 rounded border border-hairline bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-seal disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => sendMessage(text)}
                  disabled={busy || !text.trim()}
                  className="shrink-0 rounded bg-ink p-2.5 text-paper disabled:opacity-40"
                  aria-label="Send"
                >
                  <Send className="h-4 w-4" aria-hidden />
                </button>
              </div>
            </>
          )}
        </Card>

        {/* -------- Guardian -------- */}
        <Card className="p-5">
          <div className="flex items-center gap-2 border-b border-hairline pb-3">
            <HeartHandshake className="h-4 w-4 text-seal" aria-hidden />
            <h3 className="font-display text-base font-bold text-ink">Guardian</h3>
          </div>

          {!guardianName ? (
            <div className="mt-4">
              <p className="text-sm leading-relaxed text-info">
                Enter the code from their phone, plus your name and email, to link up.
              </p>
              <form onSubmit={linkGuardian} className="mt-3 space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-ink">6-digit code</label>
                  <input
                    value={codeInput}
                    onChange={(e) => setCodeInput(e.target.value)}
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
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    required
                    className="w-full rounded border border-hairline bg-paper px-3 py-2 text-ink outline-none focus:border-seal"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-ink">Your email</label>
                  <input
                    type="email"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    required
                    className="w-full rounded border border-hairline bg-paper px-3 py-2 text-ink outline-none focus:border-seal"
                  />
                </div>
                {linkError && (
                  <div className="flex items-start gap-2 rounded border border-fake/30 bg-fake/10 px-3 py-2 text-sm text-fake">
                    <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                    {linkError}
                  </div>
                )}
                <button
                  type="submit"
                  disabled={!codeInput.trim() || !nameInput.trim() || !emailInput.trim()}
                  className="w-full rounded bg-ink px-4 py-2.5 text-sm font-semibold text-paper transition-opacity disabled:opacity-50"
                >
                  Link as guardian
                </button>
              </form>
            </div>
          ) : (
            <>
              <p className="mt-3 text-xs text-info">
                {guardianName} is watching over this phone. Ordinary and genuine messages never
                generate an alert; only likely-fake or unconfirmed ones do.
              </p>
              <div className="mt-4 space-y-2">
                {alerts.length === 0 ? (
                  <EmptyState
                    title="No alerts yet"
                    hint="Send a likely-fake message on the left to see one land here."
                    icon={<BellRing className="h-6 w-6" />}
                  />
                ) : (
                  alerts.map((a) => (
                    <Card key={a.id} accent="border-l-fake" className="p-3">
                      <div className="flex items-start justify-between gap-3">
                        <span className="text-sm font-medium text-ink">{a.headline}</span>
                        <Badge tone={a.verdict === "LIKELY_FAKE" ? "fake" : "notice"}>
                          {a.verdict}
                        </Badge>
                      </div>
                      <div className="mt-1 font-mono text-[11px] text-info">
                        flagged and blocked automatically, {a.time}
                      </div>
                    </Card>
                  ))
                )}
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
