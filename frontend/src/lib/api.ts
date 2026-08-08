// Typed API client (spec §9). Card copy comes ONLY from these responses —
// components must never invent verdict strings themselves.

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface ApiError {
  code: string;
  message: string;
}

export interface ApiResponse<T> {
  ok: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface EntityRef {
  id: string;
  name: string;
  sebi_reg_no: string;
}

export interface CommunicationRef {
  id: string;
  title: string;
  published_at: string | null;
  log_seq: number | null;
  channel: string | null;
}

export interface ButtonSpec {
  kind: string;
  label: string;
  url: string;
}

export interface TraceStep {
  stage: string;
  outcome: string;
  ms: number;
}

export interface HashComparison {
  algorithm: "phash64" | "pdq256" | "simhash64";
  bits: number;
  query_hex: string;
  registered_hex: string;
  distance: number;
  differing_bits: number[];
  threshold_match: number;
  threshold_near: number | null;
}

export interface VideoComparison {
  frame_distances: number[];
  frame_max_distance: number;
  matched_frames: number;
  total_frames: number;
  ratio: number;
  threshold_ratio: number;
}

export interface MatchEvidence {
  outcome: "match" | "near" | "miss";
  kind: string;
  /** What the reader actually sent — decides how the comparison is worded. */
  content_kind: "image" | "text" | "video" | "document";
  /** The wording the issuer published, for text/document comparisons. */
  registered_text: string | null;
  query_sha256: string | null;
  registered_sha256: string | null;
  sha256_identical: boolean;
  hash_comparison: HashComparison | null;
  video_comparison: VideoComparison | null;
  registered_communication_id: string | null;
}

/** Localized sentences for the evidence panel — numbers already interpolated
 * server-side, so the component renders wording it never invents (spec §12.1). */
export interface EvidenceCopy {
  title: string;
  submitted_label: string;
  registered_label: string;
  sha_label: string;
  sha_summary: string;
  fingerprint_label: string;
  fingerprint_summary: string;
  scale_summary: string | null;
  frames_summary: string | null;
  plain_title: string;
  plain_file_label: string;
  plain_content_label: string;
  plain_file_line: string;
  plain_content_line: string;
  plain_explain: string;
  technical_toggle: string;
}

/** Why the verdict is what it is: the rule that fired, plus anything that
 * escalated it. Strictness is only defensible if it can be read back. */
export interface WhyPayload {
  label: string;
  rule: string;
  explanation: string;
  escalated_by_label: string;
  escalated_by: string[];
  strict_note: string;
}

export interface CardPayload {
  verification_id: string;
  verdict: string;
  headline: string;
  body: string;
  why: WhyPayload | null;
  /** Plain-language register for a non-specialist. Same verdict, no jargon. */
  plain_headline: string;
  plain_body: string;
  plain_reason_strings: string[];
  reasons: string[];
  reason_strings: string[];
  advice: string[];
  buttons: ButtonSpec[];
  matched_entity: EntityRef | null;
  matched_communication: CommunicationRef | null;
  claimed_entity_text: string | null;
  pipeline_trace: TraceStep[];
  match_evidence: MatchEvidence | null;
  evidence_copy: EvidenceCopy | null;
  locale: string;
}

/** Preview of a *published* artifact, for the registered side of the
 * comparison. 404s for drafts and non-images — callers hide the panel. */
export function artifactPreviewUrl(sha256: string): string {
  return `${API_BASE_URL}/api/artifacts/${sha256}/preview`;
}

export interface CertificatePayload {
  verdict: string | null;
  entity: EntityRef | null;
  communication: CommunicationRef;
  artifact_sha256: string | null;
  signature_chain: {
    maker_key_id: string | null;
    maker_key_status: string | null;
    checker_key_id: string | null;
    checker_key_status: string | null;
  };
  inclusion_proof: {
    leaf_index: number;
    leaf_hash: string;
    audit_path: string[];
    tree_size: number;
    root_hash: string;
  } | null;
}

export interface TelemetrySummary {
  totals_by_verdict: Record<string, number>;
  series_daily: Array<Record<string, string | number>>;
  by_state: Array<{ state_code: string; count_flagged: number }>;
  top_impersonated: Array<{ entity: string; count: number }>;
  campaigns: Array<{
    campaign: string;
    count: number;
    last_seen: string;
    channels: string[];
  }>;
}

export type Locale = "en" | "hi";

export interface VerifyInput {
  file?: File;
  text?: string;
  url?: string;
  claimedSenderText?: string;
  stateCode?: string;
  locale?: Locale;
  channel?: "sim" | "whatsapp" | "telegram";
}

export async function verifySubmit(
  input: VerifyInput
): Promise<ApiResponse<CardPayload>> {
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  if (input.text !== undefined) form.append("text", input.text);
  if (input.url !== undefined) form.append("url", input.url);
  if (input.claimedSenderText) form.append("claimed_sender_text", input.claimedSenderText);
  if (input.stateCode) form.append("state_code", input.stateCode);
  form.append("locale", input.locale ?? "en");
  form.append("channel", input.channel ?? "sim");

  const res = await fetch(`${API_BASE_URL}/api/verify`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export interface StageEvent {
  stage: "reading" | "signature" | "registry" | "risk";
  label: string;
  detail: string;
  outcome: string | null;
  /** Real measured duration of this stage on the server, not a paced value. */
  ms: number;
}

/** The four stages the server reports, in order. Known up front so the UI can
 * show what is *about* to be checked, greyed out, rather than popping rows in
 * from nowhere. */
export const VERIFY_STAGES: StageEvent["stage"][] = [
  "reading",
  "signature",
  "registry",
  "risk",
];

/**
 * Streams a verification, calling `onStage` as each stage genuinely completes
 * on the server. Falls back to nothing special on error — the caller decides.
 *
 * Uses fetch + ReadableStream rather than EventSource because this is a POST
 * with a file body, which EventSource cannot do.
 */
export async function verifyStream(
  input: VerifyInput,
  handlers: {
    onStage?: (stage: StageEvent) => void;
    onResult?: (card: CardPayload) => void;
    onError?: (error: ApiError) => void;
  }
): Promise<void> {
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  if (input.text !== undefined) form.append("text", input.text);
  if (input.url !== undefined) form.append("url", input.url);
  if (input.claimedSenderText) form.append("claimed_sender_text", input.claimedSenderText);
  if (input.stateCode) form.append("state_code", input.stateCode);
  form.append("locale", input.locale ?? "en");
  form.append("channel", input.channel ?? "sim");

  const res = await fetch(`${API_BASE_URL}/api/verify/stream`, {
    method: "POST",
    body: form,
  });

  // Guard rails (rate limit, bad input) come back as a normal JSON error.
  if (!res.ok || !res.body || !res.headers.get("content-type")?.includes("event-stream")) {
    const body = (await res.json().catch(() => null)) as ApiResponse<never> | null;
    handlers.onError?.(
      body?.error ?? { code: "stream_failed", message: "Could not reach the server." }
    );
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line; keep any partial tail.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        const event = JSON.parse(line.slice(6));
        if (event.type === "stage") handlers.onStage?.(event.payload as StageEvent);
        else if (event.type === "result") handlers.onResult?.(event.payload as CardPayload);
        else if (event.type === "error") handlers.onError?.(event.payload.error as ApiError);
      } catch {
        // a malformed frame shouldn't kill the rest of the stream
      }
    }
  }
}

/**
 * /api/sim/* — a frontend-only demo endpoint, distinct from the real
 * channel webhooks (backend/app/api/webhooks_telegram.py,
 * webhooks_whatsapp.py). It runs the exact same verification pipeline and
 * the exact same reply-formatting functions those webhooks use
 * (channels/telegram.py::build_reply, channels/whatsapp.py::build_reply),
 * but never sends anything anywhere — it exists purely so this app can
 * show what a Telegram/WhatsApp reply would literally say.
 */
export interface ChannelSimInput {
  file?: File;
  text?: string;
  /** Caption on a forwarded photo/document/video — irrelevant for a plain
   * text message, matching how a real caption field works. */
  caption?: string;
}

export interface TelegramSimReply {
  /** The literal Telegram message text, incl. its <b>bold</b> HTML tag. */
  text: string;
  buttons: ButtonSpec[];
  card: CardPayload;
}

export interface WhatsAppSimReply {
  /** The literal WhatsApp message text, incl. its *bold* markdown-style tag. */
  text: string;
  card: CardPayload;
}

export interface SmsSimReply {
  /** The literal SMS reply body — plain text, no markup (real SMS has none). */
  text: string;
}

function channelSimForm(input: ChannelSimInput): FormData {
  const form = new FormData();
  if (input.file) form.append("file", input.file);
  if (input.text !== undefined) form.append("text", input.text);
  if (input.caption) form.append("caption", input.caption);
  return form;
}

export async function simTelegram(
  input: ChannelSimInput
): Promise<ApiResponse<TelegramSimReply>> {
  const res = await fetch(`${API_BASE_URL}/api/sim/telegram`, {
    method: "POST",
    body: channelSimForm(input),
  });
  return res.json();
}

export async function simWhatsapp(
  input: ChannelSimInput
): Promise<ApiResponse<WhatsAppSimReply>> {
  const res = await fetch(`${API_BASE_URL}/api/sim/whatsapp`, {
    method: "POST",
    body: channelSimForm(input),
  });
  return res.json();
}

/** Text only — the SMS simulator endpoint has no `file` parameter at all
 * (see api/sim.py's sim_sms docstring for why), so `input.file` is ignored
 * here rather than silently sent and dropped server-side. */
export async function simSms(input: ChannelSimInput): Promise<ApiResponse<SmsSimReply>> {
  const form = new FormData();
  if (input.text !== undefined) form.append("text", input.text);
  const res = await fetch(`${API_BASE_URL}/api/sim/sms`, { method: "POST", body: form });
  return res.json();
}

export async function getVerification(
  id: string,
  locale: Locale = "en"
): Promise<ApiResponse<CardPayload>> {
  const res = await fetch(
    `${API_BASE_URL}/api/verifications/${id}?locale=${locale}`
  );
  return res.json();
}

export async function getCertificate(
  token: string
): Promise<{ status: number; body: ApiResponse<CertificatePayload> }> {
  const res = await fetch(`${API_BASE_URL}/api/c/${token}`);
  return { status: res.status, body: await res.json() };
}

/** One recent check, for the dashboard feed. Aggregate fields only — what a
 * user submitted is never stored, so it is never returned. */
export interface RecentCheck {
  id: string;
  verdict: string;
  input_kind: string;
  channel: string;
  campaign: string | null;
  state_code: string | null;
  latency_ms: number;
  created_at: string;
}

export async function getRecentChecks(limit = 12): Promise<ApiResponse<RecentCheck[]>> {
  const res = await fetch(`${API_BASE_URL}/api/telemetry/recent?limit=${limit}`);
  return res.json();
}

/** How communications get into the record, and how many came from where. */
export interface IngestFeed {
  name: string;
  adapter: string;
  origin: string;
  /** true when pointed at a live endpoint rather than the sample file */
  live: boolean;
  ingested: number;
}

export interface IngestStatus {
  feeds: IngestFeed[];
  by_source: Record<string, number>;
  total_published: number;
  ingested_total: number;
}

export async function getIngestStatus(): Promise<ApiResponse<IngestStatus>> {
  const res = await fetch(`${API_BASE_URL}/api/ingest/status`);
  return res.json();
}

export async function runIngest(): Promise<ApiResponse<{ published: number }>> {
  const res = await fetch(`${API_BASE_URL}/api/ingest/run`, { method: "POST" });
  return res.json();
}

export async function getTelemetrySummary(
  window = "14d"
): Promise<ApiResponse<TelemetrySummary>> {
  const res = await fetch(
    `${API_BASE_URL}/api/telemetry/summary?window=${window}`
  );
  return res.json();
}

// --- Registry ---

export interface KeyOut {
  id: string;
  label: string;
  role: string;
  public_key_ed25519: string;
  status: string;
  valid_from: string;
  revoked_at: string | null;
  revocation_reason: string | null;
}

export interface EntityOut {
  id: string;
  name: string;
  kind: string;
  sebi_reg_no: string;
  status: string;
  keys: KeyOut[];
}

export interface EntityDetailOut extends EntityOut {
  domains: Array<{ domain: string; kind: string }>;
  sms_headers: Array<{ header: string }>;
}

export async function listEntities(): Promise<ApiResponse<EntityOut[]>> {
  const res = await fetch(`${API_BASE_URL}/api/registry/entities`);
  return res.json();
}

export async function getEntity(id: string): Promise<ApiResponse<EntityDetailOut>> {
  const res = await fetch(`${API_BASE_URL}/api/registry/entities/${id}`);
  return res.json();
}

// --- Transparency log ---

export interface LogRoot {
  tree_size: number;
  root_hash: string;
  timestamp: string | null;
  sth_sig: string | null;
  registry_public_key: string;
}

export interface LogEntryOut {
  seq: number;
  leaf_hash: string;
  entry: Record<string, unknown>;
  tree_size: number;
  root_hash: string;
  created_at: string;
}

export interface InclusionProof {
  leaf_index: number;
  leaf_hash: string;
  audit_path: string[];
  tree_size: number;
  root_hash: string;
}

export async function getLogRoot(): Promise<ApiResponse<LogRoot>> {
  const res = await fetch(`${API_BASE_URL}/api/log/root`);
  return res.json();
}

export async function listLogEntries(limit = 50): Promise<ApiResponse<LogEntryOut[]>> {
  const res = await fetch(`${API_BASE_URL}/api/log/entries?limit=${limit}`);
  return res.json();
}

export async function getInclusionProof(seq: number): Promise<ApiResponse<InclusionProof>> {
  const res = await fetch(`${API_BASE_URL}/api/log/entries/${seq}/proof`);
  return res.json();
}

// --- Issuer (demo persona via X-Demo-Persona header, no real auth) ---

export interface CommOut {
  id: string;
  entity_id: string;
  title: string;
  channel: string;
  impact: string;
  status: string;
  published_at: string | null;
  log_seq: number | null;
  artifact_sha256: string | null;
}

function personaHeaders(personaKeyId: string): HeadersInit {
  return { "X-Demo-Persona": personaKeyId };
}

export async function listCommunications(
  entityId: string
): Promise<ApiResponse<CommOut[]>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications?entity_id=${entityId}`
  );
  return res.json();
}

export async function createCommunication(input: {
  entityId: string;
  title: string;
  channel: string;
  impact: string;
  file?: File;
  canonicalText?: string;
  personaKeyId: string;
}): Promise<ApiResponse<CommOut>> {
  const form = new FormData();
  form.append("entity_id", input.entityId);
  form.append("title", input.title);
  form.append("channel", input.channel);
  form.append("impact", input.impact);
  if (input.file) form.append("file", input.file);
  if (input.canonicalText) form.append("canonical_text", input.canonicalText);
  const res = await fetch(`${API_BASE_URL}/api/issuer/communications`, {
    method: "POST",
    body: form,
    headers: personaHeaders(input.personaKeyId),
  });
  return res.json();
}

export async function makerSign(
  commId: string,
  personaKeyId: string
): Promise<ApiResponse<CommOut>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications/${commId}/sign`,
    { method: "POST", headers: personaHeaders(personaKeyId) }
  );
  return res.json();
}

