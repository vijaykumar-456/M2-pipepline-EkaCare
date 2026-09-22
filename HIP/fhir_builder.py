#chatgpt - updated code as per abdm compliant
"""
ABDM / NRCeS FHIR R4 Document Bundle Builder.

Builds document Bundles for the HI types used by this project:

    OPConsultation
    Prescription
    DiagnosticReport
    DischargeSummary
    HealthDocumentRecord
    ImmunizationRecord
    WellnessRecord

Input:
    data/master_flat_table.csv

Example:
    python src/fhir_builder.py R008

Output:
    data/bundles/<record_id>_<hi_type>_<care_context_id>.json

The builder creates:

    Composition
    Patient
    Practitioner
    Organization
    Encounter

plus the clinical resources required by the selected HI type.

IMPORTANT:
This is an ABDM/NRCeS-oriented builder. Final production acceptance
must still be checked using the exact NRCeS validator/profile version
configured for the ABDM environment.
"""

import base64
import csv
import html
import json
import mimetypes
import os
import sys
import uuid
from datetime import datetime, timezone


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

FHIR_BASE = "https://nrces.in/ndhm/fhir/r4/StructureDefinition"

SNOMED_SYSTEM = "http://snomed.info/sct"
LOINC_SYSTEM = "http://loinc.org"

OBSERVATION_CATEGORY_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/observation-category"
)

CONDITION_CATEGORY_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/condition-category"
)

ALLERGY_CLINICAL_STATUS_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical"
)

ALLERGY_VERIFICATION_STATUS_SYSTEM = (
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification"
)

IDENTIFIER_TYPE_SYSTEM = (
    "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-identifier-type-code"
)


# ---------------------------------------------------------------------
# Document profile definitions
#
# These profile URLs correspond to the current NRCeS ABDM R4
# document profiles used by the project.
# ---------------------------------------------------------------------

DOCUMENT_PROFILES = {
    "OPConsultation": {
        "profile": f"{FHIR_BASE}/OPConsultRecord",
        "code": "371530004",
        "display": "Clinical consultation report",
        "title": "OP Consultation Record",
    },
    "Prescription": {
        "profile": f"{FHIR_BASE}/PrescriptionRecord",
        "code": "440545006",
        "display": "Prescription record",
        "title": "Prescription",
    },
    "DiagnosticReport": {
        "profile": f"{FHIR_BASE}/DiagnosticReportRecord",
        "code": "721981007",
        "display": "Diagnostic report - laboratory",
        "title": "Diagnostic Report",
    },
    "DischargeSummary": {
        "profile": f"{FHIR_BASE}/DischargeSummaryRecord",
        "code": "373942005",
        "display": "Discharge summary",
        "title": "Discharge Summary",
    },
    "HealthDocumentRecord": {
        "profile": f"{FHIR_BASE}/HealthDocumentRecord",
        "code": "419891008",
        "display": "Record artifact",
        "title": "Health Document Record",
    },
    "ImmunizationRecord": {
        "profile": f"{FHIR_BASE}/ImmunizationRecord",
        "code": "41000179103",
        "display": "Immunization record",
        "title": "Immunization Record",
    },
    "WellnessRecord": {
        "profile": f"{FHIR_BASE}/WellnessRecord",
        "code": None,
        "display": "Wellness Record",
        "title": "Wellness Record",
    },
}


RESOURCE_PROFILES = {
    "Patient": f"{FHIR_BASE}/Patient",
    "Practitioner": f"{FHIR_BASE}/Practitioner",
    "PractitionerRole": f"{FHIR_BASE}/PractitionerRole",
    "Organization": f"{FHIR_BASE}/Organization",
    "Encounter": f"{FHIR_BASE}/Encounter",
    "Observation": f"{FHIR_BASE}/Observation",
    "Condition": f"{FHIR_BASE}/Condition",
    "MedicationRequest": f"{FHIR_BASE}/MedicationRequest",
    "AllergyIntolerance": f"{FHIR_BASE}/AllergyIntolerance",
    "Procedure": f"{FHIR_BASE}/Procedure",
    "ServiceRequest": f"{FHIR_BASE}/ServiceRequest",
    "DiagnosticReport": f"{FHIR_BASE}/DiagnosticReportLab",
    "DocumentReference": f"{FHIR_BASE}/DocumentReference",
    "Immunization": f"{FHIR_BASE}/Immunization",
    "Appointment": f"{FHIR_BASE}/Appointment",
    "FamilyMemberHistory": f"{FHIR_BASE}/FamilyMemberHistory",
}


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def _uuid():
    return str(uuid.uuid4())


def _urn():
    return f"urn:uuid:{_uuid()}"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _has(value):
    return bool(_clean(value))


def _date(value):
    """
    Converts YYYY-MM-DD or ISO date/time to an FHIR-friendly date.
    """
    value = _clean(value)

    if not value:
        return ""

    if "T" in value:
        return value.split("T", 1)[0]

    return value[:10]


def _datetime(value):
    """
    Converts a date into an ISO datetime if necessary.
    """
    value = _clean(value)

    if not value:
        return _now_iso()

    if "T" in value:
        return value

    return f"{value}T00:00:00+05:30"


def _year_to_birth_date(year):
    year = _clean(year)

    if not year:
        return ""

    if len(year) == 4 and year.isdigit():
        return f"{year}-01-01"

    return year


def _reference(url):
    return {
        "reference": url
    }


