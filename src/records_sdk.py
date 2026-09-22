# """
# Eka Care ABDM Records SDK launcher.
#
# This replaces the old manual M3 consent flow:
#
#     CREATE CONSENT
#         ↓
#     LIST CONSENT
#         ↓
#     APPROVE CONSENT
#         ↓
#     WEBHOOKS
#
# With Eka Records SDK:
#
#     Doctor opens patient
#         ↓
#     Eka Records SDK
#         ↓
#     Request Consent
#         ↓
#     Patient approves in PHR app
#         ↓
#     View
#         ↓
#     Our /records page
#         ↓
#     Consent Details / Retrieve Health Records
# """
#
# import os
# import sys
# import argparse
# from urllib.parse import urlencode
#
# from flask import Flask, jsonify, redirect, request
# from dotenv import load_dotenv
#
#
# # ============================================================
# # ENVIRONMENT
# # ============================================================
#
# load_dotenv()
#
#
# # ============================================================
# # PROJECT PATH
# # ============================================================
#
# PROJECT_ROOT = os.path.dirname(
#     os.path.dirname(os.path.abspath(__file__))
# )
#
# sys.path.insert(0, PROJECT_ROOT)
# sys.path.insert(
#     0,
#     os.path.join(PROJECT_ROOT, "src")
# )
#
#
# # ============================================================
# # PROJECT IMPORTS
# # ============================================================
#
# import flat_table_manager as ftm
#
# from config import load_config
# from eka_client import get_auth_token
#
#
# # ============================================================
# # FLASK APP
# # ============================================================
#
# app = Flask(__name__)
#
#
# # ============================================================
# # CONFIGURATION
# # ============================================================
#
# # Eka staging Records SDK.
# #
# # Change this to the production URL when Eka gives you
# # the production SDK URL.
# EKA_RECORDS_SDK_URL = os.environ.get(
#     "EKA_RECORDS_SDK_URL",
#     "https://abdm.dev.eka.care/abdm-records/index.html",
# )
#
#
# # Public/base URL of YOUR application.
# #
# # Example:
# #
# #   http://localhost:5000
# #
# # or:
# #
# #   https://your-domain.com
# #
# APP_BASE_URL = os.environ.get(
#     "APP_BASE_URL",
#     "http://localhost:5001",
# ).rstrip("/")
#
#
# # ============================================================
# # HELPERS
# # ============================================================
#
# def get_hiu_clinic_id():
#     """
#     Get the Eka HIU / clinic ID.
#
#     This is the CID used by the Records SDK.
#     """
#
#     clinic_id = os.environ.get(
#         "EKA_HIU_CLINIC_ID",
#         "",
#     ).strip()
#
#     if not clinic_id:
#         raise RuntimeError(
#             "EKA_HIU_CLINIC_ID is not configured."
#         )
#
#     return clinic_id
#
#
# def get_patient_row(care_context_id):
#     """
#     Find patient information from your existing
#     master_flat_table.csv using care_context_id.
#     """
#
#     if not care_context_id:
#         raise ValueError(
#             "care_context_id is required."
#         )
#
#     try:
#         row = ftm.find_row_by_care_context_id(
#             care_context_id
#         )
#
#     except ValueError as exc:
#         raise ValueError(
#             f"Unable to find care context "
#             f"{care_context_id}: {exc}"
#         )
#
#     if not row:
#         raise ValueError(
#             f"No patient found for "
#             f"care_context_id={care_context_id}"
#         )
#
#     return row
#
#
# def validate_patient_for_sdk(row):
#     """
#     Validate the fields required by Eka Records SDK.
#     """
#
#     missing = []
#
#     if not row.get("abha_address"):
#         missing.append("abha_address")
#
#     if not row.get("eka_patient_id"):
#         missing.append("eka_patient_id")
#
#     if missing:
#         raise ValueError(
#             "Missing required SDK patient fields: "
#             + ", ".join(missing)
#         )
#
#     if row.get("link_status") != "LINKED":
#         raise ValueError(
#             "Care Context is not LINKED. "
#             f"Current status: {row.get('link_status')}"
#         )
#
#
# def build_records_sdk_url(row, token):
#     """
#     Build the Eka Records SDK URL.
#
#     Required Eka parameters:
#
#         abha
#         oid
#         cid
#         consent-view
#         token
#     """
#
#     clinic_id = get_hiu_clinic_id()
#
#     consent_view_url = (
#         f"{APP_BASE_URL}/records"
#     )
#
#     params = {
#         "abha": row["abha_address"],
#         "oid": row["eka_patient_id"],
#         "cid": clinic_id,
#         "consent-view": consent_view_url,
#         "token": token,
#     }
#
#     return (
#         f"{EKA_RECORDS_SDK_URL}"
#         f"?{urlencode(params)}"
#     )
#
#
# # ============================================================
# # HEALTH CHECK
# # ============================================================
#
# @app.get("/")
# def home():
#     return jsonify({
#         "application": "Eka ABDM Records SDK",
#         "status": "running",
#         "message": (
#             "Use /abdm-records/<care_context_id> "
#             "to open the Eka Records SDK."
#         ),
#     })
#
#
# # ============================================================
# # RECORDS SDK
# # ============================================================
#
# @app.get("/abdm-records/<care_context_id>")
# def abdm_records(care_context_id):
#     """
#     Open Eka Records SDK for a patient.
#
#     Example:
#
#         /abdm-records/cc-edc0eb5fd2544a43
#     """
#
#     try:
#         # ----------------------------------------------------
#         # 1. Find patient
#         # ----------------------------------------------------
#
#         row = get_patient_row(
#             care_context_id
#         )
#
#         # ----------------------------------------------------
#         # 2. Validate patient
#         # ----------------------------------------------------
#
#         validate_patient_for_sdk(
#             row
#         )
#
#         # ----------------------------------------------------
#         # 3. Get Eka configuration
#         # ----------------------------------------------------
#
#         config = load_config()
#
#         # ----------------------------------------------------
#         # 4. Generate short-lived Eka access token
#         # ----------------------------------------------------
#
#         token = get_auth_token(
#             config
#         )
#
#         # ----------------------------------------------------
#         # 5. Build Records SDK URL
#         # ----------------------------------------------------
#
#         sdk_url = build_records_sdk_url(
#             row,
#             token,
#         )
#
#         print()
#         print("==============================================")
#         print("EKA RECORDS SDK")
#         print("==============================================")
#         print()
#
#         print(
#             "Patient Name :",
#             row.get("patient_name"),
#         )
#
#         print(
#             "ABHA         :",
#             row.get("abha_address"),
#         )
#
#         print(
#             "OID          :",
#             row.get("eka_patient_id"),
#         )
#
#         print(
#             "Care Context :",
#             row.get("care_context_id"),
#         )
#
#         print(
#             "HIU Clinic   :",
#             get_hiu_clinic_id(),
#         )
#
#         print()
#         print(
#             "Consent View :",
#             f"{APP_BASE_URL}/records",
#         )
#
#         print()
#         print("Opening Eka Records SDK...")
#         print()
#
#         # ----------------------------------------------------
#         # Redirect browser to Eka SDK
#         # ----------------------------------------------------
#
#         return redirect(
#             sdk_url,
#             code=302,
#         )
#
#     except Exception as exc:
#
#         print()
#         print("ERROR:")
#         print(exc)
#         print()
#
#         return jsonify({
#             "success": False,
#             "error": str(exc),
#         }), 400
#
#
# # ============================================================
# # CONSENT VIEW
# # ============================================================
#
# @app.get("/records")
# def records_view():
#     """
#     This is YOUR consent-view page.
#
#     Eka opens this URL after the doctor clicks VIEW
#     for an approved consent.
#
#     Expected query parameters:
#
#         consent_id
#         abha
#     """
#
#     consent_id = request.args.get(
#         "consent_id",
#         "",
#     )
#
#     abha = request.args.get(
#         "abha",
#         "",
#     )
#
#     print()
#     print("==============================================")
#     print("CONSENT VIEW")
#     print("==============================================")
#     print()
#
#     print(
#         "Consent ID:",
#         consent_id,
#     )
#
#     print(
#         "ABHA:",
#         abha,
#     )
#
#     print()
#
#     # --------------------------------------------------------
#     # IMPORTANT
#     # --------------------------------------------------------
#     #
#     # This page is intentionally NOT calling:
#     #
#     #   Consent Details
#     #
#     # or:
#     #
#     #   Retrieve Health Records
#     #
#     # yet.
#     #
#     # We should implement those APIs next using the exact
#     # Eka request/response format from your account/docs.
#     # --------------------------------------------------------
#
#     return f"""
#     <!DOCTYPE html>
#
#     <html>
#
#     <head>
#
#         <title>
#             ABDM Health Records
#         </title>
#
#         <meta
#             charset="UTF-8"
#         >
#
#         <meta
#             name="viewport"
#             content="width=device-width, initial-scale=1.0"
#         >
#
#         <style>
#
#             body {{
#                 font-family: Arial, sans-serif;
#                 margin: 40px;
#                 background: #f5f6f8;
#             }}
#
#             .container {{
#                 max-width: 1000px;
#                 margin: auto;
#                 background: white;
#                 padding: 30px;
#                 border-radius: 10px;
#             }}
#
#             h1 {{
#                 margin-top: 0;
#             }}
#
#             .info {{
#                 background: #f1f3f5;
#                 padding: 15px;
#                 border-radius: 8px;
#                 margin-bottom: 20px;
#             }}
#
#             .label {{
#                 font-weight: bold;
#             }}
#
#             .message {{
#                 padding: 20px;
#                 border: 1px solid #ddd;
#                 border-radius: 8px;
#                 margin-top: 20px;
#             }}
#
#         </style>
#
#     </head>
#
#
#     <body>
#
#         <div class="container">
#
#             <h1>
#                 Patient Health Records
#             </h1>
#
#             <div class="info">
#
#                 <p>
#                     <span class="label">
#                         ABHA:
#                     </span>
#
#                     {abha or "Not provided"}
#                 </p>
#
#                 <p>
#                     <span class="label">
#                         Consent ID:
#                     </span>
#
#                     {consent_id or "Not provided"}
#                 </p>
#
#             </div>
#
#
#             <div class="message">
#
#                 <h3>
#                     Consent Approved
#                 </h3>
#
#                 <p>
#                     The Eka Records SDK has opened this
#                     consent-view page successfully.
#                 </p>
#
#                 <p>
#                     Next step:
#                     retrieve the approved care contexts
#                     and fetch the FHIR health records.
#                 </p>
#
#             </div>
#
#         </div>
#
#     </body>
#
#     </html>
#     """
#
#
# # ============================================================
# # PATIENT INFORMATION API
# # ============================================================
#
# @app.get("/api/patient/<care_context_id>")
# def patient_information(care_context_id):
#     """
#     Optional API for your frontend.
#
#     Returns basic patient information required
#     by your own UI.
#
#     Do NOT expose sensitive information unnecessarily
#     in production.
#     """
#
#     try:
#
#         row = get_patient_row(
#             care_context_id
#         )
#
#         validate_patient_for_sdk(
#             row
#         )
#
#         return jsonify({
#             "success": True,
#
#             "patient": {
#                 "name": row.get(
#                     "patient_name"
#                 ),
#
#                 "abha_address": row.get(
#                     "abha_address"
#                 ),
#
#                 "oid": row.get(
#                     "eka_patient_id"
#                 ),
#
#                 "care_context_id": row.get(
#                     "care_context_id"
#                 ),
#
#                 "link_status": row.get(
#                     "link_status"
#                 ),
#             },
#         })
#
#     except Exception as exc:
#
#         return jsonify({
#             "success": False,
#             "error": str(exc),
#         }), 400
#
#
# # ============================================================
# # MAIN
# # ============================================================
#
# def main():
#
#     parser = argparse.ArgumentParser(
#         description=(
#             "Run Eka Care ABDM Records SDK server."
#         )
#     )
#
#     parser.add_argument(
#         "--host",
#         default=os.environ.get(
#             "HOST",
#             "127.0.0.1",
#         ),
#     )
#
#     parser.add_argument(
#         "--port",
#         type=int,
#         default=int(
#             os.environ.get(
#                 "PORT",
#                 "5001",
#             )
#         ),
#     )
#
#     args = parser.parse_args()
#
#     print()
#     print("==============================================")
#     print("EKA ABDM RECORDS SDK SERVER")
#     print("==============================================")
#     print()
#
#     print(
#         "SDK URL:",
#         EKA_RECORDS_SDK_URL,
#     )
#
#     print(
#         "APP URL:",
#         APP_BASE_URL,
#     )
#
#     print(
#         "CONSENT VIEW:",
#         f"{APP_BASE_URL}/records",
#     )
#
#     print()
#
#     print(
#         "Example:"
#     )
#
#     print(
#         f"  http://{args.host}:{args.port}"
#         "/abdm-records/<care_context_id>"
#     )
#
#     print()
#
#     app.run(
#         host=args.host,
#         port=args.port,
#         debug=False,
#     )
#
#
# if __name__ == "__main__":
#     main()

