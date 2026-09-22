import sys
import os
import json
import traceback

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

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


# ============================================================
# SIGNATURE VERIFICATION
# ============================================================

def _verify_signature(req) -> bool:
    """
    TODO:
    Replace with Eka's actual webhook signature verification.
    """
    return True


# ============================================================
# SAVE WEBHOOK PAYLOAD
# ============================================================

def save_webhook_payload(payload):
    os.makedirs("data", exist_ok=True)

    with open(
        "data/webhook_last.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            indent=2,
        )


# ============================================================
# MAIN WEBHOOK
# ============================================================

@app.route(
    "/webhooks/eka",
    methods=["POST"],
)
def handle_webhook():

    if not _verify_signature(request):
        return jsonify({
            "error": "invalid signature"
        }), 401


    payload = request.get_json(
        force=True,
        silent=True,
    ) or {}


    print()
    print("=" * 70)
    print("EKA WEBHOOK RECEIVED")
    print("=" * 70)

    print(
        json.dumps(
            payload,
            indent=2,
        )
    )

    print("=" * 70)
    print()


    save_webhook_payload(payload)


    event_type = payload.get(
        "event",
        ""
    )

    data = payload.get(
        "data",
        {}
    )


    print("EVENT:", event_type)


    # ========================================================
    # LINK CARE CONTEXT
    # ========================================================

    if event_type == "abha.link_care_context":

        return handle_link_care_context(data)


    # ========================================================
    # CONSENT UPDATE
    # ========================================================

    if event_type == "abha.consent_update":

        return handle_consent_update(data)


    # ========================================================
    # HIP DATA FETCH
    # ========================================================

    if event_type == "abha.hip_data_fetch":

        return handle_hip_data_fetch(data)


    # ========================================================
    # HIU DATA PUSH
    # ========================================================

    if event_type == "abha.hiu_data_push":

        return handle_hiu_data_push(data)


    # ========================================================
    # DISCOVER CARE CONTEXT
    # ========================================================

    if event_type == "abha.discover_care_context":

        print(
            "Discover care context received."
        )

        return jsonify({
            "ok": True,
            "event": event_type,
        }), 200


    # ========================================================
    # UNKNOWN EVENT
    # ========================================================

    print(
        "Unhandled event:",
        event_type,
    )

    return jsonify({
        "ok": True,
        "note": f"unhandled event type: {event_type}",
    }), 200


# ============================================================
# LINK CARE CONTEXT
# ============================================================

def handle_link_care_context(data):

    care_context_id = data.get(
        "care_context_id"
    )

    status = data.get(
        "status"
    )

    error = data.get(
        "error"
    ) or ""


    if not care_context_id:

        return jsonify({
            "error": "missing care_context_id"
        }), 400


    print()
    print("=" * 70)
    print("CARE CONTEXT LINK")
    print("=" * 70)

    print("Care Context :", care_context_id)
    print("Status       :", status)
    print("Error        :", error)

    print("=" * 70)


    try:

        row = ftm.find_row_by_care_context_id(
            care_context_id
        )

    except ValueError:

        return jsonify({
            "error": (
                f"unknown care_context_id: "
                f"{care_context_id}"
            )
        }), 404


    record_id = row["record_id"]


    ftm.mark_link_webhook_result(
        record_id,
        status=status,
        error=error,
    )


    log.log_push_event(
        env=os.environ.get(
            "EKA_ENV",
            "sandbox",
        ),

        row_id=record_id,

        care_context_id=care_context_id,

        hi_type=row.get(
            "hi_type",
            "",
        ),

        status=status,

        error=error,
    )


    return jsonify({
        "ok": True
    }), 200


# ============================================================
# CONSENT UPDATE
# ============================================================

def handle_consent_update(data):

    print()
    print("=" * 70)
    print("CONSENT UPDATE")
    print("=" * 70)


    consent_data = data.get(
        "data",
        {}
    )


    status = consent_data.get(
        "status"
    )


    notification = consent_data.get(
        "notification",
        {}
    )


    consent_request_id = notification.get(
        "consentRequestId"
    )


    consent_artefacts = notification.get(
        "consentArtefacts",
        {}
    )


    consent_artifact_id = consent_artefacts.get(
        "id"
    )


    print(
        "Consent Request ID :",
        consent_request_id,
    )

    print(
        "Status             :",
        status,
    )

    print(
        "Consent Artifact ID:",
        consent_artifact_id,
    )

    print("=" * 70)


    return jsonify({
        "ok": True,
        "event": "abha.consent_update",
        "status": status,
    }), 200