def _coding(system, code, display=None):
    item = {
        "system": system,
        "code": code,
    }

    if display:
        item["display"] = display

    return item


def _codeable(system, code, display=None, text=None):
    result = {}

    if system and code:
        result["coding"] = [
            _coding(system, code, display)
        ]

    if text:
        result["text"] = text

    return result


def _profile(resource_type):
    profile = RESOURCE_PROFILES.get(resource_type)

    if not profile:
        return None

    return profile


def _meta(resource_type, extra_profiles=None):
    profiles = []

    profile = _profile(resource_type)

    if profile:
        profiles.append(profile)

    if extra_profiles:
        profiles.extend(extra_profiles)

    result = {
        "profile": profiles
    }

    return result


def _narrative(resource_type, title, text):
    safe = html.escape(_clean(text))

    if not safe:
        safe = html.escape(title)

    return {
        "status": "generated",
        "div": (
            f'<div xmlns="http://www.w3.org/1999/xhtml">'
            f"<p><b>{html.escape(resource_type)}</b></p>"
            f"<p>{safe}</p>"
            f"</div>"
        )
    }


def _resource_entry(resource, url=None):
    if url is None:
        url = _urn()

    resource["id"] = url.split(":")[-1]

    return {
        "fullUrl": url,
        "resource": resource,
    }


# ---------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------

def _build_patient(row, url):
    patient = {
        "resourceType": "Patient",
        "meta": _meta("Patient"),
        "text": _narrative(
            "Patient",
            "Patient",
            row.get("patient_name", ""),
        ),
        "identifier": [],
        "name": [],
    }

    abha_address = _clean(row.get("abha_address"))

    if abha_address:
        patient["identifier"].append({
            "type": _codeable(
                IDENTIFIER_TYPE_SYSTEM,
                "ABHA",
                "Ayushman Bharat Health Account (ABHA) ID",
            ),
            "value": abha_address,
        })

    abha_number = _clean(row.get("abha_number"))

    if abha_number:
        patient["identifier"].append({
            "value": abha_number,
        })

    name = _clean(row.get("patient_name"))

    if name:
        patient["name"].append({
            "text": name,
        })

    gender = {
        "M": "male",
        "F": "female",
        "O": "other",
    }.get(
        _clean(row.get("gender")).upper(),
        "unknown",
    )

    patient["gender"] = gender

    birth_date = _year_to_birth_date(
        row.get("year_of_birth")
    )

    if birth_date:
        patient["birthDate"] = birth_date

    mobile = _clean(row.get("mobile_number"))

    if mobile:
        patient["telecom"] = [{
            "system": "phone",
            "value": mobile,
            "use": "mobile",
        }]

    return _resource_entry(patient, url)


# ---------------------------------------------------------------------
# Practitioner
# ---------------------------------------------------------------------

def _build_practitioner(row, url):
    practitioner_name = _clean(
        row.get("practitioner_name")
    )

    practitioner = {
        "resourceType": "Practitioner",
        "meta": _meta("Practitioner"),
        "text": _narrative(
            "Practitioner",
            "Practitioner",
            practitioner_name or "Practitioner",
        ),
        "name": [{
            "text": practitioner_name or "Practitioner"
        }],
    }

    return _resource_entry(
        practitioner,
        url,
    )


# ---------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------

def _build_organization(row, url):
    facility_name = (
        _clean(row.get("clinic_id"))
        or _clean(row.get("hip_id"))
        or "HIP"
    )

    organization = {
        "resourceType": "Organization",
        "meta": _meta("Organization"),
        "text": _narrative(
            "Organization",
            "Healthcare facility",
            facility_name,
        ),
        "identifier": [],
        "name": facility_name,
    }

    hip_id = _clean(row.get("hip_id"))

    if hip_id:
        organization["identifier"].append({
            "value": hip_id,
        })

    return _resource_entry(
        organization,
        url,
    )


# ---------------------------------------------------------------------
# Encounter
# ---------------------------------------------------------------------

def _build_encounter(row, url, patient_url, practitioner_url=None,
                     organization_url=None):
    encounter_id = _clean(row.get("encounter_id"))

    encounter = {
        "resourceType": "Encounter",
        "meta": _meta("Encounter"),
        "text": _narrative(
            "Encounter",
            "Encounter",
            encounter_id or "Clinical encounter",
        ),
        "identifier": [],
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "subject": _reference(patient_url),
    }

    if encounter_id:
        encounter["identifier"].append({
            "value": encounter_id,
        })

    encounter_date = _date(
        row.get("encounter_date")
    )

    if encounter_date:
        encounter["period"] = {
            "start": encounter_date
        }

    if practitioner_url:
        encounter["participant"] = [{
            "individual": _reference(
                practitioner_url
            )
        }]

    if organization_url:
        encounter["serviceProvider"] = _reference(
            organization_url
        )

    return _resource_entry(
        encounter,
        url,
    )


# ---------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------

def _observation(
    row,
    url,
    patient_url,
    encounter_url,
    code,
    display,
    value=None,
    unit=None,
    category=None,
    text=None,
):
    resource = {
        "resourceType": "Observation",
        "meta": _meta("Observation"),
        "status": "final",
        "code": _codeable(
            LOINC_SYSTEM if code else None,
            code,
            display,
            text or display,
        ),
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
    }

    if category:
        resource["category"] = [{
            "coding": [{
                "system": OBSERVATION_CATEGORY_SYSTEM,
                "code": category,
            }]
        }]

    if value is not None and _has(value):
        numeric = False

        try:
            numeric_value = float(
                str(value).strip()
            )
            numeric = True
        except (TypeError, ValueError):
            numeric_value = None

        if numeric and unit:
            resource["valueQuantity"] = {
                "value": numeric_value,
                "unit": unit,
            }
        else:
            resource["valueString"] = _clean(
                value
            )

    resource["effectiveDateTime"] = _datetime(
        row.get("encounter_date")
    )

    resource["text"] = _narrative(
        "Observation",
        display,
        _clean(value) or display,
    )

    return _resource_entry(
        resource,
        url,
    )


