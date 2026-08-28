"""
CLI entrypoint: runs the Phase 1 pipeline for ONE row, steps 1-4.
Step 5 (webhook result) happens asynchronously in webhook_server.py.

Example:
    python scripts/run_phase1_for_row.py \\
        --row-id P001 \\
        --m1-json /mnt/user-data/uploads/Abha_Response.txt \\
        --partner-patient-id P001 \\
        --encounter-id ENC-P001-001 \\
        --encounter-date 2026-08-27 \\
        --hi-type OPConsultation

Deliberately does NOT batch multiple rows -- per the plan, prove one row
end-to-end (push -> log -> webhook -> ledger update) before batching.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import flat_table_manager as ftm
import logging_utils as log
import eka_client
from config import load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--row-id", required=True)
    parser.add_argument("--m1-json", required=True, help="Path to the M1 response JSON file")
    # parser.add_argument("--partner-patient-id", required=True)
    parser.add_argument("--encounter-id", required=True)
    parser.add_argument("--encounter-date", required=True)
    parser.add_argument("--hi-type", required=True)
    parser.add_argument("--clinic-id", default="SRM_CHENNAI")
    # parser.add_argument("--auth-token", default=os.environ.get("EKA_AUTH_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true",
                         help="Build the row and print it, but don't actually call the Link API")
    args = parser.parse_args()

    config = load_config()

    with open(args.m1_json) as f:
        text = f.read()
        text = text.split("JSON:", 1)[-1].strip()
        m1_json = json.loads(text)

    # Step 1
    ftm.add_or_update_identity_from_m1(args.row_id, m1_json)

    # Step 2 -- NOTE: clinical data isn't collected via CLI args here on
    # purpose. Call ftm.set_clinical_data(row_id, **fields) separately
    # (or from your HIS integration) before running this script, or
    # right after, before Phase 2 needs it.

    # Step 3
    row = ftm.generate_care_context(
        args.row_id, hi_type=args.hi_type,
        # partner_patient_id=args.partner_patient_id,
        hip_id=config.hip_id, encounter_id=args.encounter_id,
        encounter_date=args.encounter_date, clinic_id=args.clinic_id,
    )

    print(json.dumps(row, indent=2))

    if args.dry_run:
        print("\n[dry-run] Skipping actual Link API call.")
        return

    # if not args.auth_token:
    #     print("\nNo auth token supplied (--auth-token or EKA_AUTH_TOKEN env var) -- "
    #           "cannot make the real API call. Exiting without calling Link API.")
    #     return

    # Step 4
    try:
        eka_client.link_care_context(config, row)
        ftm.mark_link_sent(row["record_id"])
        log.log_push_event(env=config.env, row_id=row["record_id"],
                            care_context_id=row["care_context_id"],
                            hi_type=row["hi_type"], status="sent", http_status=202)
        print("\nLink request sent (202). Awaiting webhook for final status.")
    # except eka_client.EkaLinkError as e:
    #     log.log_push_event(env=config.env, row_id=args.row_id,
    #                         care_context_id=row["care_context_id"],
    #                         hi_type=row["hi_type"], status="failed",
    #                         http_status=e.http_status, error=str(e))
    #     print(f"\nLink API call failed: {e}")
    #     raise
    except eka_client.EkaLinkError as e:
        log.log_push_event(
            env=config.env,
            row_id=row["record_id"],
            care_context_id=row["care_context_id"],
            hi_type=row["hi_type"],
            status="failed",
            http_status=e.http_status,
            error=str(e),
        )

        print(f"\nLink API call failed: {e}")
        print(f"HTTP status: {e.http_status}")
        print(f"Eka response body: {e.body}")

        raise


if __name__ == "__main__":
    main()
