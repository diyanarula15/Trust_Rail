import {
  AlertTriangle,
  ArrowRight,
  Building2,
  HeartHandshake,
  Info,
  Landmark,
  Lock,
  MessageSquareText,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Upload,
} from "lucide-react";
import { getTelemetrySummary } from "@/lib/api";
import { Reveal } from "@/components/Reveal";
import {
  MockAutoGuard,
  MockFingerprint,
  MockIntake,
  MockLiveCheck,
  MockRecord,
  MockScam,
  MockVerdict,
} from "@/components/marketing/Mockups";

// Marketing site, structured the way a product site is: a centred hero, then
// alternating feature bands each pairing one claim with a real screen of the
// product, then trust, then a closing call to action.
//
// Two things the reference layout does that are deliberately NOT copied:
// testimonials and award badges. There are no users to quote and no awards to
// show, and inventing either on a fraud-prevention prototype would be
// self-defeating. The social-proof slot is filled with measured evaluation
// numbers instead, which are real and stronger.

const FEATURES = [
  {
    eyebrow: "For investors",
    title: "Forward it. Get a straight answer.",
    body:
      "Drop in a screenshot, a PDF, an SMS, a video or a link. In under a second you are told whether a registered company actually published it — in plain words, with the reason spelled out and the working available if you want it.",
    points: [
      "Works on anything that lands in a chat",
      "Answers in plain language, not jargon",
      "English and Hindi",
    ],
    href: "/verify",
    cta: "Check a message",
    Mock: MockVerdict,
    Icon: Upload,
  },
  {
    eyebrow: "The hard part",
    title: "It still recognises a forward after the platform mangles it.",
    body:
      "Chat apps re-save every photo they carry. That rewrites the file completely — a byte-for-byte check would miss it every time. TrustRail compares what the picture looks like and what the message says, so a forwarded copy still matches.",
    points: [
      "Survives re-compression, resizing and screenshots",
      "Ignores emoji and invisible characters injected into text",
      "Catches a filing whose figures were altered",
    ],
    href: "/verify",
    cta: "See the comparison",
    Mock: MockFingerprint,
    Icon: ScanSearch,
    flip: true,
  },
  {
    eyebrow: "Nothing hidden",
    title: "Every answer shows its working.",
    body:
      "Each verdict names the rule that produced it and the signals that escalated it. Strictness is only defensible if you can read it back, so the reasoning sits on the card rather than behind a support ticket.",
    points: [
      "Four stages, reported as the server finishes them",
      "Real measured timings, never simulated progress",
      "Every fraud signal listed individually",
    ],
    href: "/dashboard",
    cta: "See how a check works",
    Mock: MockLiveCheck,
    Icon: MessageSquareText,
  },
  {
    eyebrow: "The record",
    title: "Checked against something that cannot be rewritten.",
    body:
      "Issuers publish into an append-only record. Alter any entry and the fingerprint covering all of them changes. Your browser re-derives that fingerprint itself rather than trusting a server that says everything is fine.",
    points: [
      "Every publication and withdrawal, in order",
      "Proof verified client-side, no server trust needed",
      "Revocations are logged events, never silent edits",
    ],
    href: "/log",
    cta: "Inspect the record",
    Mock: MockRecord,
    Icon: Landmark,
    flip: true,
  },
  {
    eyebrow: "No new burden",
    title: "It rides on infrastructure issuers already use.",
    body:
      "Corporate announcements are already filed with exchanges. Every commercial SMS header and template is already pre-registered under DLT rules. TrustRail ingests both and signs them, so nobody is asked to adopt a new process.",
    points: [
      "Exchange filings ingested passively",
      "DLT-registered SMS templates become checkable",
      "Manual maker-checker publishing for everything else",
    ],
    href: "/dashboard",
    cta: "See where the record comes from",
    Mock: MockIntake,
    Icon: Building2,
  },
  {
    eyebrow: "When it is a scam",
    title: "Strict about fraud. Never strict about doubt.",
    body:
      "Any real fraud signal — an imitation web address, a look-alike company name, a demand for payment, a known campaign — is enough to call something a scam. But failing to find a match never is: that only ever means we cannot confirm it.",
    points: [
      "One fraud signal is enough to escalate",
      "An unknown issuer is never called a fraudster",
      "Campaigns are clustered and tracked",
    ],
    href: "/supervision",
    cta: "Open the supervision view",
    Mock: MockScam,
    Icon: AlertTriangle,
    flip: true,
  },
];