def _build_vital_observations(
    row,
    patient_url,
    encounter_url,
):
    result = []

    vitals = [
        (
            "vitals_bp_systolic",
            "8480-6",
            "Systolic blood pressure",
            "mmHg",
        ),
        (
            "vitals_bp_diastolic",
            "8462-4",
            "Diastolic blood pressure",
            "mmHg",
        ),
        (
            "vitals_pulse",
            "8867-4",
            "Heart rate",
            "beats/min",
        ),
        (
            "vitals_temp_c",
            "8310-5",
            "Body temperature",
            "Cel",
        ),
        (
            "vitals_spo2",
            "59408-5",
            "Oxygen saturation",
            "%",
        ),
    ]

    for field, code, display, unit in vitals:

        value = row.get(field)

        if not _has(value):
            continue

        result.append(
            _observation(
                row,
                _urn(),
                patient_url,
                encounter_url,
                code,
                display,
                value,
                unit,
                "vital-signs",
            )
        )

    return result


# ---------------------------------------------------------------------
# Symptoms
# ---------------------------------------------------------------------

def _build_symptom(row, patient_url, encounter_url):
    text = _clean(
        row.get("symptoms_text")
    )

    code = _clean(
        row.get("symptoms_snomed_code")
    )

    if not text:
        return None

    resource = {
        "resourceType": "Observation",
        "meta": _meta("Observation"),
        "status": "final",
        "category": [{
            "coding": [{
                "system": OBSERVATION_CATEGORY_SYSTEM,
                "code": "exam",
                "display": "Exam",
            }]
        }],
        "code": _codeable(
            SNOMED_SYSTEM if code else None,
            code,
            None,
            text,
        ),
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "effectiveDateTime": _datetime(
            row.get("encounter_date")
        ),
        "valueString": text,
        "text": _narrative(
            "Observation",
            "Chief complaint / symptom",
            text,
        ),
    }

    return _resource_entry(
        resource,
        _urn(),
    )


# ---------------------------------------------------------------------
# Examination
# ---------------------------------------------------------------------

def _build_examination(row, patient_url, encounter_url):
    text = _clean(
        row.get("examination_notes")
    )

    if not text:
        return None

    resource = {
        "resourceType": "Observation",
        "meta": _meta("Observation"),
        "status": "final",
        "category": [{
            "coding": [{
                "system": OBSERVATION_CATEGORY_SYSTEM,
                "code": "exam",
                "display": "Exam",
            }]
        }],
        "code": {
            "text": "Physical examination findings"
        },
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "effectiveDateTime": _datetime(
            row.get("encounter_date")
        ),
        "valueString": text,
        "text": _narrative(
            "Observation",
            "Examination",
            text,
        ),
    }

    return _resource_entry(
        resource,
        _urn(),
    )


# ---------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------

def _build_diagnosis(row, patient_url, encounter_url):
    text = _clean(
        row.get("diagnosis_text")
    )

    code = _clean(
        row.get("diagnosis_snomed_code")
    )

    if not text:
        return None

    condition = {
        "resourceType": "Condition",
        "meta": _meta("Condition"),
        "text": _narrative(
            "Condition",
            "Diagnosis",
            text,
        ),
        "clinicalStatus": {
            "coding": [{
                "system": (
                    "http://terminology.hl7.org/"
                    "CodeSystem/condition-clinical"
                ),
                "code": "active",
            }]
        },
        "category": [{
            "coding": [{
                "system": CONDITION_CATEGORY_SYSTEM,
                "code": "encounter-diagnosis",
            }]
        }],
        "code": _codeable(
            SNOMED_SYSTEM if code else None,
            code,
            None,
            text,
        ),
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
    }

    return _resource_entry(
        condition,
        _urn(),
    )


# ---------------------------------------------------------------------
# Medical history
# ---------------------------------------------------------------------

def _build_medical_history(row, patient_url, encounter_url):
    text = _clean(
        row.get("medical_history_text")
    )

    if not text:
        return None

    condition = {
        "resourceType": "Condition",
        "meta": _meta("Condition"),
        "text": _narrative(
            "Condition",
            "Medical history",
            text,
        ),
        "category": [{
            "coding": [{
                "system": CONDITION_CATEGORY_SYSTEM,
                "code": "problem-list-item",
            }]
        }],
        "code": {
            "text": text
        },
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
    }

    return _resource_entry(
        condition,
        _urn(),
    )


# ---------------------------------------------------------------------
# Allergy
# ---------------------------------------------------------------------

