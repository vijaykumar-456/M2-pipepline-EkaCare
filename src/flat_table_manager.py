"""
Single source-of-truth manager for the master flat table.
CSV at data/master_flat_table.csv is the working data; export_to_xlsx.py
(in scripts/) produces the human-readable colored view on demand.

USAGE ORDER (per patient / per care context):
    1. add_or_update_identity_from_m1(...)   <- after M1 completes
    2. set_clinical_data(...)                <- you supply this (HIS)
    3. generate_care_context(...)            <- computes hi_type-based ID
    4. mark_link_sent(...)                   <- after calling Eka Link API
    5. mark_link_webhook_result(...)         <- after abha.link_care_context fires
   (Phase 2 functions come later, once M2 Phase 1 is proven stable.)
"""
import csv
import hashlib
import os
import uuid
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(_PROJECT_ROOT, "data", "master_flat_table.csv")

ALL_COLUMNS = [
    "record_id",
    "row_id", "patient_name", "gender", "year_of_birth", "mobile_number",
    "abha_address", "abha_number", "eka_patient_id",
    "partner_patient_id", "hip_id", "clinic_id", "source_event_type",
    "encounter_id", "encounter_date", "practitioner_name",
    "symptoms_text", "symptoms_snomed_code",
    "vitals_bp_systolic", "vitals_bp_diastolic", "vitals_pulse", "vitals_temp_c", "vitals_spo2",
    "examination_notes", "diagnosis_text", "diagnosis_snomed_code", "medical_history_text",
    "medication_name", "medication_dosage", "medication_frequency", "medication_duration_days",
    "lab_test_name", "lab_test_loinc_code", "lab_result_value",
    "allergy_text", "allergy_category", "advice_notes", "clinical_notes",
    "follow_up_date", "family_history_text",
    "document_type", "document_filename",
    "immunization_vaccine_name", "immunization_date",
    "hi_type", "hi_types_multi", "care_context_id", "display",
    "link_request_status", "link_status", "link_error", "linked_at",
    "consent_status", "consent_artifact_id", "hiu_id",
    "bundle_created_at", "bundle_transfer_status", "transfer_error",
]


# def _load_rows() -> dict:
#     if not os.path.exists(CSV_PATH):
#         return {}
#     with open(CSV_PATH, newline="") as f:
#         return {r["row_id"]: r for r in csv.DictReader(f)}

def _load_rows() -> dict:
    if not os.path.exists(CSV_PATH):
        return {}

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = {}

        for r in csv.DictReader(f):
            record_id = r.get("record_id", "").strip()

            if not record_id:
                # Backward compatibility for old rows
                record_id = _new_record_id(rows)
                r["record_id"] = record_id

            rows[record_id] = r

        return rows


def _save_rows(rows: dict):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS)
        writer.writeheader()
        for row in rows.values():
            writer.writerow({k: row.get(k, "") for k in ALL_COLUMNS})


# def get_row(row_id: str) -> dict:
#     rows = _load_rows()
#     if row_id not in rows:
#         raise ValueError(f"No row found for row_id={row_id}")
#     return rows[row_id]

def get_row(record_id: str) -> dict:
    rows = _load_rows()

    if record_id not in rows:
        raise ValueError(f"No row found for record_id={record_id}")

    return rows[record_id]

def _new_record_id(rows: dict) -> str:
    """
    Generate the next R001, R002, R003... record ID.
    """
    numbers = []

    for row in rows.values():
        record_id = row.get("record_id", "")

        if record_id.startswith("R"):
            try:
                numbers.append(int(record_id[1:]))
            except ValueError:
                pass

    next_number = max(numbers, default=0) + 1

    return f"R{next_number:03d}"

