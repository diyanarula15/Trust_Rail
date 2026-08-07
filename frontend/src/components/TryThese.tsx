"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Image as ImageIcon, Info, ShieldQuestion } from "lucide-react";
import { API_BASE_URL, artifactPreviewUrl, type VerifyInput } from "@/lib/api";

// Concrete things to try, so the page explains itself instead of asking for
// "a file" and leaving you to guess which one.
//
// Every example runs the real pipeline. The photo example in particular is
// not a canned result: it downloads a genuinely published image, re-encodes
// it in *your browser* to JPEG quality 0.5 via canvas — which is what
// WhatsApp does to a forwarded photo, and really does rewrite every byte —
// then submits that. The match you see is earned, not staged.

interface Sample {
  sha256: string;
  title: string;
  channel: string;
}

const TEXT_EXAMPLES = [
  {
    Icon: AlertTriangle,
    accent: "text-fake",
    label: "A scam SMS",
    expect: "should come back as likely fake",
    text: "MERIDN IPO allotment confirmed! Pay allotment fee now to http://rneridianbroking-refunds.top/claim. Last 2 hours only. Pay via UPI meridianrefund@okpay",
  },
  {
    Icon: ShieldQuestion,
    accent: "text-notice",
    label: "A fake official claim",
    expect: "names a real company, but nothing matches it",
    text: "Important circular from Kumaon Metals Ltd regarding the revised allotment schedule for retail investors.",
  },
  {
    Icon: Info,
    accent: "text-info",
    label: "An ordinary news line",
    expect: "makes no official claim at all",
    text: "Benchmark indices ended higher today led by banking and IT stocks.",
  },
];

/** Re-encode a blob as JPEG q0.5 in the browser — the same lossy re-save a
 * messaging app performs on a forwarded photo. */
async function reencodeAsWhatsAppWould(blob: Blob, name: string): Promise<File> {
  const bitmap = await createImageBitmap(blob);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0);
  bitmap.close();
  const out: Blob = await new Promise((resolve, reject) =>
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("canvas encode failed"))),
      "image/jpeg",
      0.5
    )
  );
  return new File([out], name, { type: "image/jpeg" });
}

export function TryThese({
  onRun,
  busy,
}: {
  onRun: (input: Omit<VerifyInput, "locale">) => void;
  busy: boolean;
}) {
  const [sample, setSample] = useState<Sample | null>(null);
  const [preparing, setPreparing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/artifacts/samples?limit=1`)
      .then((r) => r.json())
      .then((r) => {
        if (!cancelled && r.ok && r.data?.length) setSample(r.data[0]);
      })
      .catch(() => {
        /* no samples: the photo example just doesn't offer itself */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function runPhotoExample() {
    if (!sample) return;
    setPreparing(true);
    try {
      const res = await fetch(artifactPreviewUrl(sample.sha256));
      const file = await reencodeAsWhatsAppWould(await res.blob(), "forwarded-photo.jpg");
      onRun({ file });
    } catch {
      /* leave the button available to retry */
    } finally {
      setPreparing(false);
    }
  }

  return (
    <div className="rounded border border-hairline bg-card p-5">
      <h2 className="font-display text-base font-semibold text-ink">
        Not sure what to send? Try one of these.
      </h2>
      <p className="mt-1 text-sm text-info">
        Each one runs the real check, start to finish. Watch the steps as they
        happen, then open “How this was checked” on the answer.
      </p>

      <div className="mt-4 space-y-2">
        {sample && (
          <button
            type="button"
            disabled={busy || preparing}
            onClick={runPhotoExample}
            className="flex w-full items-start gap-3 rounded border border-hairline p-3 text-left hover:bg-paper disabled:opacity-50"
          >
            <ImageIcon className="mt-0.5 h-4 w-4 shrink-0 text-verified" aria-hidden />
            <span className="min-w-0">
              <span className="block text-sm font-medium text-ink">
                {preparing ? "Re-saving the photo…" : "A photo, forwarded like WhatsApp would"}
              </span>
              <span className="mt-0.5 block text-xs text-info">
                Takes a real published notice, re-saves it in your browser at
                lower quality (which changes every byte), and checks it. Should
                still come back genuine.
              </span>
            </span>
          </button>
        )}

        {TEXT_EXAMPLES.map(({ Icon, accent, label, expect, text }) => (
          <button
            key={label}
            type="button"
            disabled={busy}
            onClick={() => onRun({ text })}
            className="flex w-full items-start gap-3 rounded border border-hairline p-3 text-left hover:bg-paper disabled:opacity-50"
          >
            <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${accent}`} aria-hidden />
            <span className="min-w-0">
              <span className="block text-sm font-medium text-ink">{label}</span>
              <span className="mt-0.5 block text-xs text-info">{expect}</span>
            </span>
          </button>
        ))}
      </div>

      <p className="mt-4 border-t border-hairline pt-3 text-xs leading-relaxed text-info">
        <span className="font-medium text-ink">Or send your own.</span> Use the
        box below: drop an image, PDF, video or <code>.eml</code> file, paste a
        message, or paste a link. Nothing you send is stored.
      </p>
    </div>
  );
}
