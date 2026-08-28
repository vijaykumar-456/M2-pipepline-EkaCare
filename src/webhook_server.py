# """"
# Single webhook endpoint per the abdm-m2-care-context-linking skill's
# integration blueprint: one endpoint, routed on event type.
#
# Run locally with a tunnel (ngrok/cloudflared) pointed at this during dev:
#     python src/webhook_server.py
#
# TODO before trusting this in sandbox/prod: verify Eka's webhook signature
# on every incoming request. The skill doesn't specify the exact signature
# scheme -- check Eka's console/docs for the header name and verification
# method before removing the placeholder check below.
# """
# import sys
# import os
#
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#
# from flask import Flask, request, jsonify
# import flat_table_manager as ftm
# import logging_utils as log
# import fhir_builder
# import encryption
# import json
#
# app = Flask(__name__)
#
#
# def _verify_signature(req) -> bool:
#     # PLACEHOLDER -- replace with Eka's real signature verification.
#     # Do not deploy to prod with this returning True unconditionally.
#     return True
#
#
# @app.route("/webhooks/eka", methods=["POST"])
# def handle_webhook():
#     if not _verify_signature(request):
#         return jsonify({"error": "invalid signature"}), 401
#
#     payload = request.get_json(force=True, silent=True) or {}
#     event_type = payload.get("event")
#
#     if event_type == "abha.link_care_context":
#         row_id = payload.get("partner_patient_id")  # confirm exact field name from real payload
#         status = payload.get("status")              # "LINKED" or "ERRORED"
#         error = payload.get("error", "")
#         if not row_id:
#             return jsonify({"error": "missing partner_patient_id in payload"}), 400
#         ftm.mark_link_webhook_result(row_id, status=status, error=error)
#         try:
#             row = ftm.get_row(row_id)
#             log.log_push_event(
#                 env=os.environ.get("EKA_ENV", "sandbox"), row_id=row_id,
#                 care_context_id=row.get("care_context_id", ""),
#                 hi_type=row.get("hi_type", ""), status=status, error=error,
#             )
#         except ValueError:
#             pass
#         return jsonify({"ok": True}), 200
#
#     elif event_type == "abha.hip_data_fetch":
#
#         # ---------------------------------------------------------
#         # Phase 2: HIU has requested health data
#         # ---------------------------------------------------------
#
#         transaction_id = payload.get("transaction_id", "")
#
#         data = payload.get("data", {})
#
#         care_contexts = data.get("care_contexts", [])
#
#         key_information = data.get("key_information", {})
#
#         hiu_id = data.get("hiu_id", "")
#
#         if not transaction_id:
#             return jsonify({
#                 "error": "missing transaction_id"
#             }), 400
#
#         if not care_contexts:
#             return jsonify({
#                 "error": "missing care_contexts"
#             }), 400
#
#         if not key_information:
#             return jsonify({
#                 "error": "missing key_information"
#             }), 400
#
#         # ---------------------------------------------------------
#         # Process each requested Care Context
#         # ---------------------------------------------------------
#
#         for requested_context in care_contexts:
#
#             care_context_id = requested_context.get(
#                 "care_context_id"
#             )
#
#             if not care_context_id:
#                 return jsonify({
#                     "error": "missing care_context_id"
#                 }), 400
#
#             try:
#                 row = ftm.find_row_by_care_context_id(
#                     care_context_id
#                 )
#             except ValueError:
#                 return jsonify({
#                     "error": f"unknown care_context_id: {care_context_id}"
#                 }), 404
#
#             row_id = row["row_id"]
#
#             env = os.environ.get(
#                 "EKA_ENV",
#                 "sandbox"
#             )
#
#             # -----------------------------------------------------
#             # Consent check
#             # -----------------------------------------------------
#
#             if not ftm.check_consent_before_bundling(row_id):
#                 log.log_bundle_event(
#                     env=env,
#                     row_id=row_id,
#                     hiu_id=hiu_id,
#                     consent_artifact_id=row.get(
#                         "consent_artifact_id",
#                         ""
#                     ),
#                     hi_types=row.get(
#                         "hi_type",
#                         ""
#                     ),
#                     event_type="bundle_blocked",
#                     status="denied",
#                     error=(
#                         "consent not granted or "
#                         "care context not linked"
#                     ),
#                 )
#
#                 return jsonify({
#                     "error": (
#                         "consent not granted for "
#                         "this care context"
#                     )
#                 }), 403
#
#             # -----------------------------------------------------
#             # Build FHIR Bundle
#             # -----------------------------------------------------
#
#             try:
#
#                 bundle = fhir_builder.build_bundle(row)
#
#                 ftm.mark_bundle_created(row_id)
#
#                 log.log_bundle_event(
#                     env=env,
#                     row_id=row_id,
#                     hiu_id=hiu_id,
#                     consent_artifact_id=row.get(
#                         "consent_artifact_id",
#                         ""
#                     ),
#                     hi_types=row.get(
#                         "hi_type",
#                         ""
#                     ),
#                     event_type="bundle_created",
#                     status="ok",
#                 )
#
#             except Exception as e:
#
#                 log.log_bundle_event(
#                     env=env,
#                     row_id=row_id,
#                     hiu_id=hiu_id,
#                     consent_artifact_id=row.get(
#                         "consent_artifact_id",
#                         ""
#                     ),
#                     hi_types=row.get(
#                         "hi_type",
#                         ""
#                     ),
#                     event_type="bundle_created",
#                     status="failed",
#                     error=str(e),
#                 )
#
#                 return jsonify({
#                     "error": "bundle build failed"
#                 }), 500
#
#             # -----------------------------------------------------
#             # Encrypt + send to Eka
#             # -----------------------------------------------------
#
#             try:
#
#                 encrypted = encryption.encrypt_fhir_bundle(
#                     json.dumps(bundle),
#                     key_information,
#                 )
#
#                 # IMPORTANT:
#                 # Do NOT mark as "sent" here.
#                 # First call the actual Eka Data On-Fetch API.
#
#                 # response = eka_client.push_on_fetch_response(
#                 #     config=config,
#                 #     transaction_id=transaction_id,
#                 #     encrypted_data=encrypted,
#                 #     key_information=key_information,
#                 # )
#
#                 # Only after successful API response:
#                 #
#                 # ftm.mark_bundle_transferred(
#                 #     row_id,
#                 #     status="sent"
#                 # )
#
#             except Exception as e:
#
#                 ftm.mark_bundle_transferred(
#                     row_id,
#                     status="failed",
#                     error=str(e),
#                 )
#
#                 log.log_bundle_event(
#                     env=env,
#                     row_id=row_id,
#                     hiu_id=hiu_id,
#                     consent_artifact_id=row.get(
#                         "consent_artifact_id",
#                         ""
#                     ),
#                     hi_types=row.get(
#                         "hi_type",
#                         ""
#                     ),
#                     event_type="bundle_transferred",
#                     status="failed",
#                     error=str(e),
#                 )
#
#                 return jsonify({
#                     "error": "encryption/transfer failed"
#                 }), 500
#
#         return jsonify({
#             "ok": True
#         }), 200
#
#     elif event_type == "abha.discover_care_context":
#         # Discovery flow -- not implemented yet.
#         return jsonify({"ok": True, "note": "discover_care_context received, not yet wired"}), 200
#
#     else:
#         return jsonify({"ok": True, "note": f"unhandled event type: {event_type}"}), 200
#
#
# if __name__ == "__main__":
#     app.run(port=5000, debug=True)


