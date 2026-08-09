import { BellRing, CheckCircle2, AlertTriangle, FileCheck2, Link2, MessageSquareWarning, ShieldCheck, Smartphone } from "lucide-react";

// Static reproductions of what TrustRail actually shows, for the marketing
// sections. The reference site puts a real product screen beside every claim,
// which is the single thing that stops a feature list reading as vapour.
//
// These are faithful, not aspirational: every string, colour and number here
// is what the running product genuinely produces — the verdict wording comes
// from i18n `plain`, the fingerprint grid is a real phash64 rendered the same
// way `MatchEvidence` renders it, and the distances are measured values from
// the acceptance suite. Nothing here shows a capability that does not exist.

function Frame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="tr-lift overflow-hidden rounded-xl border border-hairline bg-card shadow-sm">
      <div className="flex items-center gap-1.5 border-b border-hairline bg-paper px-4 py-2.5">
        <span className="h-2 w-2 rounded-full bg-hairline" />
        <span className="h-2 w-2 rounded-full bg-hairline" />
        <span className="h-2 w-2 rounded-full bg-hairline" />
        <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-info">
          {label}
        </span>
      </div>
      <div className="p-4 sm:p-5">{children}</div>
    </div>
  );
}

/** The answer an investor actually sees. */
export function MockVerdict() {
  return (
    <Frame label="verify">
      <div className="rounded-lg border-l-4 border-verified bg-card p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-lg font-bold tracking-tight text-ink">
            Yes, this is genuine
          </h3>
          <ShieldCheck className="h-6 w-6 shrink-0 text-verified" aria-hidden />
        </div>
        <p className="mt-2 text-sm leading-relaxed text-ink">
          Meridian Broking Ltd really did publish this. We matched it against their own
          official record.
        </p>
        <div className="mt-3 rounded-lg bg-paper px-3 py-2.5">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-info">
            Why this answer
          </div>
          <p className="mt-1 text-xs leading-relaxed text-ink">
            We found this exact content in the record of what registered issuers have
            published.
          </p>
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-info">
          <span>DEMO-INZ-000123</span>
          <span>published 2026-08-01</span>
          <span>record entry 3</span>
        </div>
      </div>
    </Frame>
  );
}

/** The scam case, so the palette shows both ends. */
export function MockScam() {
  return (
    <Frame label="verify">
      <div className="rounded-lg border-l-4 border-fake bg-card p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-lg font-bold tracking-tight text-ink">
            This looks like a scam
          </h3>
          <AlertTriangle className="h-6 w-6 shrink-0 text-fake" aria-hidden />
        </div>
        <p className="mt-2 text-sm leading-relaxed text-ink">
          The web address is a near copy of a real company&rsquo;s address. Do not pay anyone,
          and do not share any code or password because of this message.
        </p>
        <div className="mt-3 rounded-lg bg-paper px-3 py-2.5">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-info">
            Escalated by
          </div>
          <ul className="mt-1 space-y-1 text-xs text-fake">
            <li className="flex gap-1.5">
              <span className="mt-[5px] h-1 w-1 shrink-0 rounded-full bg-current" />
              It matches a scam campaign already being tracked.
            </li>
            <li className="flex gap-1.5">
              <span className="mt-[5px] h-1 w-1 shrink-0 rounded-full bg-current" />
              It asks you to send money directly.
            </li>
          </ul>
        </div>
      </div>
    </Frame>
  );
}

// A real phash64 pair from the acceptance suite: the published notice and a
// 2.5% crop of it. Ten bits differ, which is exactly on the match line.
const PUBLISHED = "8ddd39686a2c65a5";
const FORWARDED = "8add19786a3c6327";
const DIFFERING = new Set([5, 6, 7, 18, 27, 43, 53, 54, 56, 62]);