def _build_allergy(row, patient_url, encounter_url):
    allergy_text = _clean(
        row.get("allergy_text")
    )

    if not allergy_text:
        return None

    category = _clean(
        row.get("allergy_category")
    ).lower()

    valid_categories = {
        "food",
        "medication",
        "environment",
        "biologic",
    }

    if category not in valid_categories:
        category = "medication"

    allergy = {
        "resourceType": "AllergyIntolerance",
        "meta": _meta("AllergyIntolerance"),
        "text": _narrative(
            "AllergyIntolerance",
            "Allergy",
            allergy_text,
        ),
        "clinicalStatus": {
            "coding": [{
                "system": ALLERGY_CLINICAL_STATUS_SYSTEM,
                "code": "active",
            }]
        },
        "verificationStatus": {
            "coding": [{
                "system": ALLERGY_VERIFICATION_STATUS_SYSTEM,
                "code": "confirmed",
            }]
        },
        "category": [
            category
        ],
        "patient": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "code": {
            "text": allergy_text
        },
    }

    return _resource_entry(
        allergy,
        _urn(),
    )


# ---------------------------------------------------------------------
# Medication
# ---------------------------------------------------------------------

def _frequency_from_text(text):
    value = _clean(text).lower()

    mapping = {
        "once daily": 1,
        "once a day": 1,
        "daily": 1,
        "od": 1,
        "twice daily": 2,
        "twice a day": 2,
        "bid": 2,
        "thrice daily": 3,
        "three times daily": 3,
        "three times a day": 3,
        "tid": 3,
        "four times daily": 4,
        "qid": 4,
    }

    return mapping.get(value)


def _build_medication_request(
    row,
    patient_url,
    encounter_url,
):
    medicine = _clean(
        row.get("medication_name")
    )

    if not medicine:
        return None

    dosage = _clean(
        row.get("medication_dosage")
    )

    frequency_text = _clean(
        row.get("medication_frequency")
    )

    duration = _clean(
        row.get("medication_duration_days")
    )

    dosage_text = " ".join(
        x for x in [
            dosage,
            frequency_text,
        ]
        if x
    )

    dosage_instruction = {
        "text": dosage_text or medicine
    }

    frequency = _frequency_from_text(
        frequency_text
    )

    duration_number = None

    if duration:
        try:
            duration_number = int(float(duration))
        except ValueError:
            duration_number = None

    repeat = {}

    if frequency is not None:
        repeat["frequency"] = frequency
        repeat["period"] = 1
        repeat["periodUnit"] = "d"

    if duration_number is not None:
        repeat["duration"] = duration_number
        repeat["durationUnit"] = "d"

    if repeat:
        dosage_instruction["timing"] = {
            "repeat": repeat
        }

    medication = {
        "resourceType": "MedicationRequest",
        "meta": _meta("MedicationRequest"),
        "text": _narrative(
            "MedicationRequest",
            "Medication",
            dosage_text or medicine,
        ),
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "text": medicine
        },
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "authoredOn": _date(
            row.get("encounter_date")
        ) or _date(
            row.get("follow_up_date")
        ),
        "dosageInstruction": [
            dosage_instruction
        ],
    }

    return _resource_entry(
        medication,
        _urn(),
    )


# ---------------------------------------------------------------------
# Advice
# ---------------------------------------------------------------------

def _build_advice(row, patient_url, encounter_url):
    advice = _clean(
        row.get("advice_notes")
    )

    if not advice:
        return None

    care_plan = {
        "resourceType": "CarePlan",
        "status": "active",
        "intent": "plan",
        "text": _narrative(
            "CarePlan",
            "Advice",
            advice,
        ),
        "description": advice,
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
    }

    return _resource_entry(
        care_plan,
        _urn(),
    )


# ---------------------------------------------------------------------
# Clinical notes
# ---------------------------------------------------------------------

def _build_clinical_notes(
    row,
    patient_url,
    encounter_url,
):
    notes = _clean(
        row.get("clinical_notes")
    )

    if not notes:
        return None

    care_plan = {
        "resourceType": "CarePlan",
        "status": "active",
        "intent": "proposal",
        "text": _narrative(
            "CarePlan",
            "Clinical notes",
            notes,
        ),
        "description": notes,
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
    }

    return _resource_entry(
        care_plan,
        _urn(),
    )


# ---------------------------------------------------------------------
# Follow-up
# ---------------------------------------------------------------------

def _build_followup(
    row,
    patient_url,
    practitioner_url,
):
    followup = _date(
        row.get("follow_up_date")
    )

    if not followup:
        return None

    appointment = {
        "resourceType": "Appointment",
        "meta": _meta("Appointment"),
        "text": _narrative(
            "Appointment",
            "Follow-up appointment",
            followup,
        ),
        "status": "proposed",
        "appointmentType": {
            "text": "Follow-up"
        },
        "start": _datetime(followup),
        "participant": [{
            "actor": _reference(patient_url),
            "status": "accepted",
        }],
    }

    if practitioner_url:
        appointment["participant"].append({
            "actor": _reference(
                practitioner_url
            ),
            "status": "accepted",
        })

    return _resource_entry(
        appointment,
        _urn(),
    )


# ---------------------------------------------------------------------
# Procedure
# ---------------------------------------------------------------------

def _build_procedure_from_notes(
    row,
    patient_url,
    encounter_url,
):
    notes = _clean(
        row.get("examination_notes")
    )

    if not notes:
        return None

    procedure = {
        "resourceType": "Procedure",
        "meta": _meta("Procedure"),
        "status": "completed",
        "code": {
            "text": "Clinical examination"
        },
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "performedDateTime": _datetime(
            row.get("encounter_date")
        ),
        "note": [{
            "text": notes
        }],
    }

    return _resource_entry(
        procedure,
        _urn(),
    )


# ---------------------------------------------------------------------
# Service Request
# ---------------------------------------------------------------------

