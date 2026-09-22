# #Claude-updated
# """
# Wraps Eka Care's API: login/token exchange + Link API + Phase 2 on-fetch.
#
# Auth is now self-managed here: call get_auth_token(config) and it handles
# login + in-memory caching + refresh before expiry. Callers never pass or
# store a token themselves -- it's pulled from config.client_id/client_secret
# on demand.
#
# NOT runnable from this environment -- no network path to Eka's API domain
# here. The request/response shapes below (login endpoint, field names) are
# UNCONFIRMED -- I don't have Eka's actual login API doc. If you have a link
# to it (same as the ECDH one), send it and I'll correct this to match
# exactly rather than guessing.
# """
# import time
# import requests
#
# from config import Config
#
#
# class EkaLinkError(Exception):
#     def __init__(self, message: str, http_status: int | None = None, body: str = ""):
#         super().__init__(message)
#         self.http_status = http_status
#         self.body = body
#
#
# class EkaAuthError(Exception):
#     def __init__(self, message: str, http_status: int | None = None, body: str = ""):
#         super().__init__(message)
#         self.http_status = http_status
#         self.body = body
#
#
# # In-memory token cache, keyed by client_id so multiple configs (e.g.
# # sandbox + prod in the same process) don't clobber each other's tokens.
# _token_cache: dict[str, dict] = {}
#
# # Refresh this many seconds before actual expiry, so a token never gets
# # used right at the edge of expiring mid-request.
# _REFRESH_MARGIN_SECONDS = 60
#
#
# def _login(config: Config) -> dict:
#     """
#     Calls Eka's login/token endpoint using client_id + client_secret.
#
#     UNCONFIRMED endpoint path and request/response field names -- this is
#     a best-guess client_credentials-style shape. Confirm against Eka's
#     real auth docs before trusting this in sandbox.
#     """
#     url = f"{config.base_url}/connect-auth/v1/account/login"
#     body = {
#         "client_id": config.client_id,
#         "client_secret": config.client_secret,
#     }
#     resp = requests.post(url, json=body, timeout=30)
#     if resp.status_code != 200:
#         raise EkaAuthError(
#             f"Login failed with status {resp.status_code}",
#             http_status=resp.status_code, body=resp.text,
#         )
#     data = resp.json()
#     access_token = data.get("access_token")  # UNCONFIRMED field name
#     expires_in = data.get("expires_in", 3600)  # UNCONFIRMED field name, default guess
#     if not access_token:
#         raise EkaAuthError("Login response did not contain an access_token", body=resp.text)
#
#     return {
#         "access_token": access_token,
#         "expires_at": time.time() + expires_in,
#     }
#
#
# def get_auth_token(config: Config) -> str:
#     """
#     Returns a valid access token, logging in only when there's no cached
#     token yet or the cached one is near expiry. This is what
#     link_care_context() and push_on_fetch_response() call internally --
#     you should not need to call this directly except to pre-warm the cache.
#     """
#     cached = _token_cache.get(config.client_id)
#     if cached and time.time() < cached["expires_at"] - _REFRESH_MARGIN_SECONDS:
#         return cached["access_token"]
#
#     token_data = _login(config)
#     _token_cache[config.client_id] = token_data
#     return token_data["access_token"]
#
#
# def link_care_context(config: Config, row: dict) -> requests.Response:
#     """
#     row must already have care_context_id/display/hi_type filled in
#     (i.e. generate_care_context() has run for this row).
#
#     Returns the raw response on 202. Raises EkaLinkError on anything else --
#     caller is responsible for logging (see logging_utils.log_push_event)
#     and updating the flat table (flat_table_manager.mark_link_sent /
#     leaving link_request_status alone on failure so it can be retried).
#     """
#     auth_token = get_auth_token(config)
#
#     url = f"{config.base_url}/abdm/v1/care-contexts/link"
#     headers = {
#         "X-Pt-Id": row["eka_patient_id"],
#         # "X-Partner-Pt-Id": row["partner_patient_id"],
#         "X-Hip-Id": row["hip_id"],
#         "Authorization": f"Bearer {auth_token}",   # confirm exact scheme before relying on this
#         "Content-Type": "application/json",
#     }
#     # care_context = {
#     #     "care_context_id": row["care_context_id"],
#     #     "display": row["display"],
#     # }
#     # if row.get("hi_types_multi"):
#     #     care_context["hi_types"] = row["hi_types_multi"].split(",")
#     # else:
#     #     care_context["hi_type"] = row["hi_type"]
#     #
#     # body = {
#     #     "abha_address": row["abha_address"],
#     #     "care_contexts": [care_context],
#     # }
#
#     care_context = {
#                 "care_context_id": row["care_context_id"],
#                 "display": row["display"],
#                 "hi_types": [row["hi_type"]],
#             }
#
#     # If multiple HI types are provided, use them instead.
#     if row.get("hi_types_multi"):
#         care_context["hi_types"] = [
#             value.strip()
#             for value in row["hi_types_multi"].split(",")
#             if value.strip()
#         ]
#
#     # Eka Care Link API request body
#     body = {
#         "abha_address": row["abha_address"],
#         "care_contexts": [care_context],
#         "oid": row["eka_patient_id"],
#         # "partner_user_id": row["partner_patient_id"],
#     }
#
#     resp = requests.post(url, headers=headers, json=body, timeout=30)
#
#     if resp.status_code == 202:
#         return resp
#
#     # Per earlier troubleshooting: a generic, ABDM-error-code-less 400 with
#     # CloudFront-shaped headers is usually environment/auth-side, not a
#     # payload problem. Surface the response headers so that's visible to
#     # whoever reads the exception, rather than just the body.
#     raise EkaLinkError(
#         f"Link API call failed with status {resp.status_code}",
#         http_status=resp.status_code,
#         body=resp.text,
#     )
#
#
# # def push_on_fetch_response(config: Config,transaction_id: str,entries: list,key_information: dict,
# #                            page_count: int = 1,page_number: int = 1) -> requests.Response:
# #     """
# #     Push encrypted care-context FHIR data to the HIU after receiving
# #     abha.hip_data_fetch.
# #
# #     Eka API:
# #         POST /abdm/v1/hip/care-context/data/on-fetch
# #
# #     The entries must contain:
# #         care_context_id
# #         checksum
# #         content
# #         media
# #
# #     key_information comes from the abha.hip_data_fetch webhook.
# #     """
# #
# #     auth_token = get_auth_token(config)
# #
# #     url = (
# #         f"{config.base_url}"
# #         "/abdm/v1/hip/care-context/data/on-fetch"
# #     )
# #
# #     headers = {
# #         "X-Pt-Id": config.oid,
# #         "X-Hip-Id": config.hip_id,
# #         "Authorization": f"Bearer {auth_token}",
# #         "Content-Type": "application/json",
# #     }
# #
# #     body = {
# #         "entries": entries,
# #         "key_information": key_information,
# #         "page_count": page_count,
# #         "page_number": page_number,
# #         "transaction_id": transaction_id,
# #     }
# #
# #     resp = requests.post(
# #         url,
# #         headers=headers,
# #         json=body,
# #         timeout=30,
# #     )
# #
# #     if resp.status_code == 202:
# #         return resp
# #
# #     raise EkaLinkError(
# #         f"On-fetch API call failed with status {resp.status_code}",
# #         http_status=resp.status_code,
# #         body=resp.text,
# #     )
#
# def push_on_fetch_response(
#     config: Config,
#     transaction_id: str,
#     care_context_id: str,
#     encrypted_content: str,
#     key_information: dict,
#     checksum: str,
#     page_number: int = 1,
#     page_count: int = 1,
# ) -> requests.Response:
#
#     auth_token = get_auth_token(config)
#
#     url = (
#         f"{config.base_url}"
#         "/abdm/v1/hip/care-context/data/on-fetch"
#     )
#
#     headers = {
#         "Authorization": f"Bearer {auth_token}",
#         "Content-Type": "application/json",
#     }
#
#     body = {
#         "entries": [
#             {
#                 "care_context_id": care_context_id,
#                 "checksum": checksum,
#                 "content": encrypted_content,
#                 "media": "application/fhir+json",
#             }
#         ],
#         "key_information": key_information,
#         "page_count": page_count,
#         "page_number": page_number,
#         "transaction_id": transaction_id,
#     }
#
#     resp = requests.post(
#         url,
#         headers=headers,
#         json=body,
#         timeout=30,
#     )
#
#     if resp.status_code not in (200, 202):
#         raise EkaLinkError(
#             f"Data On-Fetch failed with status {resp.status_code}",
#             http_status=resp.status_code,
#             body=resp.text,
#         )
#
#     return resp