# def add_or_update_identity_from_m1(row_id: str, m1_json: dict) -> dict:
#     """STEP 1. Extracts Group A fields from an M1 response and writes them
#     into the row (creating it if new). Never touches Groups B/C/D.
#     Deliberately ignores profile_photo and token -- not needed here, and
#     the token is a short-lived credential that shouldn't be persisted."""
#     if "response" in m1_json and "data" in m1_json["response"]:
#         profile = m1_json["response"]["data"]["profile"]
#         oid = profile.get("oid")
#         health_ids = profile.get("health-ids") or []
#         abha_address = health_ids[0] if health_ids else None
#         abha_number = None
#         full_name = profile.get("fln") or profile.get("fn")
#         gender = profile.get("gen")
#         dob = profile.get("dob", "")
#         year_of_birth = dob.split("-")[0] if dob else None
#         mobile = profile.get("mobile")
#     else:
#         profile = m1_json.get("profile", {})
#         eka = m1_json.get("eka", {})
#         oid = eka.get("oid") or profile.get("oid")
#         abha_address = profile.get("abha_address")
#         abha_number = profile.get("abha_number")
#         full_name = profile.get("full_name")
#         gender = profile.get("gender")
#         year_of_birth = profile.get("year_of_birth")
#         mobile = profile.get("mobile")
#
#     missing = [k for k, v in {"oid": oid, "abha_address": abha_address, "full_name": full_name}.items() if not v]
#     if missing:
#         raise ValueError(f"M1 response is missing required field(s): {missing}")
#
#     rows = _load_rows()
#     row = rows.get(row_id, {c: "" for c in ALL_COLUMNS})
#     row.update({
#         "row_id": row_id, "patient_name": full_name, "gender": gender,
#         "year_of_birth": year_of_birth, "mobile_number": mobile,
#         "abha_address": abha_address, "abha_number": abha_number or row.get("abha_number", ""),
#         "eka_patient_id": oid,
#     })
#     rows[row_id] = row
#     _save_rows(rows)
#     return row


# def set_clinical_data(row_id: str, **fields) -> dict:
#     """STEP 2. You call this with whatever Group B fields you have for this
#     encounter -- pass only what applies to this hi_type, leave the rest out."""
#     rows = _load_rows()
#     if row_id not in rows:
#         raise ValueError(f"{row_id} has no identity data yet -- run step 1 first")
#     unknown = set(fields) - set(ALL_COLUMNS)
#     if unknown:
#         raise ValueError(f"Unknown column(s): {unknown}")
#     rows[row_id].update(fields)
#     _save_rows(rows)
#     return rows[row_id]

def add_or_update_identity_from_m1(row_id: str, m1_json: dict) -> dict:
    """
    STEP 1.

    Load/update patient identity from M1.

    row_id = patient ID, e.g. P001
    record_id = encounter record ID, e.g. R001/R002/R003

    IMPORTANT:
    This function NEVER creates a new encounter record for an
    existing patient.

    generate_care_context() is responsible for creating R001/R002/R003...
    """

    # ---------------------------------------------------------
    # Extract M1 data
    # ---------------------------------------------------------

    if "response" in m1_json and "data" in m1_json["response"]:
        profile = m1_json["response"]["data"]["profile"]

        oid = profile.get("oid")

        health_ids = profile.get("health-ids") or []
        abha_address = health_ids[0] if health_ids else None

        abha_number = None
        full_name = profile.get("fln") or profile.get("fn")
        gender = profile.get("gen")

        dob = profile.get("dob", "")
        year_of_birth = dob.split("-")[0] if dob else None

        mobile = profile.get("mobile")

    else:
        profile = m1_json.get("profile", {})
        eka = m1_json.get("eka", {})

        oid = eka.get("oid") or profile.get("oid")
        abha_address = profile.get("abha_address")
        abha_number = profile.get("abha_number")
        full_name = profile.get("full_name")
        gender = profile.get("gender")
        year_of_birth = profile.get("year_of_birth")
        mobile = profile.get("mobile")

    missing = [
        k for k, v in {
            "oid": oid,
            "abha_address": abha_address,
            "full_name": full_name,
        }.items()
        if not v
    ]

    if missing:
        raise ValueError(
            f"M1 response is missing required field(s): {missing}"
        )

    # Make OID a string.
    oid = str(oid).strip()

    # ---------------------------------------------------------
    # Load existing records
    # ---------------------------------------------------------

    rows = _load_rows()

    # ---------------------------------------------------------
    # Find ANY existing record belonging to P001
    # ---------------------------------------------------------

    existing_record_id = None
    existing_row = None

    for record_id, existing in rows.items():
        if existing.get("row_id") == row_id:
            existing_record_id = record_id
            existing_row = existing
            break

    # ---------------------------------------------------------
    # Patient already exists
    # Update identity ONLY.
    # DO NOT create another record.
    # ---------------------------------------------------------

    if existing_row is not None:

        existing_row.update({
            "row_id": row_id,
            "patient_name": full_name,
            "gender": gender,
            "year_of_birth": year_of_birth,
            "mobile_number": mobile,
            "abha_address": abha_address,
            "abha_number": abha_number or existing_row.get(
                "abha_number", ""
            ),
            "eka_patient_id": oid,
        })

        rows[existing_record_id] = existing_row

        _save_rows(rows)

        return existing_row

    # ---------------------------------------------------------
    # Patient does NOT exist.
    #
    # Create only the initial identity record.
    # generate_care_context() will create the actual encounter
    # record later.
    # ---------------------------------------------------------

    record_id = _new_record_id(rows)

    new_row = {
        c: ""
        for c in ALL_COLUMNS
    }

    new_row.update({
        "record_id": record_id,
        "row_id": row_id,
        "patient_name": full_name,
        "gender": gender,
        "year_of_birth": year_of_birth,
        "mobile_number": mobile,
        "abha_address": abha_address,
        "abha_number": abha_number or "",
        "eka_patient_id": oid,
    })

    rows[record_id] = new_row

    _save_rows(rows)

    return new_row



