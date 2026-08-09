import { getCertificate } from "@/lib/api";
import { Reveal } from "@/components/Reveal";

// Full animated Merkle-proof verification (client-side, via the TS
// verify_inclusion mirror) lands in Epic 7 alongside the log explorer —
// this page renders the certificate payload the API already returns today.

export default async function CertificatePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const { status, body } = await getCertificate(token);

  if (status !== 200 || !body.ok || !body.data) {
    return (
      <div className="mx-auto max-w-lg px-6 py-24 text-center">
        <h1 className="font-display text-2xl font-bold text-ink">
          {status === 410 ? "This link has been used" : "Link not found"}
        </h1>
        <p className="mt-3 text-sm text-info">
          {body.error?.message ??
            "One-time certificate links can only be viewed once. Request a fresh link from the verify result that produced it."}
        </p>
      </div>
    );
  }

  const cert = body.data;

  return (
    <div className="mx-auto max-w-xl px-6 py-16">
      <Reveal className="rounded border-l-4 border-verified bg-card p-6 shadow-sm">
        <h1 className="font-display text-xl font-bold text-ink">
          {cert.verdict === "VERIFIED_NOTICE" ? "⚠️ Verified — with notice" : "✅ Verified"}
        </h1>

        {cert.entity && (
          <div className="mt-4">
            <div className="text-sm text-info">Issued by</div>
            <div className="font-display text-lg font-semibold text-ink">{cert.entity.name}</div>
            <div className="font-mono text-sm text-info">{cert.entity.sebi_reg_no}</div>
          </div>
        )}

        <div className="mt-4">
          <div className="text-sm text-info">Communication</div>
          <div className="text-ink">{cert.communication.title}</div>
          <div className="font-mono text-xs text-info">
            {cert.communication.channel} · published{" "}
            {cert.communication.published_at?.slice(0, 10) ?? "—"} · log #
            {cert.communication.log_seq}
          </div>
        </div>

        {cert.artifact_sha256 && (
          <div className="mt-4">
            <div className="text-sm text-info">Artifact SHA-256</div>
            <div className="break-all font-mono text-xs text-ink">{cert.artifact_sha256}</div>
          </div>
        )}

        <div className="mt-4">
          <div className="text-sm text-info">Signature chain</div>
          <div className="font-mono text-xs text-ink">
            maker key {cert.signature_chain.maker_key_id?.slice(0, 8)}… (
            {cert.signature_chain.maker_key_status})
          </div>
          {cert.signature_chain.checker_key_id && (
            <div className="font-mono text-xs text-ink">
              checker key {cert.signature_chain.checker_key_id.slice(0, 8)}… (
              {cert.signature_chain.checker_key_status})
            </div>
          )}
        </div>

        {cert.inclusion_proof && (
          <div className="mt-4">
            <div className="text-sm text-info">Transparency log root</div>
            <div className="break-all font-mono text-xs text-ink">
              {cert.inclusion_proof.root_hash}
            </div>
            <div className="mt-1 text-xs text-info">
              leaf {cert.inclusion_proof.leaf_index} of {cert.inclusion_proof.tree_size} —
              inclusion proof verifies live in the log explorer (Epic 7).
            </div>
          </div>
        )}
      </Reveal>
    </div>
  );
}
