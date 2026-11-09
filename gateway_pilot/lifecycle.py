"""Read-only preflight for WF-047 model and WF-081 firmware artifacts."""

import hashlib
import json
import re
from pathlib import Path


def preflight_artifact(path, manifest, *, platform, current_revision, free_bytes,
                       capabilities, recovery_verified, verify_signature):
    """Bind a candidate to a trusted signature verifier and observed device constraints."""
    fields = ("kind", "platform", "revision", "size_bytes", "sha256")
    if not isinstance(manifest, dict) or set(manifest) != {*fields, "signature"}:
        return {"status": "BLOCKED", "reason": "invalid_manifest"}
    metadata = {key: manifest[key] for key in fields}
    kind = metadata["kind"]
    if kind not in ("model", "firmware"):
        return {"status": "BLOCKED", "reason": "unsupported_artifact_kind"}
    workflow = "WF-047" if kind == "model" else "WF-081"

    def blocked(reason):
        return {"workflow_id": workflow, "status": "BLOCKED", "reason": reason}

    if f"lifecycle.{kind}.preflight" not in capabilities:
        return blocked("capability_unavailable")
    if metadata["platform"] != platform:
        return blocked("incompatible_platform")
    if type(metadata["revision"]) is not int or metadata["revision"] <= current_revision:
        return blocked("revision_not_newer")
    size = metadata["size_bytes"]
    digest = metadata["sha256"]
    if (type(size) is not int or size <= 0 or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        return blocked("invalid_manifest")
    if size > free_bytes:
        return blocked("insufficient_storage")
    if recovery_verified is not True:
        return blocked("recovery_unverified")
    signature = manifest["signature"]
    if not isinstance(signature, bytes) or not signature or verify_signature is None:
        return blocked("signature_verification_unavailable")
    payload = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        if verify_signature(payload, signature) is not True:
            return blocked("signature_invalid")
        artifact = Path(path)
        if artifact.stat().st_size != size:
            return blocked("artifact_size_mismatch")
        with artifact.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                return blocked("artifact_digest_mismatch")
    except (OSError, ValueError):
        return blocked("verification_error")
    return {"workflow_id": workflow, "status": "PREFLIGHT_OK", "sha256": digest,
            "revision": metadata["revision"], "size_bytes": size}
