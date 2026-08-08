"use client";

import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";

// Global navigation. Before this existed every page was a dead end: you could
// land on /verify and had no way to reach the log, the registry or the
// supervision view except by typing a URL.
//
// Deliberately no hamburger menu — the nav is a horizontally scrollable row on
// small screens instead. Fewer moving parts, nothing to get stuck open, and it
// keeps every destination visible rather than hiding them behind a tap.

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/verify", label: "Verify" },
  { href: "/channels", label: "Channels" },
  { href: "/trust-circle", label: "Trust Circle" },
  { href: "/log", label: "Public record" },
  { href: "/registry", label: "Registry" },
  { href: "/issuer", label: "Issuer" },
  { href: "/supervision", label: "Supervision" },
];

export function SiteHeader() {
  const pathname = usePathname() || "/";

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-paper/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-3">
        <a href="/" className="flex shrink-0 items-center gap-2 group">
          <span className="flex h-7 w-7 items-center justify-center rounded bg-ink">
            <ShieldCheck className="h-4 w-4 text-paper" aria-hidden />
          </span>
          <span className="font-display text-lg font-bold tracking-tight text-ink">
            TrustRail
          </span>
        </a>

        <nav
          aria-label="Sections"
          className="-mx-1 flex flex-1 items-center gap-0.5 overflow-x-auto px-1"
        >
          {NAV.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <a
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-ink text-paper"
                    : "text-info hover:bg-card hover:text-ink"
                }`}
              >
                {item.label}
              </a>
            );
          })}
        </nav>

        <span className="hidden shrink-0 rounded-full border border-hairline bg-card px-2.5 py-1 font-mono text-[11px] text-info sm:inline">
          prototype
        </span>
      </div>
    </header>
  );
}
