import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Info,
  FileSignature,
  Map as MapIcon,
  ScrollText,
  BookMarked,
  ArrowRight,
  Upload,
  ScanSearch,
  MessageSquareText,
} from "lucide-react";
import { getTelemetrySummary } from "@/lib/api";

// Landing page, written for someone who has never heard of a hash: what it
// does, how it works in three steps, what each of the five answers means,
// and what every part of the system is for.

const STEPS = [
  {
    Icon: Upload,
    title: "You forward it",
    body: "A screenshot, a PDF, a video, an SMS, an email, or just a link. Whatever landed in your chat.",
  },
  {
    Icon: ScanSearch,
    title: "We check it against the real record",
    body: "Companies and exchanges publish their announcements into a tamper-proof public record. We compare what you sent against all of it, and we can still recognise a picture even after WhatsApp has re-saved it.",
  },
  {
    Icon: MessageSquareText,
    title: "You get a straight answer",
    body: "Genuine, or we cannot confirm it, or it looks like a scam. Always with the reason in plain words, and you can open the working if you want it.",
  },
];

const VERDICTS = [
  {
    Icon: ShieldCheck,
    color: "text-verified",
    border: "border-verified",
    title: "Yes, this is genuine",
    body: "It matches something the company really published.",
  },
  {
    Icon: ShieldAlert,
    color: "text-notice",
    border: "border-notice",
    title: "Genuine, but check first",
    body: "It was real when published, but the signing key was later reported stolen.",
  },
  {
    Icon: AlertTriangle,
    color: "text-notice",
    border: "border-notice",
    title: "We cannot confirm this",
    body: "It claims to be official, but nothing published matches it.",
  },
  {
    Icon: AlertTriangle,
    color: "text-fake",
    border: "border-fake",
    title: "This looks like a scam",
    body: "A fake web address, a known scam campaign, or a demand for payment.",
  },
  {
    Icon: Info,
    color: "text-info",
    border: "border-info",
    title: "Nothing official here",
    body: "It does not claim to be official at all. Most forwards land here.",
  },
];

const FEATURES = [
  {
    href: "/verify",
    Icon: ShieldCheck,
    accent: "border-verified",
    iconColor: "text-verified",
    title: "Verify",
    body: "Forward anything suspicious and watch it being checked, step by step. Open “How this was checked” to see the two files side by side and exactly why they did or did not match.",
    cta: "Check something",
  },
  {
    href: "/issuer",
    Icon: FileSignature,
    accent: "border-seal",
    iconColor: "text-seal",
    title: "Issuer console",
    body: "How a company publishes in the first place. One person drafts and signs, a second approves, and only then does it enter the public record. Watch the record’s fingerprint change the moment it does.",
    cta: "See the publishing flow",
  },
  {
    href: "/log",
    Icon: ScrollText,
    accent: "border-ink",
    iconColor: "text-ink",
    title: "Public record",
    body: "Every publication and every withdrawal, in order, and impossible to rewrite after the fact. Your browser checks the proof itself rather than taking our word for it.",
    cta: "Inspect the record",
  },
  {
    href: "/registry",
    Icon: BookMarked,
    accent: "border-info",
    iconColor: "text-info",
    title: "Who is registered",
    body: "The companies, exchanges, brokers and funds we recognise, their official web addresses and SMS sender IDs, and the status of every signing key they hold.",
    cta: "Browse registered entities",
  },
  {
    href: "/supervision",
    Icon: MapIcon,
    accent: "border-fake",
    iconColor: "text-fake",
    title: "Supervision view",
    body: "For the regulator: where impersonation attempts are landing across the country, which brands are being faked most, and which scam campaigns are running right now.",
    cta: "Open the map",
  },
];

