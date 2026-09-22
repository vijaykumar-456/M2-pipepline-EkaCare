###chatgpt-updated on eka care curl
# import os
# import sys
# import json
# import argparse
# from datetime import datetime, timezone, timedelta
#
# import requests
# from dotenv import load_dotenv
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
# sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
#
#
# # ============================================================
# # PROJECT IMPORTS
# # ============================================================
#
# import flat_table_manager as ftm
# from config import load_config
# from eka_client import get_auth_token
#
#
# # ============================================================
# # CREATE CONSENT
# # ============================================================
#
# def create_consent(row):
#     """
#     Create a consent request using Eka's Sandbox HIU consent API.
#
#     Eka Care Sandbox example:
#
#         POST /abdm/v1/consents/create
#
#     Headers:
#         Content-Type
#         X-Hip-Id
#         Authorization
#
#     Body:
#         patient
#         period
#         purpose
#         record_types
#     """
#
#     config = load_config()
#
#     # --------------------------------------------------------
#     # Get Eka authentication token
#     # --------------------------------------------------------
#
#     try:
#         token = get_auth_token(config)
#     except Exception as e:
#         print()
#         print("ERROR obtaining Eka authentication token:")
#         print(e)
#         return
#
#     # --------------------------------------------------------
#     # Consent Create API
#     # --------------------------------------------------------
#
#     url = f"{config.base_url}/abdm/v1/consents/create"
#
#     # --------------------------------------------------------
#     # Consent period
#     # --------------------------------------------------------
#
#     now = datetime.now(timezone.utc)
#
#     period_from = datetime(2026,8,1,0,0,0,
#         tzinfo=timezone.utc)
#
#     period_to = now
#
#     expiry = now + timedelta(days=30)
#
#     # --------------------------------------------------------
#     # Consent payload
#     #
#     # This follows the cURL shared by Eka Care.
#     #
#     # Do NOT add:
#     #   - care_contexts
#     #   - hip_identifier
#     #   - hiu
#     #   - requester
#     #
#     # unless Eka specifically asks for them.
#     # --------------------------------------------------------
#
#     payload = {
#         "patient": {
#             "health_id": row["abha_address"],
#             "oid": row["eka_patient_id"],
#         },
#
#         "period": {
#             "expiry": expiry.isoformat().replace("+00:00", "Z"),
#             "from": period_from.isoformat().replace("+00:00", "Z"),
#             "to": period_to.isoformat().replace("+00:00", "Z"),
#         },
#
#         "purpose": "Care management",
#
#         "record_types": [
#             row["hi_type"]
#         ],
#     }
#
#     # --------------------------------------------------------
#     # Headers
#     #
#     # These match the cURL provided by Eka Care.
#     # --------------------------------------------------------
#
#     headers = {
#         "Content-Type": "application/json",
#         "X-Hip-Id": row["hip_id"],
#         "Authorization": f"Bearer {token}",
#     }
#
#     # --------------------------------------------------------
#     # Display request
#     # --------------------------------------------------------
#
#     print()
#     print("==============================================")
#     print("CREATING REAL HIU CONSENT REQUEST")
#     print("==============================================")
#     print()
#
#     print("Patient")
#     print("----------------------------------------------")
#     print("ABHA Address :", row.get("abha_address"))
#     print("OID          :", row.get("eka_patient_id"))
#     print()
#
#     print("HIP")
#     print("----------------------------------------------")
#     print("HIP ID       :", row.get("hip_id"))
#     print()
#
#     print("Care Context")
#     print("----------------------------------------------")
#     print("Care Context :", row.get("care_context_id"))
#     print()
#
#     print("Consent Request")
#     print("----------------------------------------------")
#     print(json.dumps(payload, indent=2))
#     print()
#
#     print("Sending consent request to Eka...")
#     print()
#
#     # --------------------------------------------------------
#     # API call
#     # --------------------------------------------------------
#
#     try:
#         response = requests.post(url,headers=headers,json=payload,timeout=30)
#
#     except requests.RequestException as e:
#         print()
#         print("ERROR calling Eka:")
#         print(e)
#         return
#
#     # --------------------------------------------------------
#     # Response
#     # --------------------------------------------------------
#
#     print("HTTP STATUS:", response.status_code)
#     print()
#
#     try:
#         result = response.json()
#     except ValueError:
#         result = None
#
#     print("Eka Response")
#     print("----------------------------------------------")
#
#     if result is not None:
#         print(json.dumps(result, indent=2))
#     else:
#         print(response.text)
#
#     print()
#
#     # --------------------------------------------------------
#     # SUCCESS
#     #
#     # Your actual Sandbox response was:
#     #
#     # HTTP STATUS: 200
#     #
#     # {
#     #     "consent_init_id": "..."
#     # }
#     # --------------------------------------------------------
#
#     if response.status_code in (200, 201, 202, 204):
#
#         print("==============================================")
#         print("CONSENT REQUEST CREATED SUCCESSFULLY")
#         print("==============================================")
#         print()
#
#         consent_init_id = None
#
#         if isinstance(result, dict):
#
#             consent_init_id = result.get("consent_init_id")
#
#         if consent_init_id:
#             print("consent_init_id:")
#             print("----------------------------------------------")
#             print(consent_init_id)
#             print()
#
#         print("NEXT STEP")
#         print("----------------------------------------------")
#         print("The consent request has been created.")
#         print()
#         print("Use the consent_init_id returned by Eka")
#         print("for the next consent/approval step.")
#         print()
#         print("After the consent is approved, Eka / ABDM")
#         print("should initiate the HIP data-fetch flow.")
#         print()
#         print("Your webhook should then receive:")
#         print()
#         print("    abha.hip_data_fetch")
#         print()
#
#         return
#
#     # --------------------------------------------------------
#     # FAILURE
#     # --------------------------------------------------------
#
#     print("==============================================")
#     print("CONSENT REQUEST FAILED")
#     print("==============================================")
#     print()
#
#     print("HTTP STATUS:", response.status_code)
#
#     if result is not None:
#         print("Eka error response:")
#         print(json.dumps(result, indent=2))
#     else:
#         print("Eka response:")
#         print(response.text)
#
#     print()
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
#             "Create a real HIU consent request for "
#             "an existing linked Care Context."
#         )
#     )
#
#     parser.add_argument(
#         "--care-context-id",
#         required=True,
#         help=(
#             "Existing LINKED care_context_id "
#             "from master_flat_table.csv"
#         ),
#     )
#
#     args = parser.parse_args()
#
#     # --------------------------------------------------------
#     # Find existing Care Context
#     # --------------------------------------------------------
#
#     try:
#         row = ftm.find_row_by_care_context_id(
#             args.care_context_id
#         )
#
#     except ValueError as e:
#         print()
#         print("ERROR:")
#         print(e)
#         print()
#         return
#
#     # --------------------------------------------------------
#     # Display existing Care Context
#     # --------------------------------------------------------
#
#     print()
#     print("Existing Care Context")
#     print("----------------------------------------------")
#     print("Record ID       :", row.get("record_id"))
#     print("Patient ID      :", row.get("row_id"))
#     print("Patient Name    :", row.get("patient_name"))
#     print("ABHA Address    :", row.get("abha_address"))
#     print("ABHA Number     :", row.get("abha_number"))
#     print("OID             :", row.get("eka_patient_id"))
#     print("HIP ID          :", row.get("hip_id"))
#     print("Care Context ID :", row.get("care_context_id"))
#     print("HI Type         :", row.get("hi_type"))
#     print("Link Status     :", row.get("link_status"))
#     print()
#
#     # --------------------------------------------------------
#     # Care Context must already be linked
#     # --------------------------------------------------------
#
#     if row.get("link_status") != "LINKED":
#
#         print("ERROR: Care Context is not LINKED.")
#         print(
#             "Current link_status:",
#             row.get("link_status")
#         )
#         print()
#
#         return
#
#     # --------------------------------------------------------
#     # Create consent
#     # --------------------------------------------------------
#
#     create_consent(row)
#
#
# # ============================================================
# # ENTRY POINT
# # ============================================================
#
# if __name__ == "__main__":
#     main()


