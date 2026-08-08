"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { ChevronDown, ShieldCheck } from "lucide-react";

// Global navigation.
//
// Eight flat links read as an internal tool rather than a product, and on a
// phone they became a horizontal scroll nobody would discover the end of. The
// things a visitor actually wants are promoted; the operator-facing views
// (issuer console, registry, supervision, channels) sit behind one grouped
// menu, which is the shape a product site uses.
//
// Trust Circle sits in PRIMARY, not MORE, on purpose: it's the one part of
// this product a family member sets up FOR someone else and then never
// touches this site again to use — burying it a click deep behind "More"
// undersells the one feature explicitly asked to read as important.

const PRIMARY = [
  { href: "/verify", label: "Verify" },
  { href: "/trust-circle", label: "Trust Circle" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/log", label: "Public record" },
];

const MORE = [
  { href: "/issuer", label: "Issuer console", hint: "How a company publishes" },
  { href: "/registry", label: "Registry", hint: "Who we can verify against" },
  { href: "/supervision", label: "Supervision", hint: "Regulator view" },
  { href: "/channels", label: "Channels", hint: "WhatsApp, Telegram, SMS, email" },
];

export function SiteHeader() {
  const pathname = usePathname() || "/";
  const [openMore, setOpenMore] = useState(false);
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);
  const moreActive = MORE.some((m) => isActive(m.href));

  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-paper/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-3.5">
        <a href="/" className="flex shrink-0 items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink">
            <ShieldCheck className="h-4 w-4 text-paper" aria-hidden />
          </span>
          <span className="font-display text-lg font-bold tracking-tight text-ink">
            TrustRail
          </span>
        </a>

        <nav aria-label="Sections" className="ml-2 flex flex-1 items-center gap-0.5">
          {PRIMARY.map((item) => (
            <a
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
              className={`hidden whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors sm:inline-block ${
                isActive(item.href)
                  ? "bg-ink text-paper"
                  : "text-info hover:bg-card hover:text-ink"
              }`}
            >
              {item.label}
            </a>
          ))}

          <div
            className="relative hidden sm:block"
            onMouseEnter={() => setOpenMore(true)}
            onMouseLeave={() => setOpenMore(false)}
          >
            <button
              type="button"
              onClick={() => setOpenMore((v) => !v)}
              aria-expanded={openMore}
              className={`flex items-center gap-1 whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
                moreActive ? "bg-ink text-paper" : "text-info hover:bg-card hover:text-ink"
              }`}
            >
              More
              <ChevronDown className={`h-3.5 w-3.5 transition-transform ${openMore ? "rotate-180" : ""}`} />
            </button>

            {openMore && (
              <div className="absolute left-0 top-full w-64 pt-2">
                <div className="overflow-hidden rounded-xl border border-hairline bg-card py-1.5 shadow-sm">
                  {MORE.map((item) => (
                    <a
                      key={item.href}
                      href={item.href}
                      className={`block px-4 py-2.5 transition-colors hover:bg-paper ${
                        isActive(item.href) ? "bg-paper" : ""
                      }`}
                    >
                      <span className="block text-sm font-medium text-ink">{item.label}</span>
                      <span className="mt-0.5 block text-xs text-info">{item.hint}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Small screens: one scrollable row, no hidden menu to discover */}
          <div className="-mx-1 flex items-center gap-0.5 overflow-x-auto px-1 sm:hidden">
            {[...PRIMARY, ...MORE].map((item) => (
              <a
                key={item.href}
                href={item.href}
                aria-current={isActive(item.href) ? "page" : undefined}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium ${
                  isActive(item.href) ? "bg-ink text-paper" : "text-info"
                }`}
              >
                {item.label}
              </a>
            ))}
          </div>
        </nav>

        <a
          href="/verify"
          className="hidden shrink-0 rounded-full bg-ink px-4 py-2 text-sm font-semibold text-paper hover:opacity-90 sm:inline-block"
        >
          Check a message
        </a>
      </div>
    </header>
  );
}
