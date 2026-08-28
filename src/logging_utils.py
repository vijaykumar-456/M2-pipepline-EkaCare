"""
Structured (JSON-lines) logging for the two events that must always be
logged, per the abdm-m2-care-context-linking skill:
  1. every Phase 1 push (link attempt), success or failure
  2. every Phase 2 FHIR bundle creation and transfer

Never log PHI/bundle contents -- only IDs and references. Never log the
raw request/response body if it might contain patient data.
"""
import json
import os
from datetime import datetime, timezone

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def _write(log_file: str, record: dict):
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    path = os.path.join(LOG_DIR, log_file)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def log_push_event(env: str, row_id: str, care_context_id: str, hi_type: str,
                    status: str, http_status: int | None = None, error: str = ""):
    """Call this every time a Phase 1 link push happens -- whether it
    succeeded or failed. Log the failure especially; that's often the
    more important record to have."""
    _write("push_events.log", {
        "event": "care_context_push",
        "env": env,
        "row_id": row_id,
        "care_context_id": care_context_id,
        "hi_type": hi_type,
        "status": status,               # e.g. "sent" / "failed"
        "http_status": http_status,
        "error": error,
    })


def log_bundle_event(env: str, row_id: str, hiu_id: str, consent_artifact_id: str,
                      hi_types: str, event_type: str, status: str, error: str = ""):
    """Call this on FHIR bundle creation AND separately on transfer, so
    'built but not delivered' is distinguishable from 'never built'."""
    _write("bundle_events.log", {
        "event": event_type,            # "bundle_created" or "bundle_transferred"
        "env": env,
        "row_id": row_id,
        "hiu_id": hiu_id,
        "consent_artifact_id": consent_artifact_id,
        "hi_types": hi_types,
        "status": status,
        "error": error,
    })