"""
Webhook server for receiving abha.link_care_context and abha.hip_data_fetch
events, per the abdm-m2-care-context-linking skill's integration blueprint.

Run locally with a tunnel (ngrok/cloudflared) pointed at this during dev:
    python src/webhook_server.py

TODO before trusting this in sandbox/prod: verify Eka's webhook signature
on every incoming request. The skill doesn't specify the exact signature
scheme -- check Eka's console/docs for the header name and verification
method before removing the placeholder check below.
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
import flat_table_manager as ftm
import logging_utils as log
import fhir_builder
import encryption
import eka_client
from config import load_config

app = Flask(__name__)
_config = load_config()  # loaded once at startup -- needs EKA_ENV/EKA_CLIENT_ID/etc set


def _verify_signature(req) -> bool:
    # PLACEHOLDER -- replace with Eka's real signature verification.
    # Do not deploy to prod with this returning True unconditionally.
    return True


@app.route("/webhooks/eka", methods=["POST"])
def handle_webhook():
    if not _verify_signature(request):
        return jsonify({"error": "invalid signature"}), 401

    payload = request.get_json(force=True, silent=True) or {}
    print("\n========== WEBHOOK RECEIVED ==========")
    print(json.dumps(payload, indent=2))
    print("======================================")

    # Save the latest webhook payload
    os.makedirs("data", exist_ok=True)

    with open("data/webhook_last.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    event_type = payload.get("event")
    data = payload.get("data", {})  # real payload nests everything under "data"

    if event_type == "abha.link_care_context":
        care_context_id = data.get("care_context_id")
        status = data.get("status")
        error = data.get("error") or ""

        if not care_context_id:
            return jsonify({
                "error": "missing care_context_id in payload.data"
            }), 400

        try:
            row = ftm.find_row_by_care_context_id(care_context_id)
        except ValueError:
            return jsonify({
                "error": f"unknown care_context_id: {care_context_id}"
            }), 404

        # IMPORTANT:
        # record_id is R001/R002/R003...
        # row_id is P001 (patient ID)
        record_id = row["record_id"]

        ftm.mark_link_webhook_result(
            record_id,
            status=status,
            error=error
        )

        log.log_push_event(
            env=os.environ.get("EKA_ENV", "sandbox"),
            row_id=record_id,
            care_context_id=care_context_id,
            hi_type=row.get("hi_type", ""),
            status=status,
            error=error,
        )

        return jsonify({"ok": True}), 200

    elif event_type == "abha.hip_data_fetch":
        transaction_id = payload.get("transaction_id", "")
        care_contexts = data.get("care_contexts", [])
        key_information = data.get("key_information", {})
        hiu_id = data.get("hip_id", "")  # confirm: docs show hip_id here, not hiu_id

        if not transaction_id:
            return jsonify({"error": "missing transaction_id"}), 400
        if not care_contexts:
            return jsonify({"error": "missing care_contexts"}), 400
        if not key_information:
            return jsonify({"error": "missing key_information"}), 400

        requester_nonce = key_information.get("nonce", "")
        requester_public_key = key_information.get("dh_public_key", {}).get("key_value", "")

        # Real payload's care_contexts is a list of plain ID strings, not
        # objects -- confirmed from the doc you pasted:
        # "care_contexts": ["care_context_1", "care_context_2"]
        for care_context_id in care_contexts:
            try:
                row = ftm.find_row_by_care_context_id(care_context_id)
            except ValueError:
                return jsonify({"error": f"unknown care_context_id: {care_context_id}"}), 404

            record_id = row["record_id"]
            env = os.environ.get("EKA_ENV", "sandbox")

            # HARD GATE -- do not build or touch the bundle before this passes.
            if not ftm.check_consent_before_bundling(record_id):
                log.log_bundle_event(
                    env=env, row_id=row_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_blocked",
                    status="denied", error="consent not granted or care context not linked",
                )
                return jsonify({"error": "consent not granted for this care context"}), 403

            try:
                bundle = fhir_builder.build_bundle(row)
                ftm.mark_bundle_created(record_id)
                log.log_bundle_event(
                    env=env, row_id=row_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_created", status="ok",
                )
            except Exception as e:
                log.log_bundle_event(
                    env=env, row_id=row_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_created",
                    status="failed", error=str(e),
                )
                return jsonify({"error": "bundle build failed"}), 500

            try:
                hip_key_material = encryption.generate_hip_key_material()
                bundle_json = json.dumps(bundle)

                encrypted = encryption.encrypt_fhir_bundle(
                    bundle_json,
                    hip_key_material,
                    requester_nonce,
                    requester_public_key,
                )

                checksum = encryption.calculate_checksum(
                    encrypted
                )

                eka_client.push_on_fetch_response(
                    config=_config,
                    transaction_id=transaction_id,
                    care_context_id=care_context_id,
                    encrypted_content=encrypted,
                    key_information=key_information,
                    checksum=checksum,
                )
                ftm.mark_bundle_transferred(record_id, status="sent")
                log.log_bundle_event(
                    env=env, row_id=record_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_transferred", status="sent",
                )
            except Exception as e:
                ftm.mark_bundle_transferred(row_id, status="failed", error=str(e))
                log.log_bundle_event(
                    env=env, row_id=record_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_transferred",
                    status="failed", error=str(e),
                )
                return jsonify({"error": "encryption/transfer failed"}), 500

        return jsonify({"ok": True}), 200

    elif event_type == "abha.discover_care_context":
        return jsonify({"ok": True, "note": "discover_care_context received, not yet wired"}), 200

    else:
        return jsonify({"ok": True, "note": f"unhandled event type: {event_type}"}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)