export default async function LandingPage() {
  const summary = await getTelemetrySummary().catch(() => null);
  const totals = summary?.data?.totals_by_verdict ?? {};
  const totalVerifications = Object.values(totals).reduce((a, b) => a + b, 0);
  const flagged = (totals["LIKELY_FAKE"] ?? 0) + (totals["OFFICIAL_CLAIM_UNVERIFIED"] ?? 0);

  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      {/* Hero */}
      <section className="max-w-2xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-hairline bg-card px-3 py-1 text-xs font-medium text-info">
          <span className="h-1.5 w-1.5 rounded-full bg-verified" />
          SEBI Securities Market TechSprint 2026 · prototype
        </div>
        <h1 className="mt-5 font-display text-5xl font-bold leading-[1.05] tracking-tight text-ink">
          Forward it. We&rsquo;ll tell you if the market actually said it.
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-info">
          Fake announcements, doctored filings and &ldquo;guaranteed
          return&rdquo; schemes spread through WhatsApp faster than any
          regulator can chase them. TrustRail answers one question, in seconds:{" "}
          <span className="text-ink">
            did a registered company really put this out?
          </span>
        </p>
        <div className="mt-7 flex flex-wrap items-center gap-3">
          <a
            href="/verify"
            className="inline-flex items-center gap-2 rounded bg-ink px-5 py-2.5 text-sm font-semibold text-paper hover:opacity-90"
          >
            Check a message <ArrowRight className="h-4 w-4" />
          </a>
          <a
            href="/log"
            className="rounded border border-hairline px-5 py-2.5 text-sm font-semibold text-ink hover:bg-card"
          >
            See the public record
          </a>
        </div>

        <div className="mt-8 flex flex-wrap gap-x-8 gap-y-2 font-mono text-sm text-info">
          <span>
            <span className="text-ink">{totalVerifications}</span> checks in the
            last 14 days
          </span>
          <span>
            <span className="text-ink">{flagged}</span> flagged as unconfirmed
            or fake
          </span>
        </div>
      </section>

      {/* How it works */}
      <section className="mt-20">
        <h2 className="font-display text-2xl font-bold tracking-tight text-ink">
          How it works
        </h2>
        <div className="mt-6 grid gap-5 md:grid-cols-3">
          {STEPS.map(({ Icon, title, body }, i) => (
            <div key={title} className="rounded border border-hairline bg-card p-5">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-paper">
                  <Icon className="h-5 w-5 text-seal" aria-hidden />
                </span>
                <span className="font-mono text-xs text-info">Step {i + 1}</span>
              </div>
              <h3 className="mt-3 font-display font-semibold text-ink">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-info">{body}</p>
            </div>
          ))}
        </div>
        <p className="mt-5 max-w-3xl rounded border-l-2 border-seal bg-card px-4 py-3 text-sm leading-relaxed text-info">
          <span className="font-medium text-ink">
            Why forwarding doesn&rsquo;t break it.
          </span>{" "}
          When you forward a photo, apps re-save it to save space. That rewrites
          the file completely, so an ordinary file check would say &ldquo;no
          match&rdquo;. We compare what the picture <em>looks like</em> instead,
          which survives re-saving, cropping and screenshotting. You can see
          both comparisons on any result.
        </p>
      </section>

      {/* The five answers */}
      <section className="mt-20">
        <h2 className="font-display text-2xl font-bold tracking-tight text-ink">
          The five answers you can get
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-info">
          TrustRail never says &ldquo;verified&rdquo; unless it can actually
          prove it, with a signature or a match against the published record.
          When it cannot prove something, it says so plainly instead of
          guessing.
        </p>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {VERDICTS.map(({ Icon, color, border, title, body }) => (
            <div
              key={title}
              className={`rounded border border-l-4 border-hairline ${border} bg-card p-4`}
            >
              <Icon className={`h-5 w-5 ${color}`} aria-hidden />
              <h3 className="mt-2 font-display text-sm font-semibold text-ink">
                {title}
              </h3>
              <p className="mt-1 text-sm leading-relaxed text-info">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="mt-20">
        <h2 className="font-display text-2xl font-bold tracking-tight text-ink">
          What&rsquo;s in here
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {FEATURES.map(({ href, Icon, accent, iconColor, title, body, cta }) => (
            <a
              key={href}
              href={href}
              className={`group rounded border border-l-4 border-hairline ${accent} bg-card p-5 transition-colors hover:bg-paper`}
            >
              <Icon className={`h-6 w-6 ${iconColor}`} aria-hidden />
              <h3 className="mt-3 font-display text-lg font-semibold text-ink">
                {title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-info">{body}</p>
              <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-ink">
                {cta}
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
              </span>
            </a>
          ))}
        </div>
      </section>

      {/* Honesty note */}
      <section className="mt-20 rounded border border-hairline bg-card p-6">
        <h2 className="font-display text-lg font-bold text-ink">
          What this is, honestly
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-info">
          This is a hackathon prototype, not a SEBI service. Every company,
          registration number, filing and scam campaign you see here is
          fictional and made up for the demo. The cryptography is real: the
          signatures, the tamper-proof record and the proof your browser checks
          are genuine implementations, not mock-ups. What is deliberately not
          built is listed in the project&rsquo;s architecture notes rather than
          glossed over.
        </p>
      </section>
    </div>
  );
}