"""
Eka Care ABDM Records SDK + Consent Details

Flow:

    Doctor opens patient
        ↓
    Eka Records SDK
        ↓
    Request Consent
        ↓
    Patient approves
        ↓
    Consent = SUCCESS
        ↓
    View
        ↓
    /records?consent_id=...&abha=...
        ↓
    Consent Details API
        ↓
    Approved HIPs + Care Contexts
        ↓
    Retrieve Health Records API
        ↓
    FHIR Bundle
        ↓
    Display records
"""

import os
import sys
import argparse
import json
import time

from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, request
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

# ============================================================
# PROJECT IMPORTS
# ============================================================

import flat_table_manager as ftm

from config import load_config
from eka_client import get_auth_token

# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)

# ============================================================
# EKA RECORDS SDK
# ============================================================

EKA_RECORDS_SDK_URL = os.environ.get(
    "EKA_RECORDS_SDK_URL",
    "https://abdm.dev.eka.care/abdm-records/index.html",
)

APP_BASE_URL = os.environ.get(
    "APP_BASE_URL",
    "http://localhost:5001",
).rstrip("/")

# ============================================================
# OPTION A
# ============================================================
#
# FHIR is NOT retrieved from:
#
#   GET /health/api/v1/fhir/retrieve
#
# Instead:
#
#   abha.hiu_data_push
#          ↓
#   webhook.py
#          ↓
#   decrypt FHIR
#          ↓
#   decrypt-hiu/<care_context_id>.json
#
# records_sdk.py reads that file.
# ============================================================

