"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import {
  artifactPreviewUrl,
  type EvidenceCopy,
  type HashComparison,
  type MatchEvidence as Evidence,
  type VideoComparison,
} from "@/lib/api";

// Shows the registry stage's actual working: the two files, their byte
// hashes, their perceptual fingerprints, and where the result fell against
// the thresholds. Every number and sentence comes from the API — this file
// contributes layout only, never wording (spec §12.1, same rule as
// PipelineTrace).
//
// The fingerprint grid is not a chart *about* the hash. A phash64 is a
// flattened 8x8 grid of DCT-sign bits, so cell (row, col) is literally bit
// row * 8 + col of the hex the API returned.

const ACCENT: Record<Evidence["outcome"], { text: string; border: string; bg: string }> = {
  match: { text: "text-verified", border: "border-verified", bg: "bg-verified" },
  near: { text: "text-notice", border: "border-notice", bg: "bg-notice" },
  miss: { text: "text-info", border: "border-info", bg: "bg-info" },
};

function hexToBits(hex: string): number[] {
  const bits: number[] = [];
  for (const ch of hex) {
    const v = Number.parseInt(ch, 16);
    if (Number.isNaN(v)) return [];
    bits.push((v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1);
  }
  return bits;
}

function BitGrid({
  hex,
  differing,
  columns,
  accent,
}: {
  hex: string;
  differing: Set<number>;
  columns: number;
  accent: string;
}) {
  const bits = hexToBits(hex);
  if (bits.length === 0) return null;
  return (
    <div
      className="grid gap-[2px]"
      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
      aria-hidden
    >
      {bits.map((bit, i) => (
        <div
          key={i}
          className={[
            "aspect-square rounded-[1px]",
            bit ? "bg-ink" : "bg-paper border border-hairline",
            differing.has(i) ? `outline outline-2 outline-offset-[1px] ${accent}` : "",
          ].join(" ")}
        />
      ))}
    </div>
  );
}

function DistanceScale({
  comparison,
  accent,
}: {
  comparison: HashComparison;
  accent: (typeof ACCENT)[Evidence["outcome"]];
}) {
  const { bits, distance, threshold_match, threshold_near } = comparison;
  const pct = (n: number) => `${Math.min(100, (n / bits) * 100)}%`;
  return (
    <div>
      <div className="relative h-2 w-full overflow-hidden rounded bg-paper ring-1 ring-hairline">
        <div className="absolute inset-y-0 left-0 bg-verified/25" style={{ width: pct(threshold_match) }} />
        {threshold_near !== null && (
          <div
            className="absolute inset-y-0 bg-notice/25"
            style={{ left: pct(threshold_match), width: pct(threshold_near - threshold_match) }}
          />
        )}
        <div
          className={`absolute top-[-3px] h-[14px] w-[2px] ${accent.bg}`}
          style={{ left: pct(distance) }}
        />
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-info">
        <span>0</span>
        <span>
          {threshold_match} match{threshold_near !== null ? ` · ${threshold_near} near` : ""}
        </span>
        <span>{bits}</span>
      </div>
    </div>
  );
}

function FrameStrip({ video, accent }: { video: VideoComparison; accent: string }) {
  return (
    <div className="flex flex-wrap gap-[3px]" aria-hidden>
      {video.frame_distances.map((d, i) => (
        <div
          key={i}
          title={`frame ${i + 1}: ${d} bits`}
          className={`h-3 w-3 rounded-[1px] ${
            d <= video.frame_max_distance ? accent : "bg-paper border border-hairline"
          }`}
        />
      ))}
    </div>
  );
}

function ImagePane({ label, src }: { label: string; src: string | null }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return null;
  return (
    <figure className="min-w-0 flex-1">
      <div className="flex aspect-video items-center justify-center overflow-hidden rounded border border-hairline bg-paper">
        {/* plain img: the API is a different origin and next/image would need a
            remote loader for a preview that may legitimately 404 */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={label}
          className="max-h-full max-w-full object-contain"
          onError={() => setFailed(true)}
        />
      </div>
      <figcaption className="mt-1 text-xs text-info">{label}</figcaption>
    </figure>
  );
}

/** The plain reading: two facts and the sentence that reconciles them. */
function PlainVerdictLines({
  copy,
  accent,
  sameFile,
}: {
  copy: EvidenceCopy;
  accent: (typeof ACCENT)[Evidence["outcome"]];
  sameFile: boolean;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <div className="rounded border border-hairline bg-card px-3 py-2">
        <div className="text-[11px] uppercase tracking-wide text-info">The file</div>
        <div className={`mt-0.5 text-sm font-medium ${sameFile ? accent.text : "text-ink"}`}>
          {copy.plain_file_line}
        </div>
      </div>
      <div className="rounded border border-hairline bg-card px-3 py-2">
        <div className="text-[11px] uppercase tracking-wide text-info">What it shows</div>
        <div className={`mt-0.5 text-sm font-medium ${accent.text}`}>
          {copy.plain_content_line}
        </div>
      </div>
    </div>
  );
}

export function MatchEvidence({
  evidence,
  copy,
  submittedImageUrl,
}: {
  evidence: Evidence;
  copy: EvidenceCopy;
  submittedImageUrl?: string | null;
}) {
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const accent = ACCENT[evidence.outcome];
  const hc = evidence.hash_comparison;
  const differing = new Set(hc?.differing_bits ?? []);
  const columns = hc && hc.bits > 64 ? 16 : 8;
  const registeredSrc = evidence.registered_sha256
    ? artifactPreviewUrl(evidence.registered_sha256)
    : null;

  return (
    <section className={`rounded border-l-2 bg-paper/60 p-3 ${accent.border}`}>
      <h4 className="font-display text-xs font-semibold uppercase tracking-wide text-info">
        {copy.plain_title || copy.title}
      </h4>

      {(submittedImageUrl || registeredSrc) && (
        <div className="mt-3 flex gap-3">
          <ImagePane label={copy.submitted_label} src={submittedImageUrl ?? null} />
          <ImagePane label={copy.registered_label} src={registeredSrc} />
        </div>
      )}

      <div className="mt-3">
        <PlainVerdictLines copy={copy} accent={accent} sameFile={evidence.sha256_identical} />
      </div>

      {copy.plain_explain && (
        <p className="mt-3 text-sm leading-relaxed text-ink">{copy.plain_explain}</p>
      )}

      {evidence.video_comparison && copy.frames_summary && (
        <div className="mt-3">
          <FrameStrip video={evidence.video_comparison} accent={accent.bg} />
          <p className="mt-1.5 text-xs text-info">{copy.frames_summary}</p>
        </div>
      )}

      {(hc || evidence.query_sha256) && (
        <div className="mt-3 border-t border-hairline pt-3">
          <button
            type="button"
            onClick={() => setTechnicalOpen((v) => !v)}
            aria-expanded={technicalOpen}
            className="flex items-center gap-1 text-xs font-medium text-info hover:text-ink"
          >
            {copy.technical_toggle || "Show the technical detail"}
            {technicalOpen ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>

          {technicalOpen && (
            <div className="mt-3 space-y-4">
              {evidence.query_sha256 && evidence.registered_sha256 && (
                <div>
                  <div className="text-xs font-medium text-info">{copy.sha_label}</div>
                  <div className="mt-1 space-y-0.5 font-mono text-xs">
                    <div className="truncate text-ink">{evidence.query_sha256}</div>
                    <div className="truncate text-ink">{evidence.registered_sha256}</div>
                  </div>
                  <p className="mt-1 text-xs text-info">{copy.sha_summary}</p>
                </div>
              )}

              {hc && (
                <div>
                  <div className="text-xs font-medium text-info">{copy.fingerprint_label}</div>
                  <div className="mt-2 flex items-start gap-4">
                    <div className="w-24 shrink-0">
                      <BitGrid
                        hex={hc.query_hex}
                        differing={differing}
                        columns={columns}
                        accent={accent.border}
                      />
                    </div>
                    <div className="w-24 shrink-0">
                      <BitGrid
                        hex={hc.registered_hex}
                        differing={differing}
                        columns={columns}
                        accent={accent.border}
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className={`font-mono text-sm ${accent.text}`}>
                        {copy.fingerprint_summary}
                      </p>
                      <div className="mt-2">
                        <DistanceScale comparison={hc} accent={accent} />
                      </div>
                    </div>
                  </div>
                  {copy.scale_summary && (
                    <p className="mt-2 text-xs text-info">{copy.scale_summary}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
