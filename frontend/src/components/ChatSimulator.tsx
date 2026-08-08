"use client";

import { useRef, useState } from "react";
import { Bot, CheckCheck, ChevronDown, ChevronUp, Paperclip, Send } from "lucide-react";
import type { ButtonSpec, CardPayload } from "@/lib/api";
import { VerdictCard } from "./VerdictCard";

export type Platform = "telegram" | "whatsapp" | "sms";

// Real SMS in this codebase (a Twilio number, or an SMS-forwarder app —
// see docs/SETUP_SMS.md) never carries an image/PDF/video through this
// particular flow the way Telegram/WhatsApp media messages do, so the demo
// doesn't offer an attach button for it — pretending otherwise would show
// a capability that doesn't exist.
export const PLATFORM_SUPPORTS_FILES: Record<Platform, boolean> = {
  telegram: true,
  whatsapp: true,
  sms: false,
};

// One-off brand-ish colors for the platform chrome — deliberately not added
// to the app's semantic verdict palette (globals.css's --verified/--notice/
// --fake/etc.), since these exist only to make this one page read as "a
// real Telegram/WhatsApp conversation," not as reusable UI tokens.
const SKIN: Record<
  Platform,
  {
    name: string;
    headerBg: string;
    outgoingBubble: string;
    incomingBubble: string;
    chatBg: string;
    accent: string;
    accentText: string;
  }
> = {
  telegram: {
    name: "Telegram",
    headerBg: "bg-[#229ED9]",
    outgoingBubble: "bg-[#DCF0FA] text-[#0b1f2b]",
    incomingBubble: "bg-white text-[#0b1f2b]",
    chatBg: "bg-[#E7EEF3]",
    accent: "bg-[#229ED9]",
    accentText: "text-white",
  },
  whatsapp: {
    name: "WhatsApp",
    headerBg: "bg-[#075E54]",
    outgoingBubble: "bg-[#DCF8C6] text-[#0b1f0f]",
    incomingBubble: "bg-white text-[#0b1f0f]",
    chatBg: "bg-[#ECE5DD]",
    accent: "bg-[#25D366]",
    accentText: "text-[#0b1f0f]",
  },
  // No brand to borrow — SMS isn't one company's app — so this reads as a
  // plain native Messages screen rather than imitating any real product.
  sms: {
    name: "SMS",
    headerBg: "bg-[#334155]",
    outgoingBubble: "bg-[#DCEEFB] text-[#0b1f2b]",
    incomingBubble: "bg-white text-[#0b1f2b]",
    chatBg: "bg-[#F1F5F9]",
    accent: "bg-[#334155]",
    accentText: "text-white",
  },
};

export interface ChatTurn {
  id: string;
  sentLabel: string;
  sentImageUrl?: string | null;
  replyText?: string;
  buttons?: ButtonSpec[];
  card?: CardPayload;
  error?: string;
}

/**
 * Renders server-composed chat text: a line fully wrapped in `<b>...</b>`
 * (Telegram) or `*...*` (WhatsApp) becomes bold, everything else renders
 * plain. This is not general HTML parsing — the format is a small, fixed,
 * server-controlled shape (channels/telegram.py::_format_reply,
 * channels/whatsapp.py::format_card both only ever wrap one whole line at a
 * time) — so line-matching is enough, and nothing here invents copy.
 */
function renderPlatformText(text: string) {
  return text.split("\n").map((line, i) => {
    const boldHtml = line.match(/^<b>(.*)<\/b>$/);
    const boldMd = line.match(/^\*(.*)\*$/);
    const content = boldHtml?.[1] ?? boldMd?.[1] ?? line;
    if (line === "") return <div key={i}>&nbsp;</div>;
    return <div key={i}>{boldHtml || boldMd ? <strong className="font-semibold">{content}</strong> : content}</div>;
  });
}

function TypingBubble({ skin }: { skin: (typeof SKIN)[Platform] }) {
  return (
    <div className={`max-w-[60%] rounded-lg px-4 py-3 shadow-sm ${skin.incomingBubble}`}>
      <span className="inline-flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-info [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-info [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-info" />
      </span>
    </div>
  );
}