DECRYPT_HIU_DIR = Path(
    os.environ.get(
        "DECRYPT_HIU_DIR",
        "decrypt-hiu",
    )
)

RECORD_WAIT_SECONDS = int(
    os.environ.get(
        "RECORD_WAIT_SECONDS",
        "60",
    )
)

RECORD_POLL_SECONDS = float(
    os.environ.get(
        "RECORD_POLL_SECONDS",
        "2",
    )
)


# ============================================================
# HELPERS
# ============================================================

def get_hiu_clinic_id():

    clinic_id = os.environ.get(
        "EKA_HIU_CLINIC_ID",
        "",
    ).strip()

    if not clinic_id:
        raise RuntimeError(
            "EKA_HIU_CLINIC_ID is not configured."
        )

    return clinic_id


def get_patient_row(care_context_id):

    if not care_context_id:
        raise ValueError(
            "care_context_id is required."
        )

    try:
        row = ftm.find_row_by_care_context_id(
            care_context_id
        )

    except ValueError as exc:
        raise ValueError(
            f"Unable to find care context "
            f"{care_context_id}: {exc}"
        )

    if not row:
        raise ValueError(
            f"No patient found for "
            f"care_context_id={care_context_id}"
        )

    return row


def validate_patient_for_sdk(row):

    missing = []

    if not row.get("abha_address"):
        missing.append("abha_address")

    if not row.get("eka_patient_id"):
        missing.append("eka_patient_id")

    if missing:
        raise ValueError(
            "Missing required SDK fields: "
            + ", ".join(missing)
        )

    if row.get("link_status") != "LINKED":
        raise ValueError(
            "Care Context is not LINKED. "
            f"Current status: {row.get('link_status')}"
        )


