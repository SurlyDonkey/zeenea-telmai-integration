"""
Telmai webhook receiver.

When Telmai completes a data scan it fires a POST to this endpoint.
We immediately call the Check for Alerts API, compute a quality score,
and write updated properties back to the linked Zeenea item — no waiting
for the next scheduled pull.

Security: HMAC-SHA256 signature in the X-Telmai-Signature header.
  Header value format: "sha256=<hex-digest>"
  Computed from: HMAC-SHA256(TELMAI_WEBHOOK_SECRET, raw request body)
  If TELMAI_WEBHOOK_SECRET is not set the signature check is skipped
  (dev / open mode — same pattern as the API key auth).

Endpoint registered by main.py at: POST /api/webhooks/telmai
"""

import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from database import AssetMapping, SyncLogEntry as DBSyncLogEntry, get_session
from models import SyncLogEntry, TelmaiWebhookPayload, WebhookResult
from store import get_telmai_client, get_zeenea_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

async def _verify_signature(request: Request) -> bytes:
    """
    Read the raw body and verify the HMAC-SHA256 signature.
    Returns the raw body bytes so the caller can re-parse as JSON.
    Raises HTTP 401 if the signature is invalid.
    """
    secret = os.getenv("TELMAI_WEBHOOK_SECRET", "")
    body = await request.body()

    if not secret:
        # No secret configured — open mode, skip verification
        logger.warning(
            "TELMAI_WEBHOOK_SECRET not set — webhook signature verification disabled"
        )
        return body

    sig_header = request.headers.get("X-Telmai-Signature", "")
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Telmai-Signature header",
        )

    # Expected format: "sha256=<hexdigest>"
    if sig_header.startswith("sha256="):
        provided_digest = sig_header[7:]
    else:
        provided_digest = sig_header

    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(provided_digest, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature mismatch — check TELMAI_WEBHOOK_SECRET",
        )

    return body


# ---------------------------------------------------------------------------
# Quality score calculation from raw alerts
# ---------------------------------------------------------------------------

_SEVERITY_PENALTY = {
    "CRITICAL": 20.0,
    "HIGH":     10.0,
    "MEDIUM":    5.0,
    "WARNING":   2.0,
    "LOW":       1.0,
}


def _score_from_alerts(alerts: list) -> float:
    """
    Derive a 0-100 quality score from a list of raw Telmai alert objects.

    Starts at 100 and subtracts a penalty for each open alert weighted
    by severity. Floor is 0.
    """
    score = 100.0
    for alert in alerts:
        severity = (alert.get("priority") or alert.get("severity") or "LOW").upper()
        score -= _SEVERITY_PENALTY.get(severity, 1.0)
    return max(round(score, 1), 0.0)


# ---------------------------------------------------------------------------
# Helper: persist a log entry
# ---------------------------------------------------------------------------

def _log(
    session: Session,
    direction: str,
    asset_name: str,
    status: str,
    message: str,
) -> SyncLogEntry:
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session.add(DBSyncLogEntry(
        id=entry_id,
        timestamp=now,
        direction=direction,
        asset_name=asset_name,
        status=status,
        message=message,
    ))
    session.commit()
    return SyncLogEntry(
        id=entry_id, timestamp=now, direction=direction,
        asset_name=asset_name, status=status, message=message,
    )


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------

