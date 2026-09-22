# """
# Webhook server for receiving abha.link_care_context and abha.hip_data_fetch
# events, per the abdm-m2-care-context-linking skill's integration blueprint.
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
# import json
#
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#
# from flask import Flask, request, jsonify
# import flat_table_manager as ftm
# import logging_utils as log
# import fhir_builder
# import encryption
# import eka_client
# from config import load_config
#
# app = Flask(__name__)
# _config = load_config()  # loaded once at startup -- needs EKA_ENV/EKA_CLIENT_ID/etc set
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
#     print("\n========== WEBHOOK RECEIVED ==========")
#     print(json.dumps(payload, indent=2))
#     print("======================================")
#
#     # Save the latest webhook payload
#     os.makedirs("data", exist_ok=True)
#
#     with open("data/webhook_last.json", "w", encoding="utf-8") as f:
#         json.dump(payload, f, indent=2)
#     event_type = payload.get("event")
#     data = payload.get("data", {})  # real payload nests everything under "data"
#
#     if event_type == "abha.link_care_context":
#         care_context_id = data.get("care_context_id")
#         status = data.get("status")
#         error = data.get("error") or ""
#
#         if not care_context_id:
#             return jsonify({
#                 "error": "missing care_context_id in payload.data"
#             }), 400
#
#         try:
#             row = ftm.find_row_by_care_context_id(care_context_id)
#         except ValueError:
#             return jsonify({
#                 "error": f"unknown care_context_id: {care_context_id}"
#             }), 404
#
#         # IMPORTANT:
#         # record_id is R001/R002/R003...
#         # row_id is P001 (patient ID)
#         record_id = row["record_id"]
#
#         ftm.mark_link_webhook_result(
#             record_id,
#             status=status,
#             error=error
#         )
#
#         log.log_push_event(
#             env=os.environ.get("EKA_ENV", "sandbox"),
#             row_id=record_id,
#             care_context_id=care_context_id,
#             hi_type=row.get("hi_type", ""),
#             status=status,
#             error=error,
#         )
#
#         return jsonify({"ok": True}), 200
#
#     elif event_type == "abha.hip_data_fetch":
#         transaction_id = payload.get("transaction_id", "")
#         care_contexts = data.get("care_contexts", [])
#         key_information = data.get("key_information", {})
#         hiu_id = data.get("hip_id", "")  # confirm: docs show hip_id here, not hiu_id
#
#         if not transaction_id:
#             return jsonify({"error": "missing transaction_id"}), 400
#         if not care_contexts:
#             return jsonify({"error": "missing care_contexts"}), 400
#         if not key_information:
#             return jsonify({"error": "missing key_information"}), 400
#
#         requester_nonce = key_information.get("nonce", "")
#         requester_public_key = key_information.get("dh_public_key", {}).get("key_value", "")
#
#         # Real payload's care_contexts is a list of plain ID strings, not
#         # objects -- confirmed from the doc you pasted:
#         # "care_contexts": ["care_context_1", "care_context_2"]
#         for care_context_id in care_contexts:
#             try:
#                 row = ftm.find_row_by_care_context_id(care_context_id)
#             except ValueError:
#                 return jsonify({"error": f"unknown care_context_id: {care_context_id}"}), 404
#
#             record_id = row["record_id"]
#             env = os.environ.get("EKA_ENV", "sandbox")
#
#             # HARD GATE -- do not build or touch the bundle before this passes.
#             if not ftm.check_consent_before_bundling(record_id):
#                 log.log_bundle_event(
#                     env=env, row_id=row_id, hiu_id=hiu_id,
#                     consent_artifact_id=row.get("consent_artifact_id", ""),
#                     hi_types=row.get("hi_type", ""), event_type="bundle_blocked",
#                     status="denied", error="consent not granted or care context not linked",
#                 )
#                 return jsonify({"error": "consent not granted for this care context"}), 403
#
#             try:
#                 bundle = fhir_builder.build_bundle(row)
#                 ftm.mark_bundle_created(record_id)
#                 log.log_bundle_event(
#                     env=env, row_id=row_id, hiu_id=hiu_id,
#                     consent_artifact_id=row.get("consent_artifact_id", ""),
#                     hi_types=row.get("hi_type", ""), event_type="bundle_created", status="ok",
#                 )
#             except Exception as e:
#                 log.log_bundle_event(
#                     env=env, row_id=row_id, hiu_id=hiu_id,
#                     consent_artifact_id=row.get("consent_artifact_id", ""),
#                     hi_types=row.get("hi_type", ""), event_type="bundle_created",
#                     status="failed", error=str(e),
#                 )
#                 return jsonify({"error": "bundle build failed"}), 500
#
#             try:
#                 hip_key_material = encryption.generate_hip_key_material()
#                 bundle_json = json.dumps(bundle)
#
#                 encrypted = encryption.encrypt_fhir_bundle(
#                     bundle_json,
#                     hip_key_material,
#                     requester_nonce,
#                     requester_public_key,
#                 )
#
#                 checksum = encryption.calculate_checksum(
#                     encrypted
#                 )
#
#                 eka_client.push_on_fetch_response(
#                     config=_config,
#                     transaction_id=transaction_id,
#                     care_context_id=care_context_id,
#                     encrypted_content=encrypted,
#                     key_information=key_information,
#                     checksum=checksum,
#                 )
#                 ftm.mark_bundle_transferred(record_id, status="sent")
#                 log.log_bundle_event(
#                     env=env, row_id=record_id, hiu_id=hiu_id,
#                     consent_artifact_id=row.get("consent_artifact_id", ""),
#                     hi_types=row.get("hi_type", ""), event_type="bundle_transferred", status="sent",
#                 )
#             except Exception as e:
#                 ftm.mark_bundle_transferred(row_id, status="failed", error=str(e))
#                 log.log_bundle_event(
#                     env=env, row_id=record_id, hiu_id=hiu_id,
#                     consent_artifact_id=row.get("consent_artifact_id", ""),
#                     hi_types=row.get("hi_type", ""), event_type="bundle_transferred",
#                     status="failed", error=str(e),
#                 )
#                 return jsonify({"error": "encryption/transfer failed"}), 500
#
#         return jsonify({"ok": True}), 200
#
#     elif event_type == "abha.discover_care_context":
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
on every incoming request.
"""
import sys
import os
import json
import encryption

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
import flat_table_manager as ftm
import logging_utils as log
import fhir_builder
import encryption
import eka_client
from config import load_config

from hiu_decrypt import get_hiu_exchange
from encryption import decrypt_incoming_payload

app = Flask(__name__)
_config = load_config()


def _verify_signature(req) -> bool:
    # PLACEHOLDER -- replace with Eka's real signature verification.
    return True


@app.route("/webhooks/eka", methods=["POST"])
def handle_webhook():
    if not _verify_signature(request):
        return jsonify({"error": "invalid signature"}), 401

    payload = request.get_json(force=True, silent=True) or {}
    print("\n========== WEBHOOK RECEIVED ==========")
    print(json.dumps(payload, indent=2))
    print("======================================")

    os.makedirs("data", exist_ok=True)
    with open("data/webhook_last.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    event_type = payload.get("event")
    data = payload.get("data", {})

    if event_type == "abha.link_care_context":
        care_context_id = data.get("care_context_id")
        status = data.get("status")
        error = data.get("error") or ""

        if not care_context_id:
            return jsonify({"error": "missing care_context_id in payload.data"}), 400

        try:
            row = ftm.find_row_by_care_context_id(care_context_id)
        except ValueError:
            return jsonify({"error": f"unknown care_context_id: {care_context_id}"}), 404

        record_id = row["record_id"]
        ftm.mark_link_webhook_result(record_id, status=status, error=error)
        log.log_push_event(
            env=os.environ.get("EKA_ENV", "sandbox"), row_id=record_id,
            care_context_id=care_context_id, hi_type=row.get("hi_type", ""),
            status=status, error=error,
        )
        return jsonify({"ok": True}), 200

    elif event_type == "abha.consent_update":
        print()
        print("========== CONSENT UPDATE ==========")

        consent_data = data.get("data", {})

        status = consent_data.get("status")

        notification = consent_data.get("notification", {})

        consent_request_id = notification.get(
            "consentRequestId"
        )

        consent_artefacts = notification.get(
            "consentArtefacts", {}
        )

        consent_artefact_id = consent_artefacts.get(
            "id"
        )

        print("Consent Request ID :", consent_request_id)
        print("Status             :", status)
        print("Consent Artefact ID:", consent_artefact_id)

        print("====================================")
        print()

        return jsonify({
            "ok": True,
            "event": "abha.consent_update",
            "status": status
        }), 200

    # elif event_type == "abha.hip_data_fetch":
    #     transaction_id = payload.get("transaction_id", "")
    #     care_contexts = data.get("care_contexts", [])
    #     key_information = data.get("key_information", {})
    #
    #     if not transaction_id:
    #         return jsonify({"error": "missing transaction_id"}), 400
    #     if not care_contexts:
    #         return jsonify({"error": "missing care_contexts"}), 400
    #     if not key_information:
    #         return jsonify({"error": "missing key_information"}), 400
    #
    #     requester_nonce = key_information.get("nonce", "")
    #     requester_public_key = key_information.get("dh_public_key", {}).get("key_value", "")
    #     env = os.environ.get("EKA_ENV", "sandbox")
    #
    #     # One call per care context. Each gets its OWN fresh key material --
    #     # simpler and safer than trying to share one ephemeral key across
    #     # multiple care contexts that might (in principle) have different
    #     # hip_id/partner_patient_id headers.
    #     for care_context_id in care_contexts:
    #         try:
    #             row = ftm.find_row_by_care_context_id(care_context_id)
    #         except ValueError:
    #             return jsonify({"error": f"unknown care_context_id: {care_context_id}"}), 404
    #
    #         record_id = row["record_id"]
    #         hiu_id = row.get("hiu_id", "")
    #
    #         # HARD GATE -- do not build or touch the bundle before this passes.
    #         if not ftm.check_consent_before_bundling(record_id):
    #             log.log_bundle_event(
    #                 env=env, row_id=record_id, hiu_id=hiu_id,
    #                 consent_artifact_id=row.get("consent_artifact_id", ""),
    #                 hi_types=row.get("hi_type", ""), event_type="bundle_blocked",
    #                 status="denied", error="consent not granted or care context not linked",
    #             )
    #             return jsonify({"error": f"consent not granted for {care_context_id}"}), 403
    elif event_type == "abha.hip_data_fetch":
        transaction_id = data.get("transaction_id", "")
        care_contexts = data.get("care_contexts", [])
        key_information = data.get("key_information", {})

        if not transaction_id:
            return jsonify({"error": "missing transaction_id"}), 400
        if not care_contexts:
            return jsonify({"error": "missing care_contexts"}), 400
        if not key_information:
            return jsonify({"error": "missing key_information"}), 400

        requester_nonce = key_information.get("nonce", "")
        requester_public_key = key_information.get("dh_public_key", {}).get("key_value", "")
        env = os.environ.get("EKA_ENV", "sandbox")

        # One call per care context. Each gets its OWN fresh key material --
        # simpler and safer than trying to share one ephemeral key across
        # multiple care contexts that might (in principle) have different
        # hip_id/partner_patient_id headers.
        for care_context_id in care_contexts:
            try:
                row = ftm.find_row_by_care_context_id(care_context_id)
            except ValueError:
                return jsonify({"error": f"unknown care_context_id: {care_context_id}"}), 404

            record_id = row["record_id"]

            # Per Eka's own docs (getting-started page): "When an HIU
            # requests data for a linked care context (after the user
            # grants consent), you receive the abha.hip_data_fetch
            # webhook." Eka's platform guarantees consent was already
            # verified upstream before this webhook is ever sent -- so
            # its arrival IS the confirmation, not something we should
            # require to already be set locally beforehand.
            #
            # transaction_id is used as the consent_artifact_id here as
            # the best available audit reference -- the real payload
            # doesn't appear to carry an explicit consent artifact ID
            # (only transaction_id, care_contexts, key_information were
            # confirmed). If Eka's payload does include one under a
            # different field name, use that instead.
            if row.get("consent_status") != "granted":
                ftm.set_consent(record_id, consent_status="granted",
                                consent_artifact_id=transaction_id,
                                hiu_id=row.get("hiu_id", ""))
                row = ftm.get_row(record_id)

            hiu_id = row.get("hiu_id", "")

            # Still checked, now as a safety net rather than a real
            # precondition -- should always pass at this point given the
            # auto-grant above, unless link_status somehow isn't LINKED.
            if not ftm.check_consent_before_bundling(record_id):
                log.log_bundle_event(
                    env=env, row_id=record_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_blocked",
                    status="denied", error="link_status not LINKED despite a data-fetch request -- unexpected",
                )
                return jsonify({"error": f"care context not in LINKED state: {care_context_id}"}), 403

            try:
                bundle = fhir_builder.build_bundle(row)
                bundle_json = json.dumps(bundle)
                # checksum on the PLAINTEXT, computed BEFORE encryption --
                # a checksum of the ciphertext would be meaningless to the
                # HIU, who only ever sees the ciphertext + this checksum.
                checksum = encryption.calculate_checksum(bundle_json)
                ftm.mark_bundle_created(record_id)
                log.log_bundle_event(
                    env=env, row_id=record_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_created", status="ok",
                )
            except Exception as e:
                log.log_bundle_event(
                    env=env, row_id=record_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_created",
                    status="failed", error=str(e),
                )
                return jsonify({"error": "bundle build failed"}), 500

            try:
                hip_key_material = encryption.generate_hip_key_material()
                encrypted = encryption.encrypt_fhir_bundle(
                    bundle_json, hip_key_material, requester_nonce, requester_public_key,
                )
                eka_client.push_on_fetch_response(
                    _config, row, transaction_id, care_context_id, checksum, encrypted, hip_key_material,
                )
                ftm.mark_bundle_transferred(record_id, status="sent")
                log.log_bundle_event(
                    env=env, row_id=record_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_transferred", status="sent",
                )
            except Exception as e:
                ftm.mark_bundle_transferred(record_id, status="failed", error=str(e))
                log.log_bundle_event(
                    env=env, row_id=record_id, hiu_id=hiu_id,
                    consent_artifact_id=row.get("consent_artifact_id", ""),
                    hi_types=row.get("hi_type", ""), event_type="bundle_transferred",
                    status="failed", error=str(e),
                )
                return jsonify({"error": "encryption/transfer failed"}), 500

        return jsonify({"ok": True}), 200

    # elif event_type == "abha.hiu_data_push":
    #
    #     print()
    #     print("==============================================")
    #     print("HIU DATA PUSH RECEIVED")
    #     print("==============================================")
    #     print()
    #
    #     data = payload.get("data", {})
    #
    #     if not data:
    #         return jsonify({"error": "missing data"}), 400
    #
    #     consent_id = data.get("consent_id", "")
    #     transaction_id = data.get("transaction_id", "")
    #
    #     entries = data.get("entries", [])
    #     key_information = data.get("key_information", {})
    #
    #     if not consent_id:
    #         return jsonify({"error": "missing consent_id"}), 400
    #
    #     if not transaction_id:
    #         return jsonify({"error": "missing transaction_id"}), 400
    #
    #     if not entries:
    #         return jsonify({"error": "missing entries"}), 400
    #
    #     if not key_information:
    #         return jsonify({"error": "missing key_information"}), 400
    #
    #     # --------------------------------------------------------
    #     # HIP key material
    #     # --------------------------------------------------------
    #
    #     hip_nonce = key_information.get("nonce", "")
    #
    #     hip_public_key = (
    #         key_information
    #         .get("dh_public_key", {})
    #         .get("key_value", "")
    #     )
    #
    #     if not hip_nonce:
    #         return jsonify({"error": "missing HIP nonce"}), 400
    #
    #     if not hip_public_key:
    #         return jsonify({"error": "missing HIP public key"}), 400
    #
    #     print("Consent ID      :", consent_id)
    #     print("Transaction ID  :", transaction_id)
    #     print("ABHA Address    :", data.get("abha_address"))
    #     print("HIP ID          :", data.get("hip_id"))
    #     print()
    #
    #     print("Number of entries:", len(entries))
    #     print()
    #
    #     # --------------------------------------------------------
    #     # IMPORTANT
    #     # --------------------------------------------------------
    #     #
    #     # You must retrieve the HIU key material that was generated
    #     # when the HIU initiated this data-fetch request.
    #     #
    #     # DO NOT generate a new HIU key here.
    #     #
    #     # The private key from the original exchange is required.
    #     #
    #     # --------------------------------------------------------
    #
    #     hiu_key_material = load_hiu_key_material(transaction_id)
    #
    #     if hiu_key_material is None:
    #         print("ERROR: HIU key material not found")
    #         return jsonify({
    #             "error": "HIU key material not found",
    #             "transaction_id": transaction_id
    #         }), 500
    #
    #     # --------------------------------------------------------
    #     # Process every care-context entry
    #     # --------------------------------------------------------
    #
    #     for entry in entries:
    #
    #         care_context_id = entry.get(
    #             "care_context_id",
    #             ""
    #         )
    #
    #         encrypted_content = entry.get(
    #             "content",
    #             ""
    #         )
    #
    #         checksum = entry.get(
    #             "checksum",
    #             ""
    #         )
    #
    #         media = entry.get(
    #             "media",
    #             ""
    #         )
    #
    #         print("----------------------------------------------")
    #         print("Care Context :", care_context_id)
    #         print("Media        :", media)
    #         print("Checksum     :", checksum)
    #         print(
    #             "Encrypted length:",
    #             len(encrypted_content)
    #         )
    #         print()
    #
    #         if not encrypted_content:
    #             print("ERROR: encrypted content missing")
    #             continue
    #
    #         # ----------------------------------------------------
    #         # DECRYPT
    #         # ----------------------------------------------------
    #
    #         try:
    #
    #             plaintext = hiu_decryption.decrypt_fhir_data(
    #                 encrypted_content=encrypted_content,
    #                 hiu_key_material=hiu_key_material,
    #                 hip_nonce=hip_nonce,
    #                 hip_x509_public_key=hip_public_key,
    #             )
    #
    #         except Exception as e:
    #
    #             print("DECRYPTION FAILED")
    #             print(str(e))
    #
    #             return jsonify({
    #                 "error": "FHIR decryption failed"
    #             }), 500
    #
    #         print("DECRYPTION SUCCESS")
    #         print()
    #
    #         # ----------------------------------------------------
    #         # CHECKSUM
    #         # ----------------------------------------------------
    #
    #         if checksum:
    #
    #             valid = hiu_decryption.verify_checksum(
    #                 plaintext,
    #                 checksum
    #             )
    #
    #             if not valid:
    #                 print("CHECKSUM FAILED")
    #
    #                 return jsonify({
    #                     "error": "FHIR checksum verification failed"
    #                 }), 500
    #
    #             print("CHECKSUM VERIFIED")
    #             print()
    #
    #         # ----------------------------------------------------
    #         # Parse FHIR
    #         # ----------------------------------------------------
    #
    #         try:
    #
    #             fhir_bundle = json.loads(
    #                 plaintext
    #             )
    #
    #         except json.JSONDecodeError:
    #
    #             print("ERROR: decrypted content is not valid JSON")
    #
    #             return jsonify({
    #                 "error": "decrypted content is not valid JSON"
    #             }), 500
    #
    #         print("FHIR RESOURCE TYPE:")
    #         print(
    #             fhir_bundle.get(
    #                 "resourceType"
    #             )
    #         )
    #
    #         print()
    #         print("FHIR BUNDLE RECEIVED SUCCESSFULLY")
    #         print("----------------------------------------------")
    #         print(
    #             json.dumps(
    #                 fhir_bundle,
    #                 indent=2
    #             )
    #         )
    #         print()
    #
    #         # ----------------------------------------------------
    #         # TODO:
    #         # Save fhir_bundle into your HIU database.
    #         # ----------------------------------------------------
    #
    #     return jsonify({
    #         "ok": True
    #     }), 200

    # elif event_type == "abha.hiu_data_push":
    #
    #     print()
    #     print("==============================================")
    #     print("HIU DATA PUSH RECEIVED")
    #     print("==============================================")
    #
    #     data = payload.get("data", {})
    #
    #     if not data:
    #         return jsonify({"error": "missing data"}), 400
    #
    #     print("Webhook Transaction ID :", payload.get("transaction_id"))
    #     print("Data Transaction ID    :", data.get("transaction_id"))
    #     print("Consent ID             :", data.get("consent_id"))
    #     print("ABHA Address           :", data.get("abha_address"))
    #     print("HIP ID                 :", data.get("hip_id"))
    #
    #     entries = data.get("entries", [])
    #
    #     print("Number of entries      :", len(entries))
    #     print()
    #
    #     key_information = data.get("key_information", {})
    #
    #     print("Key information")
    #     print("----------------------------------------------")
    #     print("Crypto algorithm       :", key_information.get("crypto_alg"))
    #     print("Curve                  :", key_information.get("curve"))
    #     print("Nonce                  :", key_information.get("nonce"))
    #
    #     dh_public_key = key_information.get(
    #         "dh_public_key", {}
    #     )
    #
    #     print("Public key expiry      :", dh_public_key.get("expiry"))
    #     print("Public key present     :", bool(dh_public_key.get("key_value")))
    #     print()
    #
    #     for index, entry in enumerate(entries, start=1):
    #         print("----------------------------------------------")
    #         print("Entry", index)
    #         print("----------------------------------------------")
    #
    #         print(
    #             "Care Context :",
    #             entry.get("care_context_id")
    #         )
    #
    #         print(
    #             "Media        :",
    #             entry.get("media")
    #         )
    #
    #         print(
    #             "Checksum     :",
    #             entry.get("checksum")
    #         )
    #
    #         encrypted_content = entry.get("content", "")
    #
    #         print(
    #             "Encrypted length:",
    #             len(encrypted_content)
    #         )
    #
    #     print()
    #     print("==============================================")
    #     print("HIU DATA PUSH RECEIVED SUCCESSFULLY")
    #     print("==============================================")
    #     print()
    #
    #     return jsonify({"ok": True}), 200

    # elif event_type == "abha.hiu_data_push":
    #
    #     print()
    #     print("==============================================")
    #     print("HIU DATA PUSH RECEIVED")
    #     print("==============================================")
    #
    #     data = payload.get("data", {})
    #
    #     if not data:
    #         return jsonify({"error": "missing data"}), 400
    #
    #     webhook_transaction_id = payload.get("transaction_id", "")
    #     data_transaction_id = data.get("transaction_id", "")
    #     consent_id = data.get("consent_id", "")
    #     abha_address = data.get("abha_address", "")
    #     hip_id = data.get("hip_id", "")
    #
    #     print("Webhook Transaction ID :", webhook_transaction_id)
    #     print("Data Transaction ID    :", data_transaction_id)
    #     print("Consent ID             :", consent_id)
    #     print("ABHA Address           :", abha_address)
    #     print("HIP ID                 :", hip_id)
    #
    #     entries = data.get("entries", [])
    #
    #     if not entries:
    #         return jsonify({"error": "missing entries"}), 400
    #
    #     key_information = data.get("key_information", {})
    #
    #     print()
    #     print("Key information")
    #     print("----------------------------------------------")
    #     print("Crypto algorithm :", key_information.get("crypto_alg"))
    #     print("Curve            :", key_information.get("curve"))
    #     print("Nonce            :", key_information.get("nonce"))
    #
    #     dh_public_key = key_information.get(
    #         "dh_public_key", {}
    #     )
    #
    #     sender_public_key = dh_public_key.get(
    #         "key_value", ""
    #     )
    #
    #     print(
    #         "Public key present:",
    #         bool(sender_public_key)
    #     )
    #
    #     print()
    #
    #     # for index, entry in enumerate(entries, start=1):
    #     #     care_context_id = entry.get(
    #     #         "care_context_id", ""
    #     #     )
    #     #
    #     #     checksum = entry.get(
    #     #         "checksum", ""
    #     #     )
    #     #
    #     #     encrypted_content = entry.get(
    #     #         "content", ""
    #     #     )
    #     #
    #     #     media = entry.get(
    #     #         "media", ""
    #     #     )
    #     #
    #     #     print("----------------------------------------------")
    #     #     print("Entry", index)
    #     #     print("----------------------------------------------")
    #     #
    #     #     print("Care Context       :", care_context_id)
    #     #     print("Media              :", media)
    #     #     print("Checksum           :", checksum)
    #     #     print(
    #     #         "Encrypted length   :",
    #     #         len(encrypted_content)
    #     #     )
    #     #
    #     #     # ------------------------------------------------
    #     #     # DO NOT DECRYPT YET
    #     #     # ------------------------------------------------
    #     #     #
    #     #     # We need the HIU private key corresponding to
    #     #     # the HIU public key used for this exchange.
    #     #     #
    #     #     # Once that private key is available, the
    #     #     # following information is required:
    #     #     #
    #     #     #   encrypted_content
    #     #     #   HIP nonce
    #     #     #   HIP public key
    #     #     #   HIU nonce
    #     #     #   HIU private key
    #     #     #
    #     #     # ------------------------------------------------
    #     #
    #     #     print()
    #     #     print("Decryption inputs received:")
    #     #     print("----------------------------------------------")
    #     #     print(
    #     #         "Encrypted content :",
    #     #         bool(encrypted_content)
    #     #     )
    #     #     print(
    #     #         "HIP public key    :",
    #     #         bool(sender_public_key)
    #     #     )
    #     #     print(
    #     #         "HIP nonce         :",
    #     #         bool(key_information.get("nonce"))
    #     #     )
    #     #     print(
    #     #         "Checksum          :",
    #     #         bool(checksum)
    #     #     )
    #     #
    #     # print()
    #     # print("==============================================")
    #     # print("HIU DATA PUSH RECEIVED SUCCESSFULLY")
    #     # print("==============================================")
    #     # print()
    #     #
    #     # return jsonify({"ok": True}), 200
    #
    #     for index, entry in enumerate(entries, start=1):
    #
    #         care_context_id = entry.get("care_context_id", "")
    #         checksum = entry.get("checksum", "")
    #         encrypted_content = entry.get("content", "")
    #         media = entry.get("media", "")
    #
    #         print("----------------------------------------------")
    #         print("Entry", index)
    #         print("----------------------------------------------")
    #
    #         print("Care Context       :", care_context_id)
    #         print("Media              :", media)
    #         print("Checksum           :", checksum)
    #         print("Encrypted length   :", len(encrypted_content))
    #
    #         # -----------------------------------------------
    #         # HIP information received in webhook
    #         # -----------------------------------------------
    #
    #         sender_nonce = key_information.get("nonce")
    #
    #         sender_public_key = (
    #             key_information
    #             .get("dh_public_key", {})
    #             .get("key_value", "")
    #         )
    #
    #         # -----------------------------------------------
    #         # Get OUR HIU key material
    #         # -----------------------------------------------
    #
    #         hiu_key_material = get_hiu_exchange()
    #
    #         # -----------------------------------------------
    #         # DECRYPT
    #         # -----------------------------------------------
    #
    #         try:
    #
    #             decrypted_fhir = decrypt_incoming_payload(
    #                 encrypted_data=encrypted_content,
    #                 own_key_material=hiu_key_material,
    #                 sender_nonce=sender_nonce,
    #                 sender_x509_public_key=sender_public_key,
    #             )
    #
    #             print()
    #             print("==============================================")
    #             print("FHIR DECRYPTED SUCCESSFULLY")
    #             print("==============================================")
    #
    #             print(decrypted_fhir)
    #
    #             # -------------------------------------------
    #             # Parse FHIR JSON
    #             # -------------------------------------------
    #
    #             fhir_bundle = json.loads(decrypted_fhir)
    #
    #             print()
    #             print("FHIR Resource Type:")
    #             print(fhir_bundle.get("resourceType"))
    #
    #             print()
    #             print("FHIR Bundle:")
    #             print(json.dumps(fhir_bundle, indent=2))
    #
    #         except Exception as e:
    #
    #             print()
    #             print("==============================================")
    #             print("FHIR DECRYPTION FAILED")
    #             print("==============================================")
    #
    #             print(type(e).__name__)
    #             print(str(e))

    elif event_type == "abha.hiu_data_push":
        data = payload.get("data", {})
        entries = data.get("entries", [])
        key_information = data.get("key_information", {})
        sender_nonce = key_information.get("nonce")
        sender_public_key = key_information.get("dh_public_key", {}).get("key_value", "")

        hiu_key_material = get_hiu_exchange()

        for entry in entries:
            encrypted_content = entry.get("content", "")
            decrypted_fhir = decrypt_incoming_payload(
                encrypted_data=encrypted_content,
                own_key_material=hiu_key_material,
                sender_nonce=sender_nonce,
                sender_x509_public_key=sender_public_key,
            )
            fhir_bundle = json.loads(decrypted_fhir)
            # print(json.dumps(fhir_bundle, indent=2))
            care_context_id = entry.get("care_context_id", "unknown")
            os.makedirs("decrypt-hiu", exist_ok=True)
            filename = f"decrypt-hiu/{care_context_id}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(fhir_bundle, f, indent=2)
            print(f"Saved decrypted bundle to {filename}")

        return jsonify({"ok": True}), 200



    elif event_type == "abha.discover_care_context":
        return jsonify({"ok": True, "note": "discover_care_context received, not yet wired"}), 200

    else:
        return jsonify({"ok": True, "note": f"unhandled event type: {event_type}"}), 200


# if __name__ == "__main__":
#     app.run(port=5000, debug=True)

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        from hiu_decrypt import create_hiu_exchange
        import eka_client as _eka_client

        _hiu_key_material = create_hiu_exchange()
        _eka_client.update_hiu_keyset(_config, _hiu_key_material)
        print("HIU keyset registered.")

    app.run(port=5000, debug=True)