# ============================================================
# BUILD EKA RECORDS SDK URL
# ============================================================

def build_records_sdk_url(row, token):

    clinic_id = get_hiu_clinic_id()

    consent_view_url = (
        f"{APP_BASE_URL}/records"
    )

    params = {
        "abha": row["abha_address"],
        "oid": row["eka_patient_id"],
        "cid": clinic_id,
        "consent-view": consent_view_url,
        "token": token,
    }

    return (
        f"{EKA_RECORDS_SDK_URL}"
        f"?{urlencode(params)}"
    )


# ============================================================
# CONSENT DETAILS API
# ============================================================

def get_consent_details(
    consent_id,
    health_id,
    token,
):

    url = (
        f"{load_config().base_url}"
        "/abdm/v1/consents/details"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "consent_id": consent_id,
        "health_id": health_id,
    }

    print()
    print("==============================================")
    print("CONSENT DETAILS API")
    print("==============================================")
    print()

    print("Consent ID:", consent_id)
    print("Health ID:", health_id)
    print("URL:", url)

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
    )

    print(
        "HTTP STATUS:",
        response.status_code
    )

    print()
    print("RAW CONSENT DETAILS:")
    print(response.text)
    print()

    if not response.ok:
        raise RuntimeError(
            "Consent Details API failed: "
            f"HTTP {response.status_code} - "
            f"{response.text}"
        )

    try:
        return response.json()

    except ValueError as exc:
        raise RuntimeError(
            "Consent Details API returned "
            "invalid JSON."
        ) from exc