def set_clinical_data(record_id: str, **fields) -> dict:
    rows = _load_rows()

    if record_id not in rows:
        raise ValueError(
            f"{record_id} has no record yet"
        )

    unknown = set(fields) - set(ALL_COLUMNS)

    if unknown:
        raise ValueError(
            f"Unknown column(s): {unknown}"
        )

    rows[record_id].update(fields)

    _save_rows(rows)

    return rows[record_id]


_HI_TYPE_LABELS = {
    "OPConsultation": "OP Consultation", "Prescription": "Prescription",
    "DiagnosticReport": "Diagnostic Report", "DischargeSummary": "Discharge Summary",
    "ImmunizationRecord": "Immunization Record", "HealthDocumentRecord": "Health Document",
    "WellnessRecord": "Wellness Record",
}


# def generate_care_context(row_id: str, hi_type: str,
#                           # partner_patient_id: str,
#                            hip_id: str, encounter_id: str, encounter_date: str,
#                            clinic_id: str = "", hi_types_multi: str = "") -> dict:
#     """STEP 3. Deterministic care_context_id + display, written into Group C.
#     Same (partner_patient_id, encounter_id) ALWAYS produces the same
#     care_context_id -- this is what makes reruns idempotent."""
#     rows = _load_rows()
#     if row_id not in rows:
#         raise ValueError(f"{row_id} has no identity data yet -- run step 1 first")
#
#     # cc_id = f"cc-{hashlib.sha256(f'{encounter_id}'.encode()).hexdigest()[:16]}"
#     cc_id = f"cc-{uuid.uuid4().hex[:16]}"
#     try:
#         date_str = datetime.strptime(encounter_date, "%Y-%m-%d").strftime("%d %b %Y")
#     except ValueError:
#         date_str = encounter_date
#     display = f"{_HI_TYPE_LABELS.get(hi_type, hi_type)} - {date_str}"
#
#     rows[row_id].update({
#         # "partner_patient_id": partner_patient_id,
#         "hip_id": hip_id, "clinic_id": clinic_id,
#         "encounter_id": encounter_id, "encounter_date": encounter_date,
#         "hi_type": hi_type, "hi_types_multi": hi_types_multi,
#         "care_context_id": cc_id, "display": display,
#         "link_request_status": "ready_to_send",
#     })
#     _save_rows(rows)
#     return rows[row_id]

def generate_care_context(
    row_id: str,
    hi_type: str,
    hip_id: str,
    encounter_id: str,
    encounter_date: str,
    clinic_id: str = "",
    hi_types_multi: str = "",
) -> dict:
    """
    STEP 3.

    Creates a NEW record for each new encounter.

    Same patient (row_id) can therefore have multiple records:

        R001 -> P001 -> ENC-P001-001
        R002 -> P001 -> ENC-P001-002

    Each record gets its own unique care_context_id.
    """

    rows = _load_rows()

    # ---------------------------------------------------------
    # Check whether this patient + encounter already exists
    # ---------------------------------------------------------

    for existing in rows.values():

        if (
            existing.get("row_id") == row_id
            and existing.get("encounter_id") == encounter_id
        ):
            raise ValueError(
                f"Encounter already exists: "
                f"patient={row_id}, encounter={encounter_id}, "
                f"record_id={existing.get('record_id')}"
            )

    # ---------------------------------------------------------
    # Find patient identity from an existing record
    # ---------------------------------------------------------

    patient_row = None

    for existing in rows.values():

        if existing.get("row_id") == row_id:
            patient_row = existing
            break

    if patient_row is None:
        raise ValueError(
            f"{row_id} has no identity data yet -- run step 1 first"
        )

    # ---------------------------------------------------------
    # Create NEW record
    # ---------------------------------------------------------

    record_id = _new_record_id(rows)

    cc_id = f"cc-{uuid.uuid4().hex[:16]}"

    try:
        date_str = datetime.strptime(
            encounter_date,
            "%Y-%m-%d"
        ).strftime("%d %b %Y")

    except ValueError:
        date_str = encounter_date

    display = (
        f"{_HI_TYPE_LABELS.get(hi_type, hi_type)} "
        f"- {date_str}"
    )

    # ---------------------------------------------------------
    # Copy patient identity into the new encounter record
    # ---------------------------------------------------------

    new_row = {
        c: patient_row.get(c, "")
        for c in ALL_COLUMNS
    }

    # ---------------------------------------------------------
    # Set record-specific fields
    # ---------------------------------------------------------

    new_row.update({
        "record_id": record_id,

        # Same patient
        "row_id": row_id,

        # Encounter-specific
        "hip_id": hip_id,
        "clinic_id": clinic_id,
        "encounter_id": encounter_id,
        "encounter_date": encounter_date,

        # Health information type
        "hi_type": hi_type,
        "hi_types_multi": hi_types_multi,

        # NEW Care Context
        "care_context_id": cc_id,
        "display": display,

        # Link lifecycle
        "link_request_status": "ready_to_send",
        "link_status": "",
        "link_error": "",
        "linked_at": "",

        # Phase 2 fields must start empty
        "consent_status": "",
        "consent_artifact_id": "",
        "hiu_id": "",
        "bundle_created_at": "",
        "bundle_transfer_status": "",
        "transfer_error": "",
    })

    # ---------------------------------------------------------
    # Add NEW record instead of overwriting patient
    # ---------------------------------------------------------

    rows[record_id] = new_row

    _save_rows(rows)

    return new_row