export interface CosignResult extends CommOut {
  old_root: string;
  new_root: string;
}

export async function cosignAndPublish(
  commId: string,
  personaKeyId: string
): Promise<ApiResponse<CosignResult>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications/${commId}/cosign`,
    { method: "POST", headers: personaHeaders(personaKeyId) }
  );
  return res.json();
}

export async function revokeCommunication(
  commId: string,
  personaKeyId: string
): Promise<ApiResponse<CommOut & { revocation_log_seq: number }>> {
  const res = await fetch(
    `${API_BASE_URL}/api/issuer/communications/${commId}/revoke`,
    { method: "POST", headers: personaHeaders(personaKeyId) }
  );
  return res.json();
}

// --- Trust Circle ---
// No auth exists in this app — possession of `circle_token` (an unguessable
// random token, the same bearer-capability pattern as certificate links)
// is what proves you're the guardian for a given circle.

export interface CircleAlertOut {
  verdict: string;
  plain_headline: string;
  campaign: string | null;
  delivered_via: "channel" | "email" | "none";
  created_at: string;
}

export interface CircleStatusOut {
  status: "pending" | "active" | "revoked";
  elder_channel: "whatsapp" | "telegram" | "email" | "sms";
  elder_masked: string;
  guardian_name: string | null;
  guardian_email: string | null;
  guardian_channel: "whatsapp" | "telegram" | "email" | "sms" | null;
  /** Auto-Guard: automatic scanning of every message on the elder's own
   * phone, via an SMS-forwarder app or Twilio number pointed at
   * `guard_webhook_url`. Independent of `elder_channel` above — that's how
   * they set the circle up; this is a separate, optional capability. */
  guard_enabled: boolean;
  guard_webhook_url: string | null;
  alerts: CircleAlertOut[];
}

export async function pairCircleComplete(input: {
  code: string;
  guardianName: string;
  guardianEmail: string;
}): Promise<ApiResponse<{ circle_token: string }>> {
  const res = await fetch(`${API_BASE_URL}/api/circle/pair/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code: input.code,
      guardian_name: input.guardianName,
      guardian_email: input.guardianEmail,
    }),
  });
  return res.json();
}

