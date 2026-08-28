# """
# Thin wrapper around Eka Care's Link API (POST /abdm/v1/care-contexts/link).
#
# NOT runnable from this environment -- no network path to Eka's API domain
# here, and no real credentials. This is the real request shape per the
# abdm-m2-care-context-linking skill; wire in your actual base_url/auth
# before running it against sandbox.
#
# Confirm the exact auth mechanism (bearer token vs client_id/secret
# exchange) against Eka's console/docs before relying on the placeholder
# Authorization header below -- that part was not in the skill text you
# gave me, so don't trust it blindly.
# """
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
# # def link_care_context(config: Config, row: dict, auth_token: str) -> requests.Response:
# #     """
# #     row must already have care_context_id/display/hi_type filled in
# #     (i.e. generate_care_context() has run for this row).
# #
# #     Returns the raw response on 202. Raises EkaLinkError on anything else --
# #     caller is responsible for logging (see logging_utils.log_push_event)
# #     and updating the flat table (flat_table_manager.mark_link_sent /
# #     leaving link_request_status alone on failure so it can be retried).
# #     """
# #     url = f"{config.base_url}/abdm/v1/care-contexts/link"
# #     headers = {
# #         "X-Pt-Id": row["eka_patient_id"],
# #         "X-Partner-Pt-Id": row["partner_patient_id"],
# #         "X-Hip-Id": row["hip_id"],
# #         "Authorization": f"Bearer {auth_token}",   # confirm exact scheme before relying on this
# #         "Content-Type": "application/json",
# #     }
# #     care_context = {
# #         "care_context_id": row["care_context_id"],
# #         "display": row["display"],
# #     }
# #     if row.get("hi_types_multi"):
# #         care_context["hi_types"] = row["hi_types_multi"].split(",")
# #     else:
# #         care_context["hi_type"] = row["hi_type"]
# #
# #     body = {
# #         "abha_address": row["abha_address"],
# #         "care_contexts": [care_context],
# #     }
# #
# #     resp = requests.post(url, headers=headers, json=body, timeout=30)
# #
# #     if resp.status_code == 202:
# #         return resp
# #
# #     # Per earlier troubleshooting: a generic, ABDM-error-code-less 400 with
# #     # CloudFront-shaped headers is usually environment/auth-side, not a
# #     # payload problem. Surface the response headers so that's visible to
# #     # whoever reads the exception, rather than just the body.
# #     raise EkaLinkError(
# #         f"Link API call failed with status {resp.status_code}",
# #         http_status=resp.status_code,
# #         body=resp.text,
# #     )
#
# def link_care_context(config: Config, row: dict, auth_token: str) -> requests.Response:
#     """
#     Calls Eka Care's Care Context Link API.
#
#     row must already have:
#       - eka_patient_id
#       - partner_patient_id
#       - hip_id
#       - abha_address
#       - care_context_id
#       - display
#       - hi_type
#
#     Returns the raw response on HTTP 202.
#     Raises EkaLinkError for any other HTTP status.
#     """
#
#     url = f"{config.base_url}/abdm/v1/care-contexts/link"
#
#     headers = {
#         "X-Pt-Id": row["eka_patient_id"],
#         "X-Partner-Pt-Id": row["partner_patient_id"],
#         "X-Hip-Id": row["hip_id"],
#         "Authorization": f"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJFQ18xNzg1OTIzMDg0NDQ3MTEiLCJiLWlkIjoiNzE3ODU5MjMwNDM0MTUzNCIsImMtaWQiOiJFQ18xNzg1OTIzMDg0NDQ3MTEiLCJjYyI6eyJwZXgiOjE3ODY0OTI4MDAsInBzdCI6ImZhbHNlIn0sImV4cCI6MTc4NzgxNDMwNiwiaWF0IjoxNzg3ODEyNTA2LCJpZHAiOiJhcGkta2V5IiwiaXNzIjoiZW1yLmVrYS5jYXJlIiwib2lkIjoiMTc4NTk5NDY4MTYxODg4IiwicGV4IjoxNzg2NDkyODAwLCJwcyI6IkFQIiwicHN0IjoiZmFsc2UiLCJzY3AiOlsicHI6MGYiXSwidXVpZCI6ImIyYmUxOTIzLTE2ZjEtNDllYi05NGYwLTNhMDg0NDFkMTQzYSIsInctaWQiOiI3MTc4NTkyMzA0MzQxNTM0Iiwidy1uIjoiU1JNIE1lZGljYWwgQ29sbGVnZSJ9.LRfQxZg7waDq--6cOT0n-Ni1YZKACe-6-BMf88PvIlw",
#         "Content-Type": "application/json",
#     }
#
#     care_context = {
#         "care_context_id": row["care_context_id"],
#         "data": "",
#         "display": row["display"],
#         "hi_types": [row["hi_type"]],
#     }
#
#     if row.get("hi_types_multi"):
#         care_context["hi_types"] = [
#             value.strip()
#             for value in row["hi_types_multi"].split(",")
#             if value.strip()
#         ]
#
#     body = {
#         "abha_address": row["abha_address"],
#         "care_contexts": [care_context],
#         "oid": row["eka_patient_id"],
#         "partner_user_id": row["partner_patient_id"],
#     }
#
#     resp = requests.post(
#         url,
#         headers=headers,
#         json=body,
#         timeout=30,
#     )
#
#     if resp.status_code == 202:
#         return resp
#
#     # raise EkaLinkError(
#     #     f"Link API call failed with status {resp.status_code}",
#     #     http_status=resp.status_code,
#     #     body=resp.text,
#     #
#     # )
#
#     except eka_client.EkaLinkError as e:
#     log.log_push_event(
#         env=config.env,
#         row_id=args.row_id,
#         care_context_id=row["care_context_id"],
#         hi_type=row["hi_type"],
#         status="failed",
#         http_status=e.http_status,
#         error=str(e),
#     )
#
#     print(f"\nLink API call failed: {e}")
#     print(f"HTTP status: {e.http_status}")
#     print(f"Eka response body: {e.body}")
#
#     raise