def _build_lab_service_request(
    row,
    patient_url,
    encounter_url,
):
    lab_name = _clean(
        row.get("lab_test_name")
    )

    if not lab_name:
        return None

    lab_code = _clean(
        row.get("lab_test_loinc_code")
    )

    request = {
        "resourceType": "ServiceRequest",
        "meta": _meta("ServiceRequest"),
        "status": "completed",
        "intent": "order",
        "code": _codeable(
            LOINC_SYSTEM if lab_code else None,
            lab_code,
            None,
            lab_name,
        ),
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "authoredOn": _date(
            row.get("encounter_date")
        ) or _date(
            row.get("immunization_date")
        ),
    }

    return _resource_entry(
        request,
        _urn(),
    )


# ---------------------------------------------------------------------
# Diagnostic result Observation
# ---------------------------------------------------------------------

def _build_lab_result(
    row,
    patient_url,
    encounter_url,
):
    lab_name = _clean(
        row.get("lab_test_name")
    )

    result_value = _clean(
        row.get("lab_result_value")
    )

    if not lab_name and not result_value:
        return None

    lab_code = _clean(
        row.get("lab_test_loinc_code")
    )

    observation = {
        "resourceType": "Observation",
        "meta": _meta("Observation"),
        "status": "final",
        "code": _codeable(
            LOINC_SYSTEM if lab_code else None,
            lab_code,
            None,
            lab_name or "Laboratory result",
        ),
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "effectiveDateTime": _datetime(
            row.get("encounter_date")
        ),
        "text": _narrative(
            "Observation",
            lab_name or "Laboratory result",
            result_value or lab_name,
        ),
    }

    if result_value:
        observation["valueString"] = result_value

    return _resource_entry(
        observation,
        _urn(),
    )


# ---------------------------------------------------------------------
# DiagnosticReport
# ---------------------------------------------------------------------

def _build_diagnostic_report(
    row,
    patient_url,
    encounter_url,
    result_urls,
):
    lab_name = _clean(
        row.get("lab_test_name")
    ) or "Laboratory diagnostic report"

    report = {
        "resourceType": "DiagnosticReport",
        "meta": {
            "profile": [
                f"{FHIR_BASE}/DiagnosticReportLab"
            ]
        },
        "text": _narrative(
            "DiagnosticReport",
            "Diagnostic Report",
            lab_name,
        ),
        "status": "final",
        "category": [{
            "coding": [{
                "system": (
                    "http://terminology.hl7.org/"
                    "CodeSystem/v2-0074"
                ),
                "code": "LAB",
                "display": "Laboratory",
            }]
        }],
        "code": _codeable(
            LOINC_SYSTEM
            if _has(row.get("lab_test_loinc_code"))
            else None,
            _clean(row.get("lab_test_loinc_code")),
            None,
            lab_name,
        ),
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "effectiveDateTime": _datetime(
            row.get("encounter_date")
        ),
        "issued": _now_iso(),
    }

    if result_urls:
        report["result"] = [
            _reference(url)
            for url in result_urls
        ]

    return _resource_entry(
        report,
        _urn(),
    )


# ---------------------------------------------------------------------
# Document attachment
# ---------------------------------------------------------------------

def _document_reference(
    row,
    patient_url,
    encounter_url,
    document_type,
):
    filename = _clean(
        row.get("document_filename")
    )

    document_type_text = _clean(
        row.get("document_type")
    ) or document_type

    if not filename and not document_type_text:
        return None

    attachment = {
        "contentType": "application/octet-stream",
    }

    if filename:
        attachment["title"] = filename

        content_type, _ = mimetypes.guess_type(
            filename
        )

        if content_type:
            attachment["contentType"] = content_type

        project_root = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )

        possible_paths = [
            os.path.join(
                project_root,
                "data",
                filename,
            ),
            os.path.join(
                project_root,
                "data",
                "documents",
                filename,
            ),
        ]

        for path in possible_paths:

            if os.path.exists(path):

                with open(
                    path,
                    "rb"
                ) as f:
                    encoded = base64.b64encode(
                        f.read()
                    ).decode("ascii")

                attachment["data"] = encoded
                break

    document = {
        "resourceType": "DocumentReference",
        "meta": _meta("DocumentReference"),
        "text": _narrative(
            "DocumentReference",
            document_type_text,
            filename or document_type_text,
        ),
        "status": "current",
        "type": {
            "text": document_type_text
        },
        "subject": _reference(patient_url),
        "date": _datetime(
            row.get("encounter_date")
        ),
        "content": [{
            "attachment": attachment
        }],
    }

    if encounter_url:
        document["context"] = {
            "encounter": [
                _reference(encounter_url)
            ]
        }

    return _resource_entry(
        document,
        _urn(),
    )


# ---------------------------------------------------------------------
# Immunization
# ---------------------------------------------------------------------

def _build_immunization(
    row,
    patient_url,
    encounter_url,
):
    vaccine = _clean(
        row.get("immunization_vaccine_name")
    )

    if not vaccine:
        return None

    immunization = {
        "resourceType": "Immunization",
        "meta": _meta("Immunization"),
        "text": _narrative(
            "Immunization",
            "Immunization",
            vaccine,
        ),
        "status": "completed",
        "vaccineCode": {
            "text": vaccine
        },
        "patient": _reference(patient_url),
        "occurrenceDateTime": _datetime(
            row.get("immunization_date")
            or row.get("encounter_date")
        ),
    }

    if encounter_url:
        immunization["encounter"] = _reference(
            encounter_url
        )

    return _resource_entry(
        immunization,
        _urn(),
    )