# ============================================================
# EXTRACT CARE CONTEXTS
# ============================================================

def extract_care_contexts(consent_details):

    care_contexts = []

    data = consent_details.get(
        "data",
        []
    )

    if not isinstance(data, list):
        raise RuntimeError(
            "Unexpected Consent Details response: "
            "'data' is not a list."
        )

    for facility in data:

        hip = facility.get(
            "hip",
            {}
        )

        hip_id = hip.get("id")

        hip_name = hip.get("name")

        contexts = facility.get(
            "care_contexts",
            []
        )

        if not isinstance(
            contexts,
            list
        ):
            continue

        for context in contexts:

            care_context_id = context.get(
                "id"
            )

            if not care_context_id:
                continue

            care_contexts.append({

                "hip_id":
                    hip_id,

                "hip_name":
                    hip_name,

                "care_context_id":
                    care_context_id,

                "display":
                    context.get(
                        "display"
                    ),

                "status":
                    context.get(
                        "status"
                    ),

                "created_at":
                    context.get(
                        "created_at"
                    ),

                "documents":
                    context.get(
                        "documents",
                        []
                    ),
            })

    return care_contexts


# ============================================================
# OPTION A - FHIR FILE
# ============================================================

def get_fhir_file_path(care_context_id):

    # Prevent accidental path traversal.
    safe_id = "".join(
        ch
        for ch in str(care_context_id)
        if ch.isalnum()
        or ch in ("-", "_", ".")
    )

    if not safe_id:
        raise ValueError(
            "Invalid care_context_id."
        )

    return (
        DECRYPT_HIU_DIR
        / f"{safe_id}.json"
    )


def read_received_fhir_bundle(
    care_context_id
):

    file_path = get_fhir_file_path(
        care_context_id
    )

    if not file_path.exists():
        return None

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            bundle = json.load(f)

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            f"FHIR JSON is invalid: "
            f"{file_path}"
        ) from exc

    if not isinstance(
        bundle,
        dict
    ):
        raise RuntimeError(
            f"FHIR data is not a JSON object: "
            f"{file_path}"
        )

    return bundle