# #ChatGPT
# """
# Thin wrapper around Eka Care's Care Context Link API.
#
# POST /abdm/v1/care-contexts/link
# """
#
# import requests
#
# from config import Config
#
#
# class EkaLinkError(Exception):
#     def __init__(
#         self,
#         message: str,
#         http_status: int | None = None,
#         body: str = "",
#     ):
#         super().__init__(message)
#         self.http_status = http_status
#         self.body = body
#
#
# def link_care_context(
#     config: Config,
#     row: dict,
#     auth_token: str,
# ) -> requests.Response:
#     """
#     Link a care context to the patient's ABHA address.
#
#     The FHIR data is intentionally NOT included here.
#     Eka allows the 'data' field to be omitted. In that case,
#     the HIP will receive abha.hip_data_fetch when an HIU
#     later requests the health data.
#     """
#
#     url = f"{config.base_url}/abdm/v1/care-contexts/link"
#
#     headers = {
#         "X-Pt-Id": row["eka_patient_id"],
#         "X-Partner-Pt-Id": row["partner_patient_id"],
#         "X-Hip-Id": row["hip_id"],
#         "Authorization": f"Bearer {auth_token}",
#         "Content-Type": "application/json",
#     }
#
#     # Build the care context
#     care_context = {
#         "care_context_id": row["care_context_id"],
#         "display": row["display"],
#         "hi_types": [row["hi_type"]],
#     }
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
#         "partner_user_id": row["partner_patient_id"],
#     }
#
#     # Make API request
#     resp = requests.post(
#         url,
#         headers=headers,
#         json=body,
#         timeout=30,
#     )
#
#     # Success
#     if resp.status_code == 202:
#         return resp
#
#     # Failure
#     raise EkaLinkError(
#         f"Link API call failed with status {resp.status_code}",
#         http_status=resp.status_code,
#         body=resp.text,
#     )


#Claude-updated
"""
Wraps Eka Care's API: login/token exchange + Link API + Phase 2 on-fetch.

Auth is now self-managed here: call get_auth_token(config) and it handles
login + in-memory caching + refresh before expiry. Callers never pass or
store a token themselves -- it's pulled from config.client_id/client_secret
on demand.

NOT runnable from this environment -- no network path to Eka's API domain
here. The request/response shapes below (login endpoint, field names) are
UNCONFIRMED -- I don't have Eka's actual login API doc. If you have a link
to it (same as the ECDH one), send it and I'll correct this to match
exactly rather than guessing.
"""
import time
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


# In-memory token cache, keyed by client_id so multiple configs (e.g.
# sandbox + prod in the same process) don't clobber each other's tokens.
_token_cache: dict[str, dict] = {}

# Refresh this many seconds before actual expiry, so a token never gets
# used right at the edge of expiring mid-request.
_REFRESH_MARGIN_SECONDS = 60


def _login(config: Config) -> dict:
    """
    Calls Eka's login/token endpoint using client_id + client_secret.

    UNCONFIRMED endpoint path and request/response field names -- this is
    a best-guess client_credentials-style shape. Confirm against Eka's
    real auth docs before trusting this in sandbox.
    """
    url = f"{config.base_url}/connect-auth/v1/account/login"
    body = {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }
    resp = requests.post(url, json=body, timeout=30)
    if resp.status_code != 200:
        raise EkaAuthError(
            f"Login failed with status {resp.status_code}",
            http_status=resp.status_code, body=resp.text,
        )
    data = resp.json()
    access_token = data.get("access_token")  # UNCONFIRMED field name
    expires_in = data.get("expires_in", 3600)  # UNCONFIRMED field name, default guess
    if not access_token:
        raise EkaAuthError("Login response did not contain an access_token", body=resp.text)

    return {
        "access_token": access_token,
        "expires_at": time.time() + expires_in,
    }