# ============================================================
# HIP DATA FETCH
# ============================================================

def handle_hip_data_fetch(data):

    print()
    print("=" * 70)
    print("HIP DATA FETCH")
    print("=" * 70)


    transaction_id = data.get(
        "transaction_id",
        "",
    )


    care_contexts = data.get(
        "care_contexts",
        [],
    )


    key_information = data.get(
        "key_information",
        {},
    )


    print(
        "Transaction ID:",
        transaction_id,
    )

    print(
        "Care Contexts:",
        care_contexts,
    )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not transaction_id:

        return jsonify({
            "error": "missing transaction_id"
        }), 400


    if not care_contexts:

        return jsonify({
            "error": "missing care_contexts"
        }), 400


    if not key_information:

        return jsonify({
            "error": "missing key_information"
        }), 400


    requester_nonce = key_information.get(
        "nonce",
        ""
    )


    requester_public_key = (
        key_information
        .get(
            "dh_public_key",
            {}
        )
        .get(
            "key_value",
            ""
        )
    )


    if not requester_nonce:

        return jsonify({
            "error": "missing requester nonce"
        }), 400


    if not requester_public_key:

        return jsonify({
            "error": "missing requester public key"
        }), 400


    env = os.environ.get(
        "EKA_ENV",
        "sandbox",
    )


    # ========================================================
    # PROCESS EACH CARE CONTEXT
    # ========================================================

    for care_context_id in care_contexts:

        print()
        print("#" * 70)
        print(
            "PROCESSING CARE CONTEXT:",
            care_context_id,
        )
        print("#" * 70)


        # ----------------------------------------------------
        # Find row
        # ----------------------------------------------------

        try:

            row = ftm.find_row_by_care_context_id(
                care_context_id
            )

        except ValueError:

            print(
                "Unknown care context:",
                care_context_id,
            )

            return jsonify({
                "error": (
                    f"unknown care_context_id: "
                    f"{care_context_id}"
                )
            }), 404


        record_id = row["record_id"]

        hiu_id = row.get(
            "hiu_id",
            "",
        )


        print(
            "Record ID      :",
            record_id,
        )

        print(
            "HI Type        :",
            row.get(
                "hi_type",
                "",
            ),
        )

        print(
            "Display        :",
            row.get(
                "display",
                "",
            ),
        )

        print(
            "Link Status    :",
            row.get(
                "link_status",
                "",
            ),
        )

        print(
            "Consent Status :",
            row.get(
                "consent_status",
                "",
            ),
        )


        # ====================================================
        # SYNCHRONIZE CONSENT
        # ====================================================

        if row.get(
            "consent_status"
        ) != "granted":

            ftm.set_consent(
                record_id,
                consent_status="granted",
                consent_artifact_id=transaction_id,
                hiu_id=hiu_id,
            )

            row = ftm.get_row(
                record_id
            )


        # ====================================================
        # CHECK LINK STATUS
        # ====================================================

        if not ftm.check_consent_before_bundling(
            record_id
        ):

            error_message = (
                "care context is not LINKED"
            )


            print(
                "ERROR:",
                error_message,
            )


            log.log_bundle_event(
                env=env,
                row_id=record_id,
                hiu_id=hiu_id,
                consent_artifact_id=row.get(
                    "consent_artifact_id",
                    "",
                ),
                hi_types=row.get(
                    "hi_type",
                    "",
                ),
                event_type="bundle_blocked",
                status="denied",
                error=error_message,
            )


            return jsonify({
                "error": error_message,
                "care_context_id": care_context_id,
            }), 403


        # ====================================================
        # BUILD FHIR
        # ====================================================

        try:

            print()
            print("BUILDING FHIR BUNDLE")


            bundle = fhir_builder.build_bundle(
                row
            )


            bundle_json = json.dumps(
                bundle
            )


            print(
                "FHIR resourceType:",
                bundle.get(
                    "resourceType"
                ),
            )


            print(
                "FHIR Bundle size:",
                len(bundle_json),
            )


            # ------------------------------------------------
            # Save plaintext bundle for debugging
            # ------------------------------------------------

            os.makedirs(
                "bundles",
                exist_ok=True,
            )


            debug_filename = (
                f"bundles/"
                f"{care_context_id}.json"
            )


            with open(
                debug_filename,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    bundle,
                    f,
                    indent=2,
                )


            print(
                "Debug bundle saved:",
                debug_filename,
            )


            # ------------------------------------------------
            # Checksum
            # ------------------------------------------------

            checksum = encryption.calculate_checksum(
                bundle_json
            )


            print(
                "Checksum:",
                checksum,
            )


            ftm.mark_bundle_created(
                record_id
            )


            log.log_bundle_event(
                env=env,
                row_id=record_id,
                hiu_id=hiu_id,
                consent_artifact_id=row.get(
                    "consent_artifact_id",
                    "",
                ),
                hi_types=row.get(
                    "hi_type",
                    "",
                ),
                event_type="bundle_created",
                status="ok",
            )


        except Exception as e:

            print()
            print("FHIR BUNDLE BUILD FAILED")
            print(str(e))

            traceback.print_exc()


            log.log_bundle_event(
                env=env,
                row_id=record_id,
                hiu_id=hiu_id,
                consent_artifact_id=row.get(
                    "consent_artifact_id",
                    "",
                ),
                hi_types=row.get(
                    "hi_type",
                    "",
                ),
                event_type="bundle_created",
                status="failed",
                error=str(e),
            )


            return jsonify({
                "error": "bundle build failed",
                "care_context_id": care_context_id,
            }), 500


        # ====================================================
        # ENCRYPT
        # ====================================================

        try:

            print()
            print("GENERATING HIP KEY MATERIAL")


            hip_key_material = (
                encryption.generate_hip_key_material()
            )


            print(
                "ENCRYPTING FHIR BUNDLE"
            )


            encrypted = encryption.encrypt_fhir_bundle(
                bundle_json,
                hip_key_material,
                requester_nonce,
                requester_public_key,
            )


            print(
                "Encryption successful."
            )

            print(
                "Encrypted size:",
                len(encrypted),
            )


        except Exception as e:

            print()
            print("FHIR ENCRYPTION FAILED")
            print(str(e))

            traceback.print_exc()


            ftm.mark_bundle_transferred(
                record_id,
                status="failed",
                error=str(e),
            )


            return jsonify({
                "error": "encryption failed",
                "care_context_id": care_context_id,
            }), 500


        # ====================================================
        # SEND TO EKA
        # ====================================================

        try:

            print()
            print("=" * 70)
            print("SENDING DATA-ON-FETCH TO EKA")
            print("=" * 70)

            print(
                "Care Context :",
                care_context_id,
            )

            print(
                "Transaction  :",
                transaction_id,
            )

            print(
                "Record ID    :",
                record_id,
            )

            print(
                "HI Type      :",
                row.get(
                    "hi_type",
                    "",
                ),
            )

            print(
                "Checksum     :",
                checksum,
            )

            print(
                "Encrypted size:",
                len(encrypted),
            )


            response = eka_client.push_on_fetch_response(
                _config,
                row,
                transaction_id,
                care_context_id,
                checksum,
                encrypted,
                hip_key_material,
            )


            # ------------------------------------------------
            # eka_client already guarantees:
            #
            # 200 / 202 = success
            # anything else = exception
            # ------------------------------------------------

            print()
            print(
                "EKA DATA-ON-FETCH ACCEPTED"
            )

            print(
                "HTTP Status:",
                response.status_code,
            )


            if response.text:

                print(
                    "Eka Response:"
                )

                print(
                    response.text
                )


            # ------------------------------------------------
            # Only now mark as sent
            # ------------------------------------------------

            ftm.mark_bundle_transferred(
                record_id,
                status="sent",
            )


            log.log_bundle_event(
                env=env,
                row_id=record_id,
                hiu_id=hiu_id,
                consent_artifact_id=row.get(
                    "consent_artifact_id",
                    "",
                ),
                hi_types=row.get(
                    "hi_type",
                    "",
                ),
                event_type="bundle_transferred",
                status="sent",
            )


            print()
            print(
                "BUNDLE TRANSFER STATUS = SENT"
            )
            print("=" * 70)


        except Exception as e:

            print()
            print("=" * 70)
            print(
                "DATA-ON-FETCH FAILED"
            )
            print("=" * 70)

            print(
                type(e).__name__
            )

            print(
                str(e)
            )

            traceback.print_exc()


            ftm.mark_bundle_transferred(
                record_id,
                status="failed",
                error=str(e),
            )


            log.log_bundle_event(
                env=env,
                row_id=record_id,
                hiu_id=hiu_id,
                consent_artifact_id=row.get(
                    "consent_artifact_id",
                    "",
                ),
                hi_types=row.get(
                    "hi_type",
                    "",
                ),
                event_type="bundle_transferred",
                status="failed",
                error=str(e),
            )


            return jsonify({
                "error": "data-on-fetch failed",
                "care_context_id": care_context_id,
            }), 500


    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print("=" * 70)
    print("ALL CARE CONTEXTS PROCESSED")
    print("=" * 70)


    return jsonify({
        "ok": True,
        "transaction_id": transaction_id,
        "care_contexts": care_contexts,
    }), 200