#31/08/2026 - Claude updated code for M2-phase2
"""
Wraps Eka Care's API: login/token exchange + Link API + Phase 2 on-fetch.

Auth is self-managed here: call get_auth_token(config) and it handles
login + in-memory caching + refresh before expiry. Callers never pass or
store a token themselves.

NEVER hardcode a real token/secret in this file. If you're pasting a real
JWT into a "just for testing" comment, rotate it -- comments still get
committed to Git, and a live token in version control is a real exposure.
"""
import os
import time
import hashlib
import requests

from config import Config


class EkaLinkError(Exception):
    def __init__(self, message: str, http_status: int | None = None, body: str = ""):
        super().__init__(message)
        self.http_status = http_status
        self.body = body


class EkaAuthError(Exception):
    def __init__(self, message: str, http_status: int | None = None, body: str = ""):
        super().__init__(message)
        self.http_status = http_status
        self.body = body


_token_cache: dict[str, dict] = {}
_REFRESH_MARGIN_SECONDS = 60


def _login(config: Config) -> dict:
    """
    Confirmed against: https://developer.eka.care/api-reference/authorization/client-login
    POST /connect-auth/v1/account/login
    """
    url = f"{config.base_url}/connect-auth/v1/account/login"
    body = {"client_id": config.client_id, "client_secret": config.client_secret}
    resp = requests.post(url, json=body, timeout=30)
    if resp.status_code != 200:
        raise EkaAuthError(
            f"Login failed with status {resp.status_code}",
            http_status=resp.status_code, body=resp.text,
        )
    data = resp.json()
    access_token = data.get("access_token")
    expires_in = data.get("expires_in", 3600)
    if not access_token:
        raise EkaAuthError("Login response did not contain an access_token", body=resp.text)
    return {"access_token": access_token, "expires_at": time.time() + expires_in}