const VERDICTS = [
  { Icon: ShieldCheck, tone: "text-verified", title: "Yes, this is genuine",
    body: "Matches something the company really published." },
  { Icon: ShieldAlert, tone: "text-notice", title: "Genuine, but check first",
    body: "Real when published, but the signing key was later reported stolen." },
  { Icon: AlertTriangle, tone: "text-notice", title: "We cannot confirm this",
    body: "Claims to be official, but nothing published matches. Not an accusation." },
  { Icon: AlertTriangle, tone: "text-fake", title: "This looks like a scam",
    body: "Carries fraud signals we treat as serious." },
  { Icon: Info, tone: "text-info", title: "Nothing official here",
    body: "Makes no official claim at all. Most forwards land here." },
];

// The hero counters are live figures. Without this Next prerenders this page
// at build time and bakes in whatever the API returned then — which, when the
// backend isn't running during the build, is zero. Rendered per request
// instead, and it degrades to zeros rather than failing if the API is down.
export const dynamic = "force-dynamic";

export default async function LandingPage() {
  const summary = await getTelemetrySummary().catch(() => null);
  const totals = summary?.data?.totals_by_verdict ?? {};
  const checks = Object.values(totals).reduce((a, b) => a + b, 0);
  const flagged = (totals["LIKELY_FAKE"] ?? 0) + (totals["OFFICIAL_CLAIM_UNVERIFIED"] ?? 0);

  return (
    <div className="-mt-px">
      {/* ---------------- Hero ---------------- */}
      <section className="tr-hero border-b border-hairline">
        <div className="mx-auto max-w-4xl px-6 py-20 text-center sm:py-28">
          <div className="inline-flex items-center gap-2 rounded-full border border-hairline bg-card px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-info">
            <span className="tr-breathe h-1.5 w-1.5 rounded-full bg-verified" />
            SEBI TechSprint 2026 · prototype
          </div>

          <h1 className="mt-7 font-display text-[2.6rem] font-bold leading-[1.04] tracking-tight text-ink sm:text-6xl">
            Forward it. We&rsquo;ll tell you if
            <br className="hidden sm:block" />{" "}
            <span className="text-seal">the market actually said it.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-info">
            Fake announcements, doctored filings and guaranteed-return schemes spread through
            chat faster than any regulator can chase them. TrustRail answers one question with
            a definite answer:{" "}
            <span className="font-medium text-ink">did a registered company really publish this?</span>
          </p>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <a href="/verify" className="tr-btn tr-btn-primary">
              Check a message <ArrowRight className="h-4 w-4" />
            </a>
            <a href="/dashboard" className="tr-btn tr-btn-secondary">
              See it working
            </a>
          </div>

          <div className="mt-14 grid gap-3 sm:grid-cols-3">
            {[
              { v: checks, l: "messages checked", t: "text-ink" },
              { v: flagged, l: "flagged as unconfirmed or fake", t: "text-fake" },
              { v: "1.000", l: "matching precision, measured", t: "text-verified" },
            ].map((s, i) => (
              <div
                key={s.l}
                className="tr-rise rounded-xl border border-hairline bg-card px-5 py-5 shadow-sm"
                style={{ ["--tr-delay" as string]: `${i * 90}ms` }}
              >
                <div className={`font-mono text-3xl font-medium ${s.t}`}>{s.v}</div>
                <div className="mt-1 text-sm text-info">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- The thesis ---------------- */}
      <section className="border-b border-hairline">
        <Reveal className="mx-auto max-w-4xl px-6 py-16 text-center sm:py-20">
          <div className="tr-eyebrow">The idea</div>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            Detection guesses. Provenance proves.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-[17px] leading-relaxed text-info">
            Most tools look at a message and estimate how suspicious it seems. That is a guess,
            and guesses cannot be audited. TrustRail asks something answerable instead — whether
            the thing in front of you matches what a registered company actually published — and
            refuses to say &ldquo;genuine&rdquo; without either a valid signature or a match
            against that record.
          </p>
        </Reveal>
      </section>

      {/* ---------------- Alternating feature bands ---------------- */}
      {FEATURES.map(({ eyebrow, title, body, points, href, cta, Mock, Icon, flip }, i) => (
        <section
          key={title}
          className={`border-b border-hairline ${i % 2 === 1 ? "tr-band" : ""}`}
        >
          <Reveal className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 sm:py-20 lg:grid-cols-2 lg:gap-16">
            <div className={flip ? "lg:order-2" : ""}>
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-seal" aria-hidden />
                <span className="tr-eyebrow">{eyebrow}</span>
              </div>
              <h2 className="mt-3 font-display text-3xl font-bold leading-[1.12] tracking-tight text-ink sm:text-[2.35rem]">
                {title}
              </h2>
              <p className="mt-4 max-w-prose text-[17px] leading-relaxed text-info">{body}</p>
              <ul className="mt-6 space-y-2.5">
                {points.map((p) => (
                  <li key={p} className="flex items-start gap-2.5 text-[15px] text-ink">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-verified" aria-hidden />
                    {p}
                  </li>
                ))}
              </ul>
              <a
                href={href}
                className="mt-7 inline-flex items-center gap-1.5 text-[15px] font-semibold text-ink underline decoration-hairline decoration-2 underline-offset-4 hover:decoration-seal"
              >
                {cta} <ArrowRight className="h-4 w-4" />
              </a>
            </div>

            <div className={flip ? "lg:order-1" : ""}>
              <Mock />
            </div>
          </Reveal>
        </section>
      ))}

      {/* ---------------- Trust Circle: its own section, deliberately not
          just another item in the alternating list above. Two real, distinct
          capabilities: reactive (forward a suspicious message and get an
          answer) and Auto-Guard (nobody has to do anything at all). ---- */}
      <section className="tr-hero border-b border-hairline">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <Reveal className="mx-auto max-w-2xl text-center">
            <div className="flex items-center justify-center gap-2">
              <HeartHandshake className="h-4 w-4 text-seal" aria-hidden />
              <span className="tr-eyebrow">Family protection</span>
            </div>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Trust Circle
            </h2>
            <p className="mt-4 text-[17px] leading-relaxed text-info">
              The person most likely to lose money to a fake IPO or a fake KYC-update text is
              often the person least likely to check it first. Trust Circle links their phone
              to yours, so a scam gets caught even when they never think to ask.
            </p>
          </Reveal>

          <Reveal delay={100} className="mt-12 grid gap-10 lg:grid-cols-2 lg:gap-16 lg:items-center">
            <div>
              <div className="flex items-center gap-2">
                <Smartphone className="h-4 w-4 text-seal" aria-hidden />
                <span className="tr-eyebrow">The important part</span>
              </div>
              <h3 className="mt-3 font-display text-2xl font-bold leading-[1.12] tracking-tight text-ink">
                Auto-Guard scans every message that arrives &mdash; before anyone clicks
              </h3>
              <p className="mt-4 max-w-prose text-[17px] leading-relaxed text-info">
                Once it&rsquo;s turned on, nothing is manually forwarded to a bot and nothing
                is left to notice. Every text that reaches their phone is checked the instant
                it arrives, using the identical pipeline every other page on this site uses.
                If one turns out to be dangerous, you&rsquo;re alerted here &mdash; and they
                are never left to make that call alone.
              </p>
              <ul className="mt-6 space-y-2.5">
                {[
                  "Works via a free SMS-forwarder app already on the Play Store, or a dedicated number",
                  "No action from them, ever — the scanning is invisible",
                  "Ordinary messages never generate an alert; only real fraud signals do",
                ].map((p) => (
                  <li key={p} className="flex items-start gap-2.5 text-[15px] text-ink">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-verified" aria-hidden />
                    {p}
                  </li>
                ))}
              </ul>
              <a
                href="/trust-circle"
                className="mt-7 inline-flex items-center gap-1.5 text-[15px] font-semibold text-ink underline decoration-hairline decoration-2 underline-offset-4 hover:decoration-seal"
              >
                Set up Trust Circle <ArrowRight className="h-4 w-4" />
              </a>
            </div>
            <MockAutoGuard />
          </Reveal>

          <Reveal delay={150} className="mx-auto mt-12 max-w-3xl rounded-xl border border-hairline bg-card p-5 text-center">
            <p className="text-sm leading-relaxed text-info">
              Prefer the reactive version? They can also just forward anything suspicious
              straight to the bot on WhatsApp, Telegram, SMS or email and get an answer back
              in seconds &mdash; the same way anyone else uses{" "}
              <a href="/channels" className="font-medium text-ink underline decoration-hairline decoration-2 underline-offset-2 hover:decoration-seal">
                Channels
              </a>
              . Auto-Guard and the reactive bots work independently; most families use both.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ---------------- The five answers ---------------- */}
      <section className="border-b border-hairline">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <Reveal className="mx-auto max-w-2xl text-center">
            <div className="tr-eyebrow">What you get back</div>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Five possible answers
            </h2>
            <p className="mt-4 text-[17px] leading-relaxed text-info">
              No score out of a hundred, no traffic light you have to interpret. One of these,
              every time, with the reason attached.
            </p>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {VERDICTS.map(({ Icon, tone, title, body }, i) => (
              <Reveal
                key={title}
                delay={i * 70}
                className="tr-lift rounded-xl border border-hairline bg-card p-5 shadow-sm"
              >
                <Icon className={`h-6 w-6 ${tone}`} aria-hidden />
                <h3 className={`mt-3 font-display text-base font-bold ${tone}`}>{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-info">{body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- Trust / how it holds up ---------------- */}
      <section className="tr-band border-b border-hairline">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <Reveal className="mx-auto max-w-2xl text-center">
            <Lock className="mx-auto h-6 w-6 text-seal" aria-hidden />
            <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Built so you do not have to take our word for it
            </h2>
            <p className="mt-4 text-[17px] leading-relaxed text-info">
              The cryptography is real, not illustrative. These numbers come from the
              evaluation and acceptance suites in the repository, not a slide.
            </p>
          </Reveal>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { v: "1.000", l: "matching precision", d: "across 81 evaluation cases" },
              { v: "25/25", l: "acceptance cases", d: "every verdict path, expected answers" },
              { v: "112", l: "backend tests", d: "including the no-unproven-verdict guardrail" },
              { v: "831", l: "proof vectors", d: "verified in Python and TypeScript alike" },
            ].map((s, i) => (
              <Reveal
                key={s.l}
                delay={i * 70}
                className="rounded-xl border border-hairline bg-card p-5 shadow-sm"
              >
                <div className="font-mono text-2xl font-medium text-ink">{s.v}</div>
                <div className="mt-1 text-sm font-medium text-ink">{s.l}</div>
                <div className="mt-0.5 text-xs leading-relaxed text-info">{s.d}</div>
              </Reveal>
            ))}
          </div>
          <p className="mx-auto mt-8 max-w-2xl text-center text-sm leading-relaxed text-info">
            Every entity, filing and campaign in this demo is fictional. The signatures,
            transparency log and matching are not.
          </p>
        </div>
      </section>

      {/* ---------------- Closing CTA ---------------- */}
      <section className="tr-hero">
        <Reveal className="mx-auto max-w-3xl px-6 py-20 text-center sm:py-24">
          <h2 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-[2.6rem]">
            Try it on something suspicious.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-[17px] leading-relaxed text-info">
            There are ready-made examples on the verify page — a real scam SMS, an ordinary news
            line, and a photo forwarded exactly the way a chat app would mangle it.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a href="/verify" className="tr-btn tr-btn-primary">
              Check a message <ArrowRight className="h-4 w-4" />
            </a>
            <a href="/dashboard" className="tr-btn tr-btn-secondary">
              Open the dashboard
            </a>
          </div>
        </Reveal>
      </section>
    </div>
  );
}