# ============================================================
# HIU DATA PUSH
# ============================================================

def handle_hiu_data_push(data):

    print()
    print("=" * 70)
    print("HIU DATA PUSH RECEIVED")
    print("=" * 70)


    entries = data.get(
        "entries",
        [],
    )


    key_information = data.get(
        "key_information",
        {},
    )


    sender_nonce = key_information.get(
        "nonce"
    )


    sender_public_key = (
        key_information
        .get(
            "dh_public_key",
            {}
        )
        .get(
            "key_value",
            ""
        )
    )


    if not entries:

        return jsonify({
            "error": "missing entries"
        }), 400


    if not sender_nonce:

        return jsonify({
            "error": "missing sender nonce"
        }), 400


    if not sender_public_key:

        return jsonify({
            "error": "missing sender public key"
        }), 400


    hiu_key_material = get_hiu_exchange()


    for entry in entries:

        care_context_id = entry.get(
            "care_context_id",
            "unknown",
        )


        encrypted_content = entry.get(
            "content",
            "",
        )


        if not encrypted_content:

            print(
                "Empty content:",
                care_context_id,
            )

            continue


        try:

            decrypted_fhir = decrypt_incoming_payload(
                encrypted_data=encrypted_content,
                own_key_material=hiu_key_material,
                sender_nonce=sender_nonce,
                sender_x509_public_key=sender_public_key,
            )


            fhir_bundle = json.loads(
                decrypted_fhir
            )


        except Exception as e:

            print(
                "FHIR decryption failed:"
            )

            print(
                str(e)
            )

            traceback.print_exc()


            return jsonify({
                "error": "FHIR decryption failed",
                "care_context_id": care_context_id,
            }), 500


        os.makedirs(
            "decrypt-hiu",
            exist_ok=True,
        )


        filename = (
            f"decrypt-hiu/"
            f"{care_context_id}.json"
        )


        with open(
            filename,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                fhir_bundle,
                f,
                indent=2,
            )


        print(
            "FHIR Resource Type:",
            fhir_bundle.get(
                "resourceType"
            ),
        )


        print(
            "Saved decrypted bundle:",
            filename,
        )


    return jsonify({
        "ok": True
    }), 200


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    if (
        os.environ.get(
            "WERKZEUG_RUN_MAIN"
        ) == "true"
        or not app.debug
    ):

        from hiu_decrypt import create_hiu_exchange


        _hiu_key_material = (
            create_hiu_exchange()
        )


        eka_client.update_hiu_keyset(
            _config,
            _hiu_key_material,
        )


        print(
            "HIU keyset registered."
        )


    app.run(
        port=5000,
        debug=True,
    )