##claude code full flow

import os
import sys
import json
import argparse
import time
from datetime import datetime, timezone, timedelta

import requests
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
# SETTINGS
# ============================================================

CONSENT_LIST_RETRIES = 5
CONSENT_LIST_RETRY_SECONDS = 2


# ============================================================
# UTILITY
# ============================================================

def utc_string(dt):
    """
    Convert datetime to Eka/ABDM UTC ISO format.
    """
    return dt.astimezone(timezone.utc).isoformat().replace(
        "+00:00",
        "Z"
    )


# ============================================================
# CREATE
# ============================================================

def create_consent(row, config, token):
    """
    Create a consent request.

    POST /abdm/v1/consents/create
    """

    url = (
        f"{config.base_url}"
        "/abdm/v1/consents/create"
    )

    now = datetime.now(timezone.utc)

    period_from = datetime(
        2026,
        8,
        1,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )

    period_to = now
    expiry = now + timedelta(days=30)

    payload = {
        "care_contexts": [
            {
                "cc_ref": row["care_context_id"],
                "patient_ref": row["eka_patient_id"],
            }
        ],

        "hip_identifier": {
            "id": row["hip_id"],
            "name": row.get("clinic_id") or row["hip_id"],
        },

        "patient": {
            "health_id": row["abha_address"],
            "oid": row["eka_patient_id"],
        },

        "period": {
            "expiry": utc_string(expiry),
            "from": utc_string(period_from),
            "to": utc_string(period_to),
        },

        "purpose": "Care management",

        "record_types": [
            row["hi_type"]
        ],
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Hip-Id": row["hip_id"],
    }

    print()
    print("==============================================")
    print("STEP 1 - CREATING CONSENT")
    print("==============================================")
    print()

    print(json.dumps(payload, indent=2))
    print()

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        print("ERROR calling consent create:")
        print(e)
        return None

    print("HTTP STATUS:", response.status_code)

    try:
        result = response.json()
    except ValueError:
        result = {}

    print("Eka Response:")
    print(json.dumps(result, indent=2))
    print()

    if response.status_code not in (200, 201, 202, 204):
        print("CONSENT CREATE FAILED")
        return None

    consent_init_id = result.get(
        "consent_init_id"
    )

    if not consent_init_id:
        print("ERROR: consent_init_id not returned.")
        return None

    print("CONSENT CREATED")
    print("----------------------------------------------")
    print("consent_init_id:", consent_init_id)

    return consent_init_id