# ============================================================
# WAIT FOR abha.hiu_data_push
# ============================================================

def wait_for_fhir_bundle(
    care_context_id
):

    file_path = get_fhir_file_path(
        care_context_id
    )

    print()
    print("==============================================")
    print("WAITING FOR FHIR DATA")
    print("==============================================")
    print()

    print(
        "Care Context:",
        care_context_id
    )

    print(
        "Expected file:",
        file_path
    )

    print(
        "Waiting:",
        RECORD_WAIT_SECONDS,
        "seconds"
    )

    print()

    deadline = (
        time.time()
        + RECORD_WAIT_SECONDS
    )

    while time.time() < deadline:

        bundle = read_received_fhir_bundle(
            care_context_id
        )

        if bundle is not None:

            print(
                "FHIR BUNDLE RECEIVED"
            )

            print(
                "File:",
                file_path
            )

            return bundle

        time.sleep(
            RECORD_POLL_SECONDS
        )

    return None


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return jsonify({

        "application":
            "Eka ABDM Records SDK",

        "status":
            "running",

        "mode":
            "OPTION_A",

        "message":
            (
                "FHIR data is received through "
                "abha.hiu_data_push."
            ),
    })


# ============================================================
# OPEN EKA RECORDS SDK
# ============================================================

@app.get(
    "/abdm-records/<care_context_id>"
)
def abdm_records(
    care_context_id
):

    try:

        row = get_patient_row(
            care_context_id
        )

        validate_patient_for_sdk(
            row
        )

        config = load_config()

        token = get_auth_token(
            config
        )

        sdk_url = build_records_sdk_url(
            row,
            token
        )

        print()
        print("==============================================")
        print("EKA RECORDS SDK")
        print("==============================================")
        print()

        print(
            "Patient:",
            row.get(
                "patient_name"
            )
        )

        print(
            "ABHA:",
            row.get(
                "abha_address"
            )
        )

        print(
            "OID:",
            row.get(
                "eka_patient_id"
            )
        )

        print(
            "Care Context:",
            care_context_id
        )

        print()

        return redirect(
            sdk_url,
            code=302
        )

    except Exception as exc:

        return jsonify({

            "success":
                False,

            "error":
                str(exc),
        }), 400


# ============================================================
# CONSENT VIEW
# ============================================================