# def get_auth_token(config: Config) -> str:
#     cached = _token_cache.get(config.client_id)
#     if cached and time.time() < cached["expires_at"] - _REFRESH_MARGIN_SECONDS:
#         return cached["access_token"]
#     token_data = _login(config)
#     _token_cache[config.client_id] = token_data
#     return token_data["access_token"]
def get_auth_token(config: Config, force_refresh: bool = False) -> str:
    cached = _token_cache.get(config.client_id)

    if (
        not force_refresh
        and cached
        and time.time() < cached["expires_at"] - _REFRESH_MARGIN_SECONDS
    ):
        return cached["access_token"]

    token_data = _login(config)

    _token_cache[config.client_id] = token_data

    return token_data["access_token"]


def link_care_context(config: Config, row: dict) -> requests.Response:
    """
    Confirmed against: https://developer.eka.care/api-reference/user-app/abdm-connect/care-contexts/link/hip-linking
    POST /abdm/v1/care-contexts/link
    Headers: X-Pt-Id, X-Partner-Pt-Id, X-Hip-Id, Authorization
    Body:    {abha_address, care_contexts[], oid, partner_user_id}
    """
    auth_token = get_auth_token(config)

    url = f"{config.base_url}/abdm/v1/care-contexts/link"
    headers = {
        "X-Pt-Id": row["eka_patient_id"],
        "X-Partner-Pt-Id": row["partner_patient_id"],
        "X-Hip-Id": row["hip_id"],
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    care_context = {
        "care_context_id": row["care_context_id"],
        "display": row["display"],
        "hi_type": row["hi_type"],
    }
    if row.get("hi_types_multi"):
        care_context["hi_types"] = [v.strip() for v in row["hi_types_multi"].split(",") if v.strip()]

    body = {
        "abha_address": row["abha_address"],
        "care_contexts": [care_context],
        "oid": row["eka_patient_id"],
        "partner_user_id": row["partner_patient_id"],
    }

    resp = requests.post(url, headers=headers, json=body, timeout=30)
    if resp.status_code == 202:
        return resp

    raise EkaLinkError(
        f"Link API call failed with status {resp.status_code}",
        http_status=resp.status_code, body=resp.text,
    )

def push_on_fetch_response(
    config: Config,
    row: dict,
    transaction_id: str,
    care_context_id: str,
    checksum: str,
    encrypted_content: str,
    hip_key_material,
    page_number: int = 1,
    page_count: int = 1,
) -> requests.Response:
    """
    Push encrypted FHIR data to the HIU after receiving
    abha.hip_data_fetch.

    Eka API:
        POST /abdm/v1/hip/care-context/data/on-fetch

    The `content` field must contain the ENCRYPTED FHIR Bundle.

    Flow:
        FHIR Bundle
            -> SHA-256 checksum of plaintext
            -> ECDH encryption
            -> encrypted_content
            -> send encrypted_content in `entries[].content`
    """

    auth_token = get_auth_token(config)

    url = (
        f"{config.base_url}"
        "/abdm/v1/hip/care-context/data/on-fetch"
    )

    headers = {
        "X-Pt-Id": row["eka_patient_id"],
        "X-Partner-Pt-Id": row["partner_patient_id"],
        "X-Hip-Id": row["hip_id"],
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    # Eka documentation requires `expiry` as a string,
    # but the documentation provided does not specify
    # the exact value/format to use.
    hip_key_expiry = os.environ.get(
        "EKA_HIP_KEY_EXPIRY",
        ""
    )

    body = {
        "entries": [
            {
                "care_context_id": care_context_id,

                # SHA-256 of the PLAINTEXT FHIR Bundle.
                # This is calculated BEFORE encryption.
                "checksum": checksum,

                # IMPORTANT:
                # This is the ENCRYPTED FHIR Bundle,
                # NOT the plaintext FHIR JSON.
                "content": encrypted_content,

                "media": "application/fhir+json",
            }
        ],

        # This is the HIP's newly generated key material.
        "key_information": {
            "crypto_alg": "ECDH",
            "curve": "Curve25519",
            "dh_public_key": {
                "expiry": hip_key_expiry,
                "key_value": hip_key_material.x509_public_key,
                "parameters": "Curve25519/32byte random key",
            },
            "nonce": hip_key_material.nonce,
        },

        # "page_count": page_count,
        # "page_number": page_number,

        # Must be the transaction_id received in
        # abha.hip_data_fetch.
        "transaction_id": transaction_id,
    }

    print()
    print("==============================================")
    print("SENDING ENCRYPTED FHIR DATA TO HIU")
    print("==============================================")
    print()

    print("Transaction ID :", transaction_id)
    print("Care Context   :", care_context_id)
    print("Checksum       :", checksum)
    print("Media          :", "application/fhir+json")
    print("Page Number    :", page_number)
    print("Page Count     :", page_count)
    print()

    print("Encrypted content length:", len(encrypted_content))
    print()

    try:
        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=30,
        )
    except requests.RequestException as e:
        raise EkaLinkError(
            f"Data On-Fetch request failed: {e}"
        ) from e

    print("HTTP STATUS:", response.status_code)
    print()

    if response.text:
        print("Eka Response:")
        print(response.text)
        print()

    if response.status_code in (200, 202):
        print("==============================================")
        print("FHIR DATA ACCEPTED BY EKA")
        print("==============================================")
        return response

    raise EkaLinkError(
        f"Data On-Fetch failed with status {response.status_code}",
        http_status=response.status_code,
        body=response.text,
    )

def update_hiu_keyset(config: Config, hiu_key_material) -> requests.Response:
    auth_token = get_auth_token(config)
    url = f"{config.base_url}/abdm/v1/hiu/keyset"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    body = {
        "public_key": hiu_key_material.x509_public_key,
        "nonce": hiu_key_material.nonce,
    }
    resp = requests.patch(url, headers=headers, json=body, timeout=30)
    if resp.status_code == 200:
        return resp
    raise EkaLinkError(
        f"HIU keyset update failed with status {resp.status_code}",
        http_status=resp.status_code, body=resp.text,
    )

# def push_on_fetch_response(config: Config, row: dict, transaction_id: str,
#                             care_context_id: str, checksum: str, encrypted_content: str,
#                             hip_key_material, page_number: int = 1, page_count: int = 1) -> requests.Response:
#     """
#     Confirmed against: https://developer.eka.care/api-reference/user-app/abdm-connect/care-contexts/data-on-fetch
#     POST /abdm/v1/hip/care-context/data/on-fetch
#     Headers: X-Pt-Id, X-Partner-Pt-Id, X-Hip-Id, Authorization
#     Body:    {entries: [{care_context_id, checksum, content, media}],
#               key_information, page_count, page_number, transaction_id}
#
#     IMPORTANT: key_information in the OUTGOING body must be YOUR (the
#     HIP's) own key material -- hip_key_material, generated fresh for this
#     exchange -- not the HIU's key_information from the incoming webhook.
#     Echoing the requester's own keys back to them would be meaningless;
#     they need YOUR public key + nonce to derive the shared secret on
#     their end.
#
#     checksum must be the SHA-256 of the PLAINTEXT bundle (see
#     encryption.calculate_checksum), computed BEFORE encryption -- not a
#     hash of the encrypted content, which the HIU has no way to verify
#     against anything.
#
#     One call per care context is fine here -- the API doesn't require
#     batching multiple care contexts into one request; page_count/
#     page_number exist for pagination within a single large payload, not
#     for combining unrelated care contexts.
#     """
#     auth_token = get_auth_token(config)
#
#     url = f"{config.base_url}/abdm/v1/hip/care-context/data/on-fetch"
#     headers = {
#         "X-Pt-Id": row["eka_patient_id"],
#         "X-Partner-Pt-Id": row["partner_patient_id"],
#         "X-Hip-Id": row["hip_id"],
#         "Authorization": f"Bearer {auth_token}",
#         "Content-Type": "application/json",
#     }
#     body = {
#         "entries": [{
#             "care_context_id": care_context_id,
#             "checksum": checksum,
#             "content": encrypted_content,
#             "media": "application/fhir+json",
#         }],
#         "key_information": {
#             "crypto_alg": "ECDH",
#             "curve": "Curve25519",
#             "dh_public_key": {
#                 "expiry": "",  # UNCONFIRMED format/requirement -- schema has it, docs don't specify
#                 "key_value": hip_key_material.x509_public_key,
#                 "parameters": "Curve25519/32byte random key",
#             },
#             "nonce": hip_key_material.nonce,
#         },
#         "page_count": page_count,
#         "page_number": page_number,
#         "transaction_id": transaction_id,
#     }
#
#     resp = requests.post(url, headers=headers, json=body, timeout=30)
#     if resp.status_code in (200, 202):
#         return resp
#
#     raise EkaLinkError(
#         f"Data On-Fetch failed with status {resp.status_code}",
#         http_status=resp.status_code, body=resp.text,
#     )