@router.post("/telmai", response_model=WebhookResult)
async def telmai_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> WebhookResult:
    """
    Receive a Telmai scan-complete webhook and immediately sync quality
    data back to the linked Zeenea catalog item.

    Flow:
      1. Verify HMAC-SHA256 signature
      2. Parse payload  { source_id, job_id, event, tenant? }
      3. Call Telmai Check for Alerts API  →  raw alert list for this job
      4. Compute quality score from alert severities
      5. Look up the Zeenea asset linked to this Telmai source
      6. Write DTC / certification / assetStatus properties to Zeenea
      7. Persist sync log entry with direction="webhook"
    """
    # 1. Verify + read raw body
    raw_body = await _verify_signature(request)

    # 2. Parse payload
    import json as _json
    try:
        data = _json.loads(raw_body)
        payload = TelmaiWebhookPayload(**data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid webhook payload: {e}",
        )

    source_id = payload.source_id
    job_id = payload.job_id
    logger.info("Webhook received: source=%s job=%s event=%s", source_id, job_id, payload.event)

    telmai = get_telmai_client()
    zeenea = get_zeenea_client()

    # 3. Fetch alerts for this specific job from Telmai
    try:
        alerts = await telmai.check_for_alerts(source_id=source_id, job_id=job_id)
    except Exception as e:
        logger.error("check_for_alerts failed: %s", e)
        _log(session, "webhook", source_id, "failed",
             f"check_for_alerts error: {str(e)[:150]}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch alerts from Telmai: {e}",
        )

    alerts_found = len(alerts)
    logger.info("check_for_alerts → %d alerts for source=%s job=%s", alerts_found, source_id, job_id)

    # 4. Compute quality score
    quality_score = _score_from_alerts(alerts)

    # 5. Find the Zeenea mapping for this Telmai source
    #    source_id maps to telmai_id in our AssetMapping table
    mapping = session.exec(
        select(AssetMapping).where(AssetMapping.telmai_id == source_id)
    ).first()

    asset_label = source_id  # fallback for log messages

    if not mapping:
        # No mapping yet — log it but don't fail (asset may not be linked yet)
        logger.warning("No Zeenea mapping for Telmai source '%s' — skipping writeback", source_id)
        _log(session, "webhook", source_id, "skipped",
             f"No Zeenea mapping for source '{source_id}' — link it in the Asset Browser")
        return WebhookResult(
            source_id=source_id,
            job_id=job_id,
            alerts_found=alerts_found,
            zeenea_updated=False,
            quality_score=quality_score,
            message=f"No Zeenea mapping found for source '{source_id}'",
        )

    asset_label = mapping.telmai_name or source_id

    # 6. Write quality properties back to Zeenea
    try:
        updated = await zeenea.update_quality_properties(
            item_id=mapping.zeenea_id,
            score=quality_score,
            alert_count=alerts_found,
            last_checked=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error("Zeenea update failed for '%s': %s", mapping.zeenea_id, e)
        _log(session, "webhook", asset_label, "failed",
             f"Zeenea update error: {str(e)[:150]}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to update Zeenea: {e}",
        )

    # Update last_synced timestamp on the mapping
    mapping.last_synced = datetime.now(timezone.utc)
    session.add(mapping)
    session.commit()

    # 7. Log the event
    msg = (
        f"Webhook: {alerts_found} alert(s) from job '{job_id}' → "
        f"score {quality_score:.1f} written to Zeenea"
    )
    _log(session, "webhook", asset_label, "success" if updated else "failed", msg)

    return WebhookResult(
        source_id=source_id,
        job_id=job_id,
        alerts_found=alerts_found,
        zeenea_updated=updated,
        quality_score=quality_score,
        message=msg,
    )


# ---------------------------------------------------------------------------
# Webhook config info endpoint (no auth — safe, returns non-secret info)
# ---------------------------------------------------------------------------

@router.get("/telmai/config")
async def webhook_config(request: Request) -> dict:
    """
    Returns the webhook URL and whether a secret is configured.
    Used by the Settings page to display setup instructions.
    """
    base_url = str(request.base_url).rstrip("/")
    secret_set = bool(os.getenv("TELMAI_WEBHOOK_SECRET", ""))
    return {
        "webhook_url": f"{base_url}/api/webhooks/telmai",
        "method": "POST",
        "signature_header": "X-Telmai-Signature",
        "signature_format": "sha256=<hmac-sha256-hex>",
        "secret_configured": secret_set,
        "event_type": "scan_complete",
        "payload_example": {
            "source_id": "your-telmai-source-id",
            "job_id": "your-job-id",
            "event": "scan_complete",
        },
    }