# def mark_link_sent(row_id: str):
#     """STEP 4. Call right after your POST /care-contexts/link call returns
#     202. Does NOT mean linked yet -- that's the webhook (step 5)."""
#     rows = _load_rows()
#     rows[row_id]["link_request_status"] = "sent"
#     _save_rows(rows)

def mark_link_sent(record_id: str):
    rows = _load_rows()

    if record_id not in rows:
        raise ValueError(
            f"No record found for record_id={record_id}"
        )

    rows[record_id]["link_request_status"] = "sent"

    _save_rows(rows)


def mark_link_webhook_result(
    record_id: str,
    status: str,
    error: str = ""
):
    rows = _load_rows()

    if record_id not in rows:
        raise ValueError(
            f"No record found for record_id={record_id}"
        )

    rows[record_id].update({
        "link_status": status,
        "link_error": error,
        "linked_at": datetime.now(
            timezone.utc
        ).isoformat(),
    })

    _save_rows(rows)

# ---------------------------------------------------------------------------
# Phase 2 -- consent + bundle transfer (Group D). Only touch these once
# Phase 1 is stable: an HIU can only request a care context that's already
# LINKED, so link_status must be "LINKED" before any of this runs.
# ---------------------------------------------------------------------------

def find_row_by_care_context_id(care_context_id: str) -> dict:
    """HIU on-fetch requests arrive keyed by care_context_id, not row_id --
    this is how the webhook handler maps back to a row."""
    rows = _load_rows()
    for row in rows.values():
        if row.get("care_context_id") == care_context_id:
            return row
    raise ValueError(f"No row found for care_context_id={care_context_id}")


def set_consent(row_id: str, consent_status: str, consent_artifact_id: str = "",
                 hiu_id: str = "") -> dict:
    """Record the outcome of a consent check/grant. consent_status should
    be one of: granted / pending / revoked / denied.
    This does NOT check anything itself -- it's just the ledger write.
    The actual gate is check_consent_before_bundling() below."""
    rows = _load_rows()
    if row_id not in rows:
        raise ValueError(f"{row_id} has no identity data yet")
    rows[row_id].update({
        "consent_status": consent_status,
        "consent_artifact_id": consent_artifact_id,
        "hiu_id": hiu_id,
    })
    _save_rows(rows)
    return rows[row_id]


def check_consent_before_bundling(row_id: str) -> bool:
    """The hard gate. Returns True only if it's safe to build and send a
    bundle for this row. Called by the webhook handler before touching
    fhir_builder at all -- never build a bundle first and check after."""
    rows = _load_rows()
    row = rows.get(row_id)
    if not row:
        return False
    if row.get("link_status") != "LINKED":
        return False  # can't share data for a care context that isn't linked
    if row.get("consent_status") != "granted":
        return False
    if not row.get("consent_artifact_id"):
        return False  # granted status with no artifact ID is a data-integrity problem, not a pass
    return True


def mark_bundle_created(row_id: str) -> dict:
    rows = _load_rows()
    rows[row_id]["bundle_created_at"] = datetime.now(timezone.utc).isoformat()
    _save_rows(rows)
    return rows[row_id]


def mark_bundle_transferred(row_id: str, status: str, error: str = "") -> dict:
    """status should be 'sent' or 'failed'."""
    rows = _load_rows()
    rows[row_id].update({"bundle_transfer_status": status, "transfer_error": error})
    _save_rows(rows)
    return rows[row_id]