@app.get(
    "/records"
)
def records_view():

    # Eka Records SDK sends these when
    # the user clicks View.

    consent_id = request.args.get(
        "consent_id",
        "",
    ).strip()

    abha = request.args.get(
        "abha",
        "",
    ).strip()

    print()
    print("==============================================")
    print("CONSENT VIEW - OPTION A")
    print("==============================================")
    print()

    print(
        "Consent ID:",
        consent_id
    )

    print(
        "ABHA:",
        abha
    )

    print()

    if not consent_id:

        return jsonify({

            "success":
                False,

            "error":
                "consent_id is missing.",
        }), 400

    if not abha:

        return jsonify({

            "success":
                False,

            "error":
                "abha is missing.",
        }), 400

    try:

        # ----------------------------------------------------
        # 1. Get Eka token
        # ----------------------------------------------------

        config = load_config()

        token = get_auth_token(
            config
        )

        # ----------------------------------------------------
        # 2. Get EXACT selected consent
        # ----------------------------------------------------

        consent_details = (
            get_consent_details(
                consent_id=
                    consent_id,

                health_id=
                    abha,

                token=
                    token,
            )
        )

        # ----------------------------------------------------
        # 3. Get approved care contexts
        # ----------------------------------------------------

        care_contexts = (
            extract_care_contexts(
                consent_details
            )
        )

        print()
        print(
            "APPROVED CARE CONTEXTS:"
        )

        print(
            json.dumps(
                care_contexts,
                indent=2
            )
        )

        print()

        # ----------------------------------------------------
        # 4. DO NOT CALL:
        #
        # GET /health/api/v1/fhir/retrieve
        #
        # Because this integration is OPTION A.
        #
        # Eka will request the data from our HIP.
        #
        # HIP:
        #
        #   abha.hip_data_fetch
        #
        # then:
        #
        #   build FHIR
        #
        # then:
        #
        #   on-fetch
        #
        # then:
        #
        #   abha.hiu_data_push
        # ----------------------------------------------------

        records = []

        for context in care_contexts:

            care_context_id = (
                context.get(
                    "care_context_id"
                )
            )

            if not care_context_id:
                continue

            print()
            print(
                "Waiting for:",
                care_context_id
            )

            fhir_bundle = (
                wait_for_fhir_bundle(
                    care_context_id
                )
            )

            if fhir_bundle is None:

                records.append({

                    "hip_id":
                        context.get(
                            "hip_id"
                        ),

                    "hip_name":
                        context.get(
                            "hip_name"
                        ),

                    "care_context_id":
                        care_context_id,

                    "display":
                        context.get(
                            "display"
                        ),

                    "status":
                        context.get(
                            "status"
                        ),

                    "data_status":
                        "WAITING_FOR_HIU_DATA_PUSH",

                    "fhir_bundle":
                        None,

                    "error":
                        (
                            "FHIR Bundle has not arrived "
                            "through abha.hiu_data_push."
                        ),
                })

                continue

            # ------------------------------------------------
            # FHIR received
            # ------------------------------------------------

            records.append({

                "hip_id":
                    context.get(
                        "hip_id"
                    ),

                "hip_name":
                    context.get(
                        "hip_name"
                    ),

                "care_context_id":
                    care_context_id,

                "display":
                    context.get(
                        "display"
                    ),

                "status":
                    context.get(
                        "status"
                    ),

                "data_status":
                    "FHIR_RECEIVED",

                # THIS IS THE RAW FHIR JSON
                "fhir_bundle":
                    fhir_bundle,
            })

        # ----------------------------------------------------
        # 5. Return result
        # ----------------------------------------------------

        return jsonify({

            "success":
                True,

            "consent_id":
                consent_id,

            "abha":
                abha,

            "care_contexts":
                care_contexts,

            "records":
                records,
        })

    except Exception as exc:

        print()
        print("CONSENT VIEW ERROR:")
        print(exc)
        print()

        return jsonify({

            "success":
                False,

            "consent_id":
                consent_id,

            "abha":
                abha,

            "error":
                str(exc),
        }), 500


# ============================================================
# PATIENT INFORMATION
# ============================================================

@app.get(
    "/api/patient/<care_context_id>"
)
def patient_information(
    care_context_id
):

    try:

        row = get_patient_row(
            care_context_id
        )

        validate_patient_for_sdk(
            row
        )

        return jsonify({

            "success":
                True,

            "patient": {

                "name":
                    row.get(
                        "patient_name"
                    ),

                "abha_address":
                    row.get(
                        "abha_address"
                    ),

                "oid":
                    row.get(
                        "eka_patient_id"
                    ),

                "care_context_id":
                    row.get(
                        "care_context_id"
                    ),

                "link_status":
                    row.get(
                        "link_status"
                    ),
            },
        })

    except Exception as exc:

        return jsonify({

            "success":
                False,

            "error":
                str(exc),
        }), 400


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Run Eka Care ABDM Records SDK server."
        )
    )

    parser.add_argument(
        "--host",
        default=os.environ.get(
            "HOST",
            "127.0.0.1",
        ),
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(
            os.environ.get(
                "PORT",
                "5001",
            )
        ),
    )

    args = parser.parse_args()

    print()
    print("==============================================")
    print("EKA ABDM RECORDS SDK - OPTION A")
    print("==============================================")
    print()

    print(
        "SDK URL:",
        EKA_RECORDS_SDK_URL
    )

    print(
        "APP URL:",
        APP_BASE_URL
    )

    print(
        "CONSENT VIEW:",
        f"{APP_BASE_URL}/records"
    )

    print(
        "FHIR DIRECTORY:",
        DECRYPT_HIU_DIR
    )

    print()

    app.run(
        host=args.host,
        port=args.port,
        debug=False,
    )


if __name__ == "__main__":
    main()