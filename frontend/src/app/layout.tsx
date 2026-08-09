import type { Metadata } from "next";
import { Archivo, Inter, JetBrains_Mono } from "next/font/google";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-archivo",
});
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "TrustRail",
  description:
    "Forward it. We'll tell you if the market actually said it.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={`${archivo.variable} ${inter.variable} ${jetbrains.variable} font-body min-h-screen flex flex-col`}
      >
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <footer className="mt-16 border-t border-hairline bg-card">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-sm text-info">
            <p>
              <span className="font-display font-semibold text-ink">TrustRail</span>: hackathon
              prototype, not affiliated with SEBI.
            </p>
            <p className="text-xs">
              All entities, filings and campaigns shown are fictional. The cryptography is real.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
