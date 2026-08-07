import type { ReactNode } from "react";

// Shared layout primitives. These exist so the six pages actually match each
// other: before this, each page hand-rolled its own container width, heading
// size and card border, and they had visibly drifted apart.
//
// Type scale is deliberately larger and heavier than the original — headings
// carry weight, body copy stays quiet — while keeping the same palette and
// fonts (Archivo / Inter / JetBrains Mono).

export function Page({
  children,
  wide = false,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={`mx-auto px-6 py-10 sm:py-14 ${wide ? "max-w-6xl" : "max-w-4xl"}`}>
      {children}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  lead,
  actions,
}: {
  eyebrow?: string;
  title: string;
  lead?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-hairline pb-6">
      <div className="min-w-0">
        {eyebrow && (
          <div className="font-mono text-xs uppercase tracking-[0.18em] text-seal">
            {eyebrow}
          </div>
        )}
        <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          {title}
        </h1>
        {lead && (
          <p className="mt-2.5 max-w-2xl text-[15px] leading-relaxed text-info">{lead}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function SectionTitle({
  children,
  hint,
}: {
  children: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="mb-3">
      <h2 className="font-display text-lg font-bold tracking-tight text-ink">{children}</h2>
      {hint && <p className="mt-1 text-sm leading-relaxed text-info">{hint}</p>}
    </div>
  );
}

export function Card({
  children,
  className = "",
  accent,
}: {
  children: ReactNode;
  className?: string;
  /** Tailwind border-colour class, e.g. "border-verified", for a left rule. */
  accent?: string;
}) {
  return (
    <div
      className={`rounded border border-hairline bg-card shadow-sm ${
        accent ? `border-l-4 ${accent}` : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

/** Big number + label. Used for the KPI rows. */
export function Stat({
  value,
  label,
  tone = "text-ink",
}: {
  value: ReactNode;
  label: string;
  tone?: string;
}) {
  return (
    <Card className="px-4 py-3.5">
      <div className={`font-mono text-2xl font-medium sm:text-3xl ${tone}`}>{value}</div>
      <div className="mt-1 text-xs uppercase tracking-wide text-info">{label}</div>
    </Card>
  );
}

/** Tables are the main content on four of the six pages, so they get a
 * consistent treatment — and a scroll container, since several are far too
 * wide for a phone. */
export function TableWrap({ children }: { children: ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">{children}</div>
    </Card>
  );
}

export function Th({
  children,
  className = "",
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`whitespace-nowrap px-4 py-2.5 text-left font-mono text-[11px] font-medium uppercase tracking-wider text-info ${className}`}
    >
      {children}
    </th>
  );
}

export function EmptyState({
  title,
  hint,
  icon,
}: {
  title: string;
  hint?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="rounded border border-dashed border-hairline px-6 py-12 text-center">
      {icon && <div className="mb-3 flex justify-center text-info">{icon}</div>}
      <p className="font-display text-base font-semibold text-ink">{title}</p>
      {hint && <p className="mx-auto mt-1.5 max-w-md text-sm leading-relaxed text-info">{hint}</p>}
    </div>
  );
}

const BADGE_TONES: Record<string, string> = {
  neutral: "border-hairline bg-paper text-info",
  verified: "border-verified/30 bg-verified/10 text-verified",
  notice: "border-notice/30 bg-notice/10 text-notice",
  fake: "border-fake/30 bg-fake/10 text-fake",
  seal: "border-seal/30 bg-seal/10 text-seal",
};

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: keyof typeof BADGE_TONES | string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] ${
        BADGE_TONES[tone] ?? BADGE_TONES.neutral
      }`}
    >
      {children}
    </span>
  );
}