export async function getCircleStatus(
  circleToken: string
): Promise<ApiResponse<CircleStatusOut>> {
  const res = await fetch(`${API_BASE_URL}/api/circle/${circleToken}`);
  return res.json();
}

export async function revokeCircle(
  circleToken: string
): Promise<ApiResponse<{ status: string }>> {
  const res = await fetch(`${API_BASE_URL}/api/circle/${circleToken}/revoke`, {
    method: "POST",
  });
  return res.json();
}

export interface GuardTokenOut {
  guard_token: string;
  webhook_url: string;
}

export async function enableGuard(circleToken: string): Promise<ApiResponse<GuardTokenOut>> {
  const res = await fetch(`${API_BASE_URL}/api/circle/${circleToken}/guard`, { method: "POST" });
  return res.json();
}

export async function regenerateGuard(circleToken: string): Promise<ApiResponse<GuardTokenOut>> {
  const res = await fetch(`${API_BASE_URL}/api/circle/${circleToken}/guard/regenerate`, {
    method: "POST",
  });
  return res.json();
}

export async function disableGuard(
  circleToken: string
): Promise<ApiResponse<{ guard_enabled: boolean }>> {
  const res = await fetch(`${API_BASE_URL}/api/circle/${circleToken}/guard/disable`, {
    method: "POST",
  });
  return res.json();
}

/** Fires a message at the REAL Auto-Guard webhook — not a simulator
 * endpoint, the exact route an SMS-forwarder app or Twilio number calls in
 * production. Used by the guardian dashboard's "send a test message" demo:
 * proof this works end to end is the alert it produces actually landing in
 * `getCircleStatus`'s alert history afterward, not a canned response here. */
export async function sendGuardTestMessage(
  webhookUrl: string,
  fromLabel: string,
  body: string
): Promise<{ ok: boolean }> {
  try {
    const res = await fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from: fromLabel, body }),
    });
    return { ok: res.ok };
  } catch {
    return { ok: false };
  }
}

export async function revokeKey(
  keyId: string,
  reason: string
): Promise<
  ApiResponse<{ key_id: string; status: string; revoked_at: string | null; revocation_log_seq: number }>
> {
  const res = await fetch(`${API_BASE_URL}/api/admin/keys/${keyId}/revoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  return res.json();
}