# ---------------------------------------------------------------------
# Family history
# ---------------------------------------------------------------------

def _build_family_history(
    row,
    patient_url,
):
    history = _clean(
        row.get("family_history_text")
    )

    if not history:
        return None

    family = {
        "resourceType": "FamilyMemberHistory",
        "meta": _meta("FamilyMemberHistory"),
        "status": "completed",
        "patient": _reference(patient_url),
        "text": _narrative(
            "FamilyMemberHistory",
            "Family history",
            history,
        ),
        "note": [{
            "text": history
        }],
    }

    return _resource_entry(
        family,
        _urn(),
    )


# ---------------------------------------------------------------------
# Composition section helper
# ---------------------------------------------------------------------

def _section(
    title,
    entries,
    code=None,
    display=None,
):
    section = {
        "title": title,
        "entry": [
            _reference(url)
            for url in entries
        ],
    }

    if code:
        section["code"] = {
            "coding": [{
                "system": SNOMED_SYSTEM,
                "code": code,
                "display": display or title,
            }],
            "text": title,
        }
    else:
        section["code"] = {
            "text": title
        }

    return section


# ---------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------

def _build_composition(
    row,
    hi_type,
    composition_url,
    patient_url,
    encounter_url,
    practitioner_url,
    organization_url,
    sections,
):
    info = DOCUMENT_PROFILES[hi_type]

    composition = {
        "resourceType": "Composition",
        "meta": {
            "profile": [
                info["profile"]
            ]
        },
        "language": "en-IN",
        "status": "final",
        "type": {},
        "subject": _reference(patient_url),
        "encounter": _reference(encounter_url),
        "date": _now_iso(),
        "author": [
            _reference(practitioner_url)
        ],
        "title": info["title"],
        "section": sections,
    }

    if info["code"]:
        composition["type"] = {
            "coding": [{
                "system": SNOMED_SYSTEM,
                "code": info["code"],
                "display": info["display"],
            }],
            "text": info["display"],
        }
    else:
        composition["type"] = {
            "text": info["display"]
        }

    composition["custodian"] = _reference(
        organization_url
    )

    composition["text"] = _narrative(
        "Composition",
        info["title"],
        row.get("display")
        or info["title"],
    )

    return _resource_entry(
        composition,
        composition_url,
    )


# ---------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------