# ============================================================
# LIST CONSENTS
# ============================================================

def list_consents(row, config, token, consent_init_id):
    """
    Find the consent_id corresponding to the
    consent_init_id returned by consent creation.

    POST /abdm/v1/consents/list
    """

    url = (
        f"{config.base_url}"
        "/abdm/v1/consents/list"
    )

    payload = {
        "hiu": {
            "clinic_id": os.environ.get(
                "EKA_HIU_CLINIC_ID",
                row.get("hip_id", "")
            ),
        },

        "patient": {
            "health_id": row["abha_address"],
            "oid": row["eka_patient_id"],
        },
    }

    hiu_d_oid = os.environ.get(
        "EKA_HIU_D_OID",
        ""
    )

    if hiu_d_oid:
        payload["hiu"]["d_oid"] = hiu_d_oid

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print()
    print("==============================================")
    print("STEP 2 - FINDING CONSENT ID")
    print("==============================================")
    print()

    print("Looking for:")
    print("consent_init_id:", consent_init_id)
    print()

    for attempt in range(
        1,
        CONSENT_LIST_RETRIES + 1
    ):

        print(
            f"Checking consent list "
            f"(attempt {attempt}/{CONSENT_LIST_RETRIES})..."
        )

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
            )

        except requests.RequestException as e:
            print("ERROR calling consent list:")
            print(e)
            return None

        print(
            "HTTP STATUS:",
            response.status_code
        )

        try:
            result = response.json()
        except ValueError:
            result = {}

        if response.status_code not in (
            200,
            201,
            202,
        ):
            print("Consent list failed:")
            print(json.dumps(result, indent=2))
            return None

        consents = result.get(
            "consents",
            []
        )

        print(
            "Consents returned:",
            len(consents)
        )

        for consent in consents:

            if consent.get(
                "consent_init_id"
            ) == consent_init_id:

                consent_id = consent.get(
                    "consent_id"
                )

                if not consent_id:
                    print(
                        "Matching consent found, "
                        "but consent_id is missing."
                    )
                    return None

                # Guard against Eka's sandbox echoing consent_init_id
                # back as a placeholder before the real consent_id has
                # materialized -- keep polling instead of treating this
                # as the final answer.
                if consent_id == consent_init_id:
                    print("consent_id matches consent_init_id -- likely still provisioning, retrying...")
                    break  # breaks out of the for-loop, falls through to the retry sleep below

                print()
                print("MATCHING CONSENT FOUND")
                print("----------------------------------------------")
                print(
                    "consent_init_id:",
                    consent_init_id
                )
                print(
                    "consent_id     :",
                    consent_id
                )
                print(
                    "status         :",
                    consent.get("status")
                )
                print(
                    "hi_types       :",
                    consent.get("hi_types")
                )
                print(
                    "period         :"
                )
                print(
                    json.dumps(
                        consent.get("period", {}),
                        indent=2
                    )
                )

                return consent

        if attempt < CONSENT_LIST_RETRIES:

            print(
                "Consent not visible yet. "
                f"Waiting {CONSENT_LIST_RETRY_SECONDS}s..."
            )

            time.sleep(
                CONSENT_LIST_RETRY_SECONDS
            )

    print()
    print("ERROR: Could not find the newly-created consent.")
    print(
        "consent_init_id:",
        consent_init_id
    )

    return None