export function ChatSimulator({
  platform,
  history,
  current,
  busy,
  onSubmit,
}: {
  platform: Platform;
  history: ChatTurn[];
  current: { sentLabel: string; sentImageUrl?: string | null } | null;
  busy: boolean;
  onSubmit: (input: { file?: File; text?: string }) => void;
}) {
  const skin = SKIN[platform];
  const supportsFiles = PLATFORM_SUPPORTS_FILES[platform];
  const [text, setText] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [openDetail, setOpenDetail] = useState<Record<string, boolean>>({});

  function submitText() {
    if (!text.trim() || busy) return;
    onSubmit({ text: text.trim() });
    setText("");
  }

  function submitFile(file: File) {
    if (busy) return;
    onSubmit({ file });
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <div className="overflow-hidden rounded-lg border border-hairline shadow-sm">
      <div className={`flex items-center gap-3 px-4 py-3 text-white ${skin.headerBg}`}>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/20">
          <Bot className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <div className="font-display text-sm font-bold">TrustRail Bot</div>
          <div className="text-xs opacity-80">via {skin.name} &middot; online</div>
        </div>
      </div>

      <div className={`flex min-h-[420px] flex-col gap-3 overflow-y-auto px-4 py-4 ${skin.chatBg}`}>
        {history.length === 0 && !current && (
          <div className="m-auto max-w-xs text-center text-sm text-info">
            {supportsFiles
              ? `Forward a message, image, PDF or video below to see what ${skin.name} would actually reply.`
              : `Send a text message below to see what ${skin.name} would actually reply.`}
          </div>
        )}

        {history.map((turn) => (
          <div key={turn.id} className="flex flex-col gap-2">
            <div className={`ml-auto max-w-[80%] rounded-lg px-3 py-2 text-sm shadow-sm ${skin.outgoingBubble}`}>
              {turn.sentImageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={turn.sentImageUrl} alt="" className="mb-1.5 max-h-40 rounded" />
              )}
              <div className="break-words">{turn.sentLabel}</div>
              <div className="mt-1 flex justify-end">
                <CheckCheck className="h-3.5 w-3.5 opacity-60" aria-hidden />
              </div>
            </div>

            {turn.error && (
              <div className="max-w-[80%] rounded-lg border border-fake bg-white px-3 py-2 text-sm text-fake shadow-sm">
                {turn.error}
              </div>
            )}

            {turn.replyText && (
              <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm shadow-sm ${skin.incomingBubble}`}>
                {renderPlatformText(turn.replyText)}
                {turn.buttons && turn.buttons.length > 0 && (
                  <div className="mt-2 space-y-1 border-t border-hairline pt-2">
                    {turn.buttons.map((b) => (
                      <a
                        key={b.kind}
                        href={b.url}
                        target="_blank"
                        rel="noreferrer"
                        className={`block rounded px-2 py-1.5 text-center text-xs font-medium ${skin.accent} ${skin.accentText}`}
                      >
                        {b.label}
                      </a>
                    ))}
                  </div>
                )}
                {turn.card && (
                  <button
                    type="button"
                    onClick={() => setOpenDetail((s) => ({ ...s, [turn.id]: !s[turn.id] }))}
                    className="mt-2 flex items-center gap-1 text-xs font-medium text-info hover:text-ink"
                  >
                    View full verdict
                    {openDetail[turn.id] ? (
                      <ChevronUp className="h-3.5 w-3.5" aria-hidden />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5" aria-hidden />
                    )}
                  </button>
                )}
              </div>
            )}

            {turn.card && openDetail[turn.id] && (
              <div className="max-w-full">
                <VerdictCard card={turn.card} />
              </div>
            )}
          </div>
        ))}

        {current && (
          <div className="flex flex-col gap-2">
            <div className={`ml-auto max-w-[80%] rounded-lg px-3 py-2 text-sm shadow-sm ${skin.outgoingBubble}`}>
              {current.sentImageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={current.sentImageUrl} alt="" className="mb-1.5 max-h-40 rounded" />
              )}
              <div className="break-words">{current.sentLabel}</div>
            </div>
            <TypingBubble skin={skin} />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-hairline bg-card px-3 py-2.5">
        {supportsFiles && (
          <>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) submitFile(f);
              }}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="shrink-0 rounded-full p-2 text-info hover:bg-paper disabled:opacity-40"
              aria-label="Attach a file"
            >
              <Paperclip className="h-5 w-5" aria-hidden />
            </button>
          </>
        )}
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submitText();
          }}
          disabled={busy}
          placeholder={`Message ${skin.name}...`}
          className="min-w-0 flex-1 rounded-full border border-hairline bg-paper px-4 py-2 text-sm outline-none focus:border-ink"
        />
        <button
          type="button"
          onClick={submitText}
          disabled={busy || !text.trim()}
          className={`shrink-0 rounded-full p-2.5 disabled:opacity-40 ${skin.accent} ${skin.accentText}`}
          aria-label="Send"
        >
          <Send className="h-4 w-4" aria-hidden />
        </button>
      </div>
    </div>
  );
}