def build_bundle(row):
    """
    Build one ABDM document Bundle from one flat-table record.
    """

    hi_type = _clean(
        row.get("hi_type")
    )

    if hi_type not in DOCUMENT_PROFILES:
        raise ValueError(
            f"Unsupported hi_type: {hi_type}. "
            f"Supported: {', '.join(DOCUMENT_PROFILES)}"
        )

    patient_url = _urn()
    practitioner_url = _urn()
    organization_url = _urn()
    encounter_url = _urn()
    composition_url = _urn()

    entries = []

    # -------------------------------------------------------------
    # Core resources
    # -------------------------------------------------------------

    patient_entry = _build_patient(
        row,
        patient_url,
    )

    practitioner_entry = _build_practitioner(
        row,
        practitioner_url,
    )

    organization_entry = _build_organization(
        row,
        organization_url,
    )

    encounter_entry = _build_encounter(
        row,
        encounter_url,
        patient_url,
        practitioner_url,
        organization_url,
    )

    entries.extend([
        patient_entry,
        practitioner_entry,
        organization_entry,
        encounter_entry,
    ])

    # -------------------------------------------------------------
    # Clinical resources
    # -------------------------------------------------------------

    sections = []

    # -------------------------------------------------------------
    # OPConsultation
    # -------------------------------------------------------------

    if hi_type == "OPConsultation":

        symptom_entry = _build_symptom(
            row,
            patient_url,
            encounter_url,
        )

        if symptom_entry:
            entries.append(symptom_entry)
            sections.append(
                _section(
                    "Chief Complaints",
                    [symptom_entry["fullUrl"]],
                    "422587007",
                    "Symptoms",
                )
            )

        vital_entries = _build_vital_observations(
            row,
            patient_url,
            encounter_url,
        )

        if vital_entries:
            entries.extend(vital_entries)

            sections.append(
                _section(
                    "Vital Signs",
                    [
                        x["fullUrl"]
                        for x in vital_entries
                    ],
                )
            )

        examination = _build_examination(
            row,
            patient_url,
            encounter_url,
        )

        if examination:
            entries.append(examination)

            sections.append(
                _section(
                    "Examination",
                    [examination["fullUrl"]],
                )
            )

        diagnosis = _build_diagnosis(
            row,
            patient_url,
            encounter_url,
        )

        if diagnosis:
            entries.append(diagnosis)

            sections.append(
                _section(
                    "Diagnosis",
                    [diagnosis["fullUrl"]],
                )
            )

        history = _build_medical_history(
            row,
            patient_url,
            encounter_url,
        )

        if history:
            entries.append(history)

            sections.append(
                _section(
                    "Medical History",
                    [history["fullUrl"]],
                )
            )

        allergy = _build_allergy(
            row,
            patient_url,
            encounter_url,
        )

        if allergy:
            entries.append(allergy)

            sections.append(
                _section(
                    "Allergies",
                    [allergy["fullUrl"]],
                )
            )

        medication = _build_medication_request(
            row,
            patient_url,
            encounter_url,
        )

        if medication:
            entries.append(medication)

            sections.append(
                _section(
                    "Medications",
                    [medication["fullUrl"]],
                )
            )

        advice = _build_advice(
            row,
            patient_url,
            encounter_url,
        )

        if advice:
            entries.append(advice)

            sections.append(
                _section(
                    "Advice",
                    [advice["fullUrl"]],
                )
            )

        clinical_notes = _build_clinical_notes(
            row,
            patient_url,
            encounter_url,
        )

        if clinical_notes:
            entries.append(clinical_notes)

            sections.append(
                _section(
                    "Clinical Notes",
                    [clinical_notes["fullUrl"]],
                )
            )

        procedure = _build_procedure_from_notes(
            row,
            patient_url,
            encounter_url,
        )

        if procedure:
            entries.append(procedure)

            sections.append(
                _section(
                    "Procedures",
                    [procedure["fullUrl"]],
                    "371525003",
                    "Clinical procedure report",
                )
            )

        family_history = _build_family_history(
            row,
            patient_url,
        )

        if family_history:
            entries.append(family_history)

            sections.append(
                _section(
                    "Family History",
                    [family_history["fullUrl"]],
                )
            )

        followup = _build_followup(
            row,
            patient_url,
            practitioner_url,
        )

        if followup:
            entries.append(followup)

            sections.append(
                _section(
                    "Follow-up",
                    [followup["fullUrl"]],
                )
            )

    # -------------------------------------------------------------
    # Prescription
    # -------------------------------------------------------------

    elif hi_type == "Prescription":

        medication = _build_medication_request(
            row,
            patient_url,
            encounter_url,
        )

        if not medication:
            raise ValueError(
                "Prescription record requires medication_name."
            )

        entries.append(medication)

        sections.append(
            _section(
                "Medications",
                [medication["fullUrl"]],
            )
        )

        advice = _build_advice(
            row,
            patient_url,
            encounter_url,
        )

        if advice:
            entries.append(advice)

            sections.append(
                _section(
                    "Advice",
                    [advice["fullUrl"]],
                )
            )

        document = _document_reference(
            row,
            patient_url,
            encounter_url,
            "Prescription",
        )

        if document:
            entries.append(document)

            sections.append(
                _section(
                    "Document",
                    [document["fullUrl"]],
                )
            )

    # -------------------------------------------------------------
    # DiagnosticReport
    # -------------------------------------------------------------

    elif hi_type == "DiagnosticReport":

        service_request = _build_lab_service_request(
            row,
            patient_url,
            encounter_url,
        )

        if service_request:
            entries.append(service_request)

        result = _build_lab_result(
            row,
            patient_url,
            encounter_url,
        )

        result_urls = []

        if result:
            entries.append(result)
            result_urls.append(
                result["fullUrl"]
            )

        report = _build_diagnostic_report(
            row,
            patient_url,
            encounter_url,
            result_urls,
        )

        # entries.append(report)
        #
        # sections.append(
        #     _section(
        #         "Diagnostic Report",
        #         [report["fullUrl"]],
        #     )
        # )

        entries.append(report)

        document = _document_reference(
            row,
            patient_url,
            encounter_url,
            "Diagnostic Report",
        )

        section_entries = [report["fullUrl"]]

        if document:
            entries.append(document)
            section_entries.append(document["fullUrl"])

        sections.append(
            _section(
                "Diagnostic Report",
                section_entries,
                "721981007",
                "Diagnostic studies report",
            )
        )

        if result:
            sections.append(
                _section(
                    "Results",
                    [result["fullUrl"]],
                )
            )

        document = _document_reference(
            row,
            patient_url,
            encounter_url,
            "Diagnostic Report",
        )

        if document:
            entries.append(document)

            sections.append(
                _section(
                    "Supporting Document",
                    [document["fullUrl"]],
                )
            )

    # -------------------------------------------------------------
    # DischargeSummary
    # -------------------------------------------------------------

    elif hi_type == "DischargeSummary":

        diagnosis = _build_diagnosis(
            row,
            patient_url,
            encounter_url,
        )

        if diagnosis:
            entries.append(diagnosis)

            sections.append(
                _section(
                    "Diagnosis",
                    [diagnosis["fullUrl"]],
                )
            )

        medication = _build_medication_request(
            row,
            patient_url,
            encounter_url,
        )

        if medication:
            entries.append(medication)

            sections.append(
                _section(
                    "Medications",
                    [medication["fullUrl"]],
                )
            )

        advice = _build_advice(
            row,
            patient_url,
            encounter_url,
        )

        if advice:
            entries.append(advice)

            sections.append(
                _section(
                    "Discharge Advice",
                    [advice["fullUrl"]],
                )
            )

        clinical_notes = _build_clinical_notes(
            row,
            patient_url,
            encounter_url,
        )

        if clinical_notes:
            entries.append(clinical_notes)

            sections.append(
                _section(
                    "Clinical Notes",
                    [clinical_notes["fullUrl"]],
                )
            )

        document = _document_reference(
            row,
            patient_url,
            encounter_url,
            "Discharge Summary",
        )

        if document:
            entries.append(document)

            sections.append(
                _section(
                    "Document",
                    [document["fullUrl"]],
                )
            )

    # -------------------------------------------------------------
    # HealthDocumentRecord
    # -------------------------------------------------------------

    elif hi_type == "HealthDocumentRecord":

        document = _document_reference(
            row,
            patient_url,
            encounter_url,
            "Health Document",
        )

        if not document:
            raise ValueError(
                "HealthDocumentRecord requires "
                "document_filename or document_type."
            )

        entries.append(document)

        sections.append(
            _section(
                "Document Reference",
                [document["fullUrl"]],
            )
        )

        clinical_notes = _build_clinical_notes(
            row,
            patient_url,
            encounter_url,
        )

        if clinical_notes:
            entries.append(clinical_notes)

            sections.append(
                _section(
                    "Clinical Notes",
                    [clinical_notes["fullUrl"]],
                )
            )

    # -------------------------------------------------------------
    # ImmunizationRecord
    # -------------------------------------------------------------

    elif hi_type == "ImmunizationRecord":

        immunization = _build_immunization(
            row,
            patient_url,
            encounter_url,
        )

        if not immunization:
            raise ValueError(
                "ImmunizationRecord requires "
                "immunization_vaccine_name."
            )

        entries.append(immunization)

        sections.append(
            _section(
                "Immunization",
                [immunization["fullUrl"]],
                "41000179103",
                "Immunization record",
            )
        )

        document = _document_reference(
            row,
            patient_url,
            encounter_url,
            "Immunization certificate",
        )

        if document:
            entries.append(document)

            sections.append(
                _section(
                    "Supporting Document",
                    [document["fullUrl"]],
                )
            )

    # -------------------------------------------------------------
    # WellnessRecord
    # -------------------------------------------------------------

    elif hi_type == "WellnessRecord":

        vital_entries = _build_vital_observations(
            row,
            patient_url,
            encounter_url,
        )

        if vital_entries:
            entries.extend(vital_entries)

            sections.append(
                _section(
                    "Vital Signs",
                    [
                        x["fullUrl"]
                        for x in vital_entries
                    ],
                )
            )

        examination = _build_examination(
            row,
            patient_url,
            encounter_url,
        )

        if examination:
            entries.append(examination)

            sections.append(
                _section(
                    "General Assessment",
                    [examination["fullUrl"]],
                )
            )

        clinical_notes = _build_clinical_notes(
            row,
            patient_url,
            encounter_url,
        )

        if clinical_notes:
            entries.append(clinical_notes)

            sections.append(
                _section(
                    "Other Observations",
                    [clinical_notes["fullUrl"]],
                )
            )

        document = _document_reference(
            row,
            patient_url,
            encounter_url,
            "Wellness Record",
        )

        if document:
            entries.append(document)

            sections.append(
                _section(
                    "Document Reference",
                    [document["fullUrl"]],
                )
            )

    # -------------------------------------------------------------
    # Composition must be FIRST in a document Bundle.
    # -------------------------------------------------------------

    composition = _build_composition(
        row,
        hi_type,
        composition_url,
        patient_url,
        encounter_url,
        practitioner_url,
        organization_url,
        sections,
    )

    bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "identifier": {
            "system": "https://ndhm.in/phr",
            "value": (
                _clean(row.get("care_context_id"))
                or _clean(row.get("record_id"))
                or str(uuid.uuid4())
            ),
        },
        "timestamp": _now_iso(),
        "entry": [
            composition
        ] + entries,
    }

    return bundle