# ============================================================
# APPROVE CONSENT
# ============================================================

def approve_consent(
    row,
    config,
    token,
    consent,
):
    """
    Approve the consent.

    POST /abdm/v1/consents/approve?oid=<patient_oid>
    """

    consent_id = consent.get(
        "consent_id"
    )

    if not consent_id:
        print("ERROR: Missing consent_id.")
        return False

    url = (
        f"{config.base_url}"
        "/abdm/v1/consents/approve"
    )

    params = {
        "oid": row["eka_patient_id"]
    }

    consent_period = consent.get(
        "period",
        {}
    )

    duration_from = consent_period.get(
        "from"
    )

    duration_to = consent_period.get(
        "to"
    )

    if not duration_from:
        duration_from = utc_string(
            datetime.now(timezone.utc)
        )

    if not duration_to:
        duration_to = utc_string(
            datetime.now(timezone.utc)
            + timedelta(days=30)
        )

    erase_at = utc_string(
        datetime.now(timezone.utc)
        + timedelta(days=30)
    )

    hi_types = consent.get(
        "hi_types"
    )

    if not hi_types:
        hi_types = [
            row["hi_type"]
        ]

    care_context_id = row[
        "care_context_id"
    ]

    care_context_display = (
        row.get("care_context_display")
        or row.get("care_context_name")
        or row.get("display")
        or f"Care Context - {care_context_id}"
    )

    payload = {
        "consent_artefacts": [
            {
                "access_mode": "view",

                "care_contexts": [
                    {
                        "display": care_context_display,
                        "id": care_context_id,
                    }
                ],

                "duration": {
                    "from": duration_from,
                    "to": duration_to,
                },

                "erase_at": erase_at,

                "hi_types": hi_types,

                "hip_id": row["hip_id"],
            }
        ],

        "id": consent_id,

        "access_mode": "view",

        "duration": {
            "from": duration_from,
            "to": duration_to,
        },

        "erase_at": erase_at,

        "hi_types": hi_types,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    print()
    print("==============================================")
    print("STEP 3 - APPROVING CONSENT")
    print("==============================================")
    print()
    print("Consent ID:")
    print("----------------------------------------------")
    print(consent_id)
    print()

    print("Approval payload:")
    print("----------------------------------------------")
    print(json.dumps(payload, indent=2))
    print()

    print("Sending approval to Eka...")
    print()

    try:
        response = requests.post(
            url,
            params=params,
            headers=headers,
            json=payload,
            timeout=30,
        )

    except requests.RequestException as e:
        print()
        print("ERROR calling consent approve:")
        print(e)
        return False

    print(
        "HTTP STATUS:",
        response.status_code
    )
    print()

    if response.text:
        print("Eka Response:")
        print(response.text)
        print()

    if response.status_code == 204:

        print("==============================================")
        print("CONSENT APPROVED SUCCESSFULLY")
        print("==============================================")
        print()

        print("Consent ID:", consent_id)
        print()

        print("NEXT:")
        print("----------------------------------------------")
        print("Keep your webhook server running.")
        print()
        print("Expected webhook events:")
        print()
        print("    abha.consent_update")
        print("    abha.hip_data_fetch")
        print("    abha.hiu_data_push")
        print()

        return True

    print("==============================================")
    print("CONSENT APPROVAL FAILED")
    print("==============================================")
    print()

    try:
        error_result = response.json()
        print(
            json.dumps(
                error_result,
                indent=2
            )
        )
    except ValueError:
        print(response.text)

    return False


# ============================================================
# COMPLETE FLOW
# ============================================================

def run_consent_flow(row):
    """
    Complete automated flow:

        CREATE
          |
        LIST
          |
        FIND consent_id
          |
        APPROVE
          |
        WEBHOOKS
    """

    config = load_config()

    try:
        token = get_auth_token(config)

    except Exception as e:

        print()
        print(
            "ERROR obtaining Eka authentication token:"
        )
        print(e)
        return

    consent_init_id = create_consent(
        row,
        config,
        token,
    )

    if not consent_init_id:
        return

    consent = list_consents(
        row,
        config,
        token,
        consent_init_id,
    )

    if not consent:
        return

    # Reuse the SAME token/session used for create + list, rather than
    # forcing a fresh login right before approval. A forced re-login here
    # was the likely cause of the 491 SessionExpiredTryAgain error --
    # if Eka ties consent state to the session that created it, a brand
    # new login mid-flow breaks that continuity rather than fixing
    # anything "stale".
    approved = approve_consent(
        row,
        config,
        token,
        consent,
    )

    if not approved:
        return

    print()
    print("==============================================")
    print("AUTOMATED CONSENT FLOW COMPLETED")
    print("==============================================")
    print()

    print("Consent Init ID :", consent_init_id)
    print(
        "Consent ID      :",
        consent.get("consent_id")
    )

    print()
    print("Now wait for your webhook server.")
    print()
    print("Expected:")
    print("    abha.consent_update")
    print("    abha.hip_data_fetch")
    print("    abha.hiu_data_push")
    print()


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Run the complete automated HIU "
            "consent flow for an existing "
            "linked Care Context."
        )
    )

    parser.add_argument(
        "--care-context-id",
        required=True,
        help=(
            "Existing LINKED care_context_id "
            "from master_flat_table.csv"
        ),
    )

    args = parser.parse_args()

    try:

        row = ftm.find_row_by_care_context_id(
            args.care_context_id
        )

    except ValueError as e:

        print()
        print("ERROR:")
        print(e)
        print()

        return

    print()
    print("Existing Care Context")
    print("----------------------------------------------")
    print(
        "Record ID       :",
        row.get("record_id")
    )
    print(
        "Patient ID      :",
        row.get("row_id")
    )
    print(
        "Patient Name    :",
        row.get("patient_name")
    )
    print(
        "ABHA Address    :",
        row.get("abha_address")
    )
    print(
        "ABHA Number     :",
        row.get("abha_number")
    )
    print(
        "OID             :",
        row.get("eka_patient_id")
    )
    print(
        "HIP ID          :",
        row.get("hip_id")
    )
    print(
        "Care Context ID :",
        row.get("care_context_id")
    )
    print(
        "HI Type         :",
        row.get("hi_type")
    )
    print(
        "Link Status     :",
        row.get("link_status")
    )
    print()

    if row.get("link_status") != "LINKED":

        print(
            "ERROR: Care Context is not LINKED."
        )

        print(
            "Current link_status:",
            row.get("link_status")
        )

        print()

        return

    hiu_clinic_id = os.environ.get(
        "EKA_HIU_CLINIC_ID",
        ""
    )

    if not hiu_clinic_id:

        print(
            "ERROR: EKA_HIU_CLINIC_ID is not configured."
        )

        print(
            "Add it to your .env file."
        )

        print()

        return

    print(
        "HIU Clinic ID:",
        hiu_clinic_id
    )

    run_consent_flow(row)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()