def get_auth_token(config: Config) -> str:
    """
    Returns a valid access token, logging in only when there's no cached
    token yet or the cached one is near expiry. This is what
    link_care_context() and push_on_fetch_response() call internally --
    you should not need to call this directly except to pre-warm the cache.
    """
    cached = _token_cache.get(config.client_id)
    if cached and time.time() < cached["expires_at"] - _REFRESH_MARGIN_SECONDS:
        return cached["access_token"]

    token_data = _login(config)
    _token_cache[config.client_id] = token_data
    return token_data["access_token"]


def link_care_context(config: Config, row: dict) -> requests.Response:
    """
    row must already have care_context_id/display/hi_type filled in
    (i.e. generate_care_context() has run for this row).

    Returns the raw response on 202. Raises EkaLinkError on anything else --
    caller is responsible for logging (see logging_utils.log_push_event)
    and updating the flat table (flat_table_manager.mark_link_sent /
    leaving link_request_status alone on failure so it can be retried).
    """
    auth_token = get_auth_token(config)

    url = f"{config.base_url}/abdm/v1/care-contexts/link"
    headers = {
        "X-Pt-Id": row["eka_patient_id"],
        # "X-Partner-Pt-Id": row["partner_patient_id"],
        "X-Hip-Id": row["hip_id"],
        "Authorization": f"Bearer {auth_token}",   # confirm exact scheme before relying on this
        "Content-Type": "application/json",
    }
    # care_context = {
    #     "care_context_id": row["care_context_id"],
    #     "display": row["display"],
    # }
    # if row.get("hi_types_multi"):
    #     care_context["hi_types"] = row["hi_types_multi"].split(",")
    # else:
    #     care_context["hi_type"] = row["hi_type"]
    #
    # body = {
    #     "abha_address": row["abha_address"],
    #     "care_contexts": [care_context],
    # }

    care_context = {
                "care_context_id": row["care_context_id"],
                "display": row["display"],
                "hi_types": [row["hi_type"]],
            }

    # If multiple HI types are provided, use them instead.
    if row.get("hi_types_multi"):
        care_context["hi_types"] = [
            value.strip()
            for value in row["hi_types_multi"].split(",")
            if value.strip()
        ]

    # Eka Care Link API request body
    body = {
        "abha_address": row["abha_address"],
        "care_contexts": [care_context],
        "oid": row["eka_patient_id"],
        # "partner_user_id": row["partner_patient_id"],
    }

    resp = requests.post(url, headers=headers, json=body, timeout=30)

    if resp.status_code == 202:
        return resp

    # Per earlier troubleshooting: a generic, ABDM-error-code-less 400 with
    # CloudFront-shaped headers is usually environment/auth-side, not a
    # payload problem. Surface the response headers so that's visible to
    # whoever reads the exception, rather than just the body.
    raise EkaLinkError(
        f"Link API call failed with status {resp.status_code}",
        http_status=resp.status_code,
        body=resp.text,
    )


# def push_on_fetch_response(config: Config,transaction_id: str,entries: list,key_information: dict,
#                            page_count: int = 1,page_number: int = 1) -> requests.Response:
#     """
#     Push encrypted care-context FHIR data to the HIU after receiving
#     abha.hip_data_fetch.
#
#     Eka API:
#         POST /abdm/v1/hip/care-context/data/on-fetch
#
#     The entries must contain:
#         care_context_id
#         checksum
#         content
#         media
#
#     key_information comes from the abha.hip_data_fetch webhook.
#     """
#
#     auth_token = get_auth_token(config)
#
#     url = (
#         f"{config.base_url}"
#         "/abdm/v1/hip/care-context/data/on-fetch"
#     )
#
#     headers = {
#         "X-Pt-Id": config.oid,
#         "X-Hip-Id": config.hip_id,
#         "Authorization": f"Bearer {auth_token}",
#         "Content-Type": "application/json",
#     }
#
#     body = {
#         "entries": entries,
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
#     if resp.status_code == 202:
#         return resp
#
#     raise EkaLinkError(
#         f"On-fetch API call failed with status {resp.status_code}",
#         http_status=resp.status_code,
#         body=resp.text,
#     )

def push_on_fetch_response(
    config: Config,
    transaction_id: str,
    care_context_id: str,
    encrypted_content: str,
    key_information: dict,
    checksum: str,
    page_number: int = 1,
    page_count: int = 1,
) -> requests.Response:

    auth_token = get_auth_token(config)

    url = (
        f"{config.base_url}"
        "/abdm/v1/hip/care-context/data/on-fetch"
    )

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    body = {
        "entries": [
            {
                "care_context_id": care_context_id,
                "checksum": checksum,
                "content": encrypted_content,
                "media": "application/fhir+json",
            }
        ],
        "key_information": key_information,
        "page_count": page_count,
        "page_number": page_number,
        "transaction_id": transaction_id,
    }

    resp = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=30,
    )

    if resp.status_code not in (200, 202):
        raise EkaLinkError(
            f"Data On-Fetch failed with status {resp.status_code}",
            http_status=resp.status_code,
            body=resp.text,
        )

    return resp