# ---------------------------------------------------------------------
# CSV loader / CLI
# ---------------------------------------------------------------------

def _find_record(record_id):
    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    csv_path = os.path.join(
        project_root,
        "data",
        "master_flat_table.csv",
    )

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}"
        )

    # Your CSV currently contains Windows/Excel characters.
    # cp1252 handles those safely.
    with open(
        csv_path,
        newline="",
        encoding="cp1252",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            if _clean(
                row.get("record_id")
            ) == record_id:

                return row

    return None


def save_bundle(record_id, row, bundle):
    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    output_dir = os.path.join(
        project_root,
        "data",
        "bundles",
    )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    hi_type = (
        _clean(row.get("hi_type"))
        or "Unknown"
    )

    care_context_id = (
        _clean(row.get("care_context_id"))
        or "unknown"
    )

    filename = (
        f"{record_id}_"
        f"{hi_type}_"
        f"{care_context_id}.json"
    )

    output_path = os.path.join(
        output_dir,
        filename,
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            bundle,
            f,
            indent=2,
            ensure_ascii=False,
        )

    return output_path


def main():
    if len(sys.argv) != 2:

        print(
            "Usage:"
        )

        print(
            "  python src/fhir_builder.py R001"
        )

        sys.exit(1)

    record_id = sys.argv[1]

    try:
        row = _find_record(
            record_id
        )

        if row is None:

            print(
                f"ERROR: record_id "
                f"'{record_id}' not found."
            )

            sys.exit(1)

        print(
            f"Found record: {record_id}"
        )

        print(
            f"Patient: "
            f"{row.get('patient_name', '')}"
        )

        print(
            f"HI Type: "
            f"{row.get('hi_type', '')}"
        )

        print(
            f"Care Context: "
            f"{row.get('care_context_id', '')}"
        )

        bundle = build_bundle(
            row
        )

        output_path = save_bundle(
            record_id,
            row,
            bundle,
        )

        print()
        print(
            "FHIR Bundle created successfully."
        )

        print(
            f"Entries: "
            f"{len(bundle['entry'])}"
        )

        print(
            "Saved to:"
        )

        print(
            output_path
        )

    except Exception as e:

        print()
        print(
            "ERROR while building FHIR Bundle:"
        )

        print(
            str(e)
        )

        raise


if __name__ == "__main__":
    main()