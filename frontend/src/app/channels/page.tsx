"use client";

import { useState } from "react";
import { ChatSimulator, type ChatTurn, type Platform } from "@/components/ChatSimulator";
import { simSms, simTelegram, simWhatsapp } from "@/lib/api";

const PLATFORMS: Platform[] = ["telegram", "whatsapp", "sms"];

export default function ChannelsPage() {
  const [platform, setPlatform] = useState<Platform>("telegram");
  const [history, setHistory] = useState<Record<Platform, ChatTurn[]>>({
    telegram: [],
    whatsapp: [],
    sms: [],
  });
  const [current, setCurrent] = useState<{ sentLabel: string; sentImageUrl?: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(input: { file?: File; text?: string }) {
    const sentLabel = input.file ? input.file.name : (input.text ?? "");
    // Held in the browser only, same as /verify — nothing here is uploaded
    // for storage, this is purely for the side-by-side "what you sent" bubble.
    const sentImageUrl =
      input.file && input.file.type.startsWith("image/") ? URL.createObjectURL(input.file) : null;

    setCurrent({ sentLabel, sentImageUrl });
    setBusy(true);

    const turnBase = { id: crypto.randomUUID(), sentLabel, sentImageUrl };
    let turn: ChatTurn;
    if (platform === "telegram") {
      const res = await simTelegram(input);
      turn = {
        ...turnBase,
        replyText: res.data?.text,
        buttons: res.data?.buttons,
        card: res.data?.card,
        error: res.error?.message,
      };
    } else if (platform === "whatsapp") {
      const res = await simWhatsapp(input);
      turn = {
        ...turnBase,
        replyText: res.data?.text,
        card: res.data?.card,
        error: res.error?.message,
      };
    } else {
      const res = await simSms(input);
      turn = { ...turnBase, replyText: res.data?.text, error: res.error?.message };
    }

    setHistory((h) => ({ ...h, [platform]: [...h[platform], turn] }));
    setCurrent(null);
    setBusy(false);
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-9rem)] max-w-2xl flex-col px-6 py-10 sm:py-14">
      <div className="mb-6 border-b border-hairline pb-6">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-seal">
          See it as a real conversation
        </div>
        <h1 className="mt-2 font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          Channels
        </h1>
        <p className="mt-2.5 max-w-2xl text-[15px] leading-relaxed text-info">
          The same verification pipeline as Verify, run through each platform&rsquo;s real
          reply formatting &mdash; this is the literal text a Telegram, WhatsApp or SMS bot
          would send. Nothing here is actually sent anywhere; see docs/SETUP_TELEGRAM.md,
          docs/SETUP_WHATSAPP.md and docs/SETUP_SMS.md for what &ldquo;going live&rdquo;
          would take. SMS also has a second, automatic mode &mdash; see{" "}
          <a href="/trust-circle" className="underline decoration-hairline decoration-2 underline-offset-2 hover:decoration-seal">
            Trust Circle
          </a>.
        </p>

        <div className="mt-4 inline-flex rounded-full border border-hairline bg-card p-1">
          {PLATFORMS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPlatform(p)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium capitalize transition-colors ${
                platform === p ? "bg-ink text-paper" : "text-info hover:text-ink"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <ChatSimulator
        platform={platform}
        history={history[platform]}
        current={current}
        busy={busy}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