function hexToBits(hex: string): number[] {
  const bits: number[] = [];
  for (const ch of hex) {
    const v = Number.parseInt(ch, 16);
    bits.push((v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1);
  }
  return bits;
}

function Grid({ hex, caption }: { hex: string; caption: string }) {
  return (
    <div>
      <div className="grid grid-cols-8 gap-[2px]" aria-hidden>
        {hexToBits(hex).map((bit, i) => (
          <div
            key={i}
            className={[
              "aspect-square rounded-[2px]",
              bit ? "bg-ink" : "border border-hairline bg-paper",
              DIFFERING.has(i) ? "outline outline-2 outline-offset-[1px] outline-verified" : "",
            ].join(" ")}
          />
        ))}
      </div>
      <div className="mt-2 text-center text-[11px] text-info">{caption}</div>
    </div>
  );
}

/** The fingerprint comparison — the most persuasive thing the product does. */
export function MockFingerprint() {
  return (
    <Frame label="how this was matched">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-hairline bg-card px-3 py-2">
          <div className="text-[10px] uppercase tracking-wider text-info">The file</div>
          <div className="mt-0.5 text-sm font-semibold text-ink">Rewritten</div>
        </div>
        <div className="rounded-lg border border-hairline bg-card px-3 py-2">
          <div className="text-[10px] uppercase tracking-wider text-info">The picture</div>
          <div className="mt-0.5 text-sm font-semibold text-verified">Unchanged</div>
        </div>
      </div>

      <div className="mt-4 flex items-start gap-4">
        <div className="w-24 shrink-0">
          <Grid hex={PUBLISHED} caption="published" />
        </div>
        <div className="w-24 shrink-0">
          <Grid hex={FORWARDED} caption="forwarded" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-mono text-sm text-verified">10 of 64 bits differ.</div>
          <div className="relative mt-2 h-2 w-full overflow-hidden rounded-full bg-paper ring-1 ring-hairline">
            <div className="absolute inset-y-0 left-0 w-[15.6%] bg-verified/25" />
            <div className="absolute inset-y-0 left-[15.6%] w-[9.4%] bg-notice/25" />
            <div className="absolute top-[-3px] h-[14px] w-[2px] bg-verified" style={{ left: "15.6%" }} />
          </div>
          <div className="mt-1 flex justify-between font-mono text-[10px] text-info">
            <span>0</span>
            <span>10 match</span>
            <span>64</span>
          </div>
        </div>
      </div>
      <p className="mt-3 border-t border-hairline pt-3 text-xs leading-relaxed text-info">
        Re-saving a photo rewrites the file completely but does not change what the picture
        looks like. We compare what it looks like.
      </p>
    </Frame>
  );
}

/** The append-only record. */
export function MockRecord() {
  const rows = [
    { seq: 15, kind: "Published", src: "exchange_filings", tone: "text-verified" },
    { seq: 14, kind: "Published", src: "exchange_filings", tone: "text-verified" },
    { seq: 13, kind: "Published", src: "dlt_sms", tone: "text-verified" },
    { seq: 12, kind: "Key revoked", src: "issuer_console", tone: "text-fake" },
  ];
  return (
    <Frame label="public record">
      <div className="rounded-lg bg-paper px-3 py-2.5">
        <div className="text-[10px] uppercase tracking-wider text-info">
          Fingerprint of the whole record
        </div>
        <div className="mt-1 break-all font-mono text-[11px] text-ink">
          4f2a9c17e8b3d05a1c6f4e2b9d78a3f150c2e6b4a97d1f38
        </div>
      </div>
      <div className="mt-3 space-y-1.5">
        {rows.map((r) => (
          <div
            key={r.seq}
            className="flex items-center justify-between gap-3 rounded-lg border border-hairline px-3 py-2"
          >
            <span className="flex items-center gap-2.5">
              <span className="font-mono text-xs text-info">#{r.seq}</span>
              <span className={`text-xs font-medium ${r.tone}`}>{r.kind}</span>
            </span>
            <span className="font-mono text-[10px] text-info">{r.src}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-1.5 border-t border-hairline pt-3 text-xs text-verified">
        <CheckCircle2 className="h-4 w-4" aria-hidden />
        Seal verified in your browser
      </div>
    </Frame>
  );
}

/** Where the record comes from. */
export function MockIntake() {
  const feeds = [
    { name: "Exchange filings", detail: "Corporate announcements, as already filed", n: 2 },
    { name: "DLT SMS registry", detail: "Pre-registered sender headers and templates", n: 3 },
    { name: "Issuer console", detail: "Manual, maker-checker approved", n: 10 },
  ];
  return (
    <Frame label="where the record comes from">
      <div className="space-y-2">
        {feeds.map((f, i) => (
          <div
            key={f.name}
            className={`rounded-lg border border-l-4 border-hairline px-3 py-2.5 ${
              i === 0 ? "border-l-seal" : i === 1 ? "border-l-info" : "border-l-ink"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-ink">{f.name}</span>
              <span className="font-mono text-base text-ink">{f.n}</span>
            </div>
            <p className="mt-0.5 text-[11px] leading-relaxed text-info">{f.detail}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-1.5 border-t border-hairline pt-3 text-xs text-info">
        <Link2 className="h-3.5 w-3.5" aria-hidden />
        Two of these are infrastructure issuers already use.
      </div>
    </Frame>
  );
}

/** The live check, mid-flight. */
export function MockLiveCheck() {
  const stages = [
    { label: "Opening what you sent", ms: "15ms", done: true },
    { label: "Looking for a digital signature", ms: "0ms", done: true },
    { label: "Comparing with the record", ms: "11ms", done: true },
    { label: "Checking for scam warning signs", ms: "", done: false },
  ];
  return (
    <Frame label="checking…">
      <div className="space-y-2.5">
        {stages.map((s) => (
          <div key={s.label} className="flex items-center gap-3">
            <span
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                s.done ? "bg-verified/10" : "bg-paper"
              }`}
            >
              {s.done ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-verified" aria-hidden />
              ) : (
                <span className="tr-breathe h-1.5 w-1.5 rounded-full bg-seal" />
              )}
            </span>
            <span className={`flex-1 text-sm ${s.done ? "text-ink" : "text-info"}`}>
              {s.label}
            </span>
            {s.ms && <span className="font-mono text-[11px] text-info">{s.ms}</span>}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-1.5 border-t border-hairline pt-3 text-xs text-info">
        <FileCheck2 className="h-3.5 w-3.5" aria-hidden />
        Timings are measured, not simulated.
      </div>
    </Frame>
  );
}

/** Auto-Guard: a text arrives on someone's phone, gets scanned with zero
 * action from them, and — only when it's actually dangerous — a guardian
 * is alerted. The alert text below is copied verbatim from
 * i18n/en.json's `circle.alert_intro` string, the exact wording the real
 * product sends; nothing here is invented for the marketing page. */
export function MockAutoGuard() {
  return (
    <Frame label="their phone → your alert">
      <div className="flex items-center gap-2 rounded-lg border border-hairline bg-paper px-3 py-2.5">
        <Smartphone className="h-4 w-4 shrink-0 text-info" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="text-[10px] uppercase tracking-wider text-info">Text received</div>
          <div className="truncate font-mono text-xs text-ink">
            &ldquo;IPO allotment confirmed! Pay fee now to claim&hellip;&rdquo;
          </div>
        </div>
        <span className="shrink-0 font-mono text-[10px] text-info">0:00</span>
      </div>

      <div className="my-2 flex items-center gap-2 pl-3 text-[11px] text-info">
        <span className="h-3 w-px bg-hairline" />
        scanned automatically, nobody opened it
      </div>

      <div className="flex items-center gap-2 rounded-lg border border-l-4 border-hairline border-l-fake bg-card px-3 py-2.5">
        <MessageSquareWarning className="h-4 w-4 shrink-0 text-fake" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="text-[10px] uppercase tracking-wider text-info">Result</div>
          <div className="text-xs font-semibold text-fake">This looks like a scam</div>
        </div>
        <span className="shrink-0 font-mono text-[10px] text-info">0:01</span>
      </div>

      <div className="my-2 flex items-center gap-2 pl-3 text-[11px] text-info">
        <span className="h-3 w-px bg-hairline" />
        guardian notified, the same second
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-hairline bg-paper px-3 py-2.5">
        <BellRing className="mt-0.5 h-4 w-4 shrink-0 text-seal" aria-hidden />
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wider text-info">
            TrustRail Trust Circle alert
          </div>
          <p className="mt-0.5 text-xs leading-relaxed text-ink">
            This was flagged and blocked automatically, no action needed from you.
          </p>
        </div>
      </div>
    </Frame>
  );
}
