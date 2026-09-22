import requests


class AbhaSessionError(Exception):
    pass


def _headers(config, client_token, row):
    """
    Headers required by Eka User Session APIs.
    """

    return {
        "Authorization": f"Bearer {client_token}",
        "Content-Type": "application/json",
        "X-Pt-Id": row["eka_patient_id"],
        "X-Partner-Pt-Id": row["partner_patient_id"],
        "X-Hip-Id": row["hip_id"],
    }


def get_session_status(config, client_token, row):
    """
    Check whether the ABHA Gateway user session is active.

    GET /abdm/v1/session/status
    """

    url = (
        f"{config.base_url}"
        "/abdm/v1/session/status"
    )

    headers = _headers(
        config,
        client_token,
        row,
    )

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    print()
    print("==============================================")
    print("ABHA USER SESSION STATUS")
    print("==============================================")
    print()

    print("HTTP STATUS:", response.status_code)

    try:
        result = response.json()
    except ValueError:
        result = {}

    print("Eka Response:")
    print(result)
    print()

    if response.status_code != 200:
        return False

    return bool(result.get("logged_in"))


def initiate_session(config, client_token, row):
    """
    Generate OTP for ABHA Gateway user session.

    POST /abdm/v1/session/init
    """

    url = (
        f"{config.base_url}"
        "/abdm/v1/session/init"
    )

    params = {
        "oid": row["eka_patient_id"]
    }

    headers = _headers(
        config,
        client_token,
        row,
    )

    payload = {
        "abha_address": row["abha_address"]
    }

    print()
    print("==============================================")
    print("GENERATING ABHA SESSION OTP")
    print("==============================================")
    print()

    print("ABHA Address:", row["abha_address"])

    response = requests.post(
        url,
        params=params,
        headers=headers,
        json=payload,
        timeout=30,
    )

    print("HTTP STATUS:", response.status_code)

    try:
        result = response.json()
    except ValueError:
        result = {}

    print("Eka Response:")
    print(result)
    print()

    if response.status_code != 200:
        raise AbhaSessionError(
            f"Session init failed: "
            f"{response.status_code} {response.text}"
        )

    txn_id = result.get("txn_id")

    if not txn_id:
        raise AbhaSessionError(
            "Session init did not return txn_id."
        )

    print("OTP generated successfully.")
    print("txn_id:", txn_id)

    return txn_id


def verify_session_otp(
    config,
    client_token,
    row,
    txn_id,
    otp,
):
    """
    Verify OTP and obtain ABHA user session token.

    POST /abdm/v1/session/verify
    """

    url = (
        f"{config.base_url}"
        "/abdm/v1/session/verify"
    )

    params = {
        "oid": row["eka_patient_id"]
    }

    headers = _headers(
        config,
        client_token,
        row,
    )

    payload = {
        "otp": otp,
        "txn_id": txn_id,
    }

    print()
    print("==============================================")
    print("VERIFYING ABHA SESSION OTP")
    print("==============================================")
    print()

    response = requests.post(
        url,
        params=params,
        headers=headers,
        json=payload,
        timeout=30,
    )

    print("HTTP STATUS:", response.status_code)

    try:
        result = response.json()
    except ValueError:
        result = {}

    # Never print the actual token.
    safe_result = dict(result)

    if "token" in safe_result:
        safe_result["token"] = "<hidden>"

    if "refresh_token" in safe_result:
        safe_result["refresh_token"] = "<hidden>"

    print("Eka Response:")
    print(safe_result)
    print()

    if response.status_code != 200:
        raise AbhaSessionError(
            f"Session verification failed: "
            f"{response.status_code} {response.text}"
        )

    user_token = result.get("token")

    if not user_token:
        raise AbhaSessionError(
            "Session verify did not return token."
        )

    print("ABHA USER SESSION CREATED.")
    print()

    return user_token


def get_or_create_user_session(
    config,
    client_token,
    row,
):
    """
    Return a valid ABHA Gateway user session token.

    Flow:

        STATUS
          ↓
        valid?
        /   \
      YES    NO
       ↓      ↓
     return  INIT
              ↓
             OTP
              ↓
           VERIFY
              ↓
        user session token
    """

    # --------------------------------------------------------
    # STEP 1 - Check existing session
    # --------------------------------------------------------

    try:
        logged_in = get_session_status(
            config,
            client_token,
            row,
        )
    except requests.RequestException as e:
        raise AbhaSessionError(
            f"Could not check session status: {e}"
        ) from e

    if logged_in:
        print()
        print("ABHA USER SESSION IS ACTIVE.")
        print("Continuing without OTP.")
        print()

        # IMPORTANT:
        #
        # The status API tells us the session exists,
        # but the actual token must be available to use.
        #
        # If your application does not persist the user token,
        # we must authenticate again.
        #
        # Therefore for this first implementation we
        # deliberately continue with OTP authentication.
        #
        print("Starting fresh user-session authentication.")
        print()

    # --------------------------------------------------------
    # STEP 2 - Generate OTP
    # --------------------------------------------------------

    txn_id = initiate_session(
        config,
        client_token,
        row,
    )

    # --------------------------------------------------------
    # STEP 3 - Ask user for OTP
    # --------------------------------------------------------

    print()
    print("==============================================")
    print("OTP REQUIRED")
    print("==============================================")
    print()

    otp = input(
        "Enter the OTP received on the patient's "
        "registered mobile: "
    ).strip()

    if not otp:
        raise AbhaSessionError(
            "OTP was not entered."
        )

    # --------------------------------------------------------
    # STEP 4 - Verify OTP
    # --------------------------------------------------------

    user_token = verify_session_otp(
        config,
        client_token,
        row,
        txn_id,
        otp,
    )

    return user_token