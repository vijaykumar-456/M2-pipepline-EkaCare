"""
Builds ABDM/NRCES-profile FHIR R4 document bundles from Group B (clinical
source) fields on a flat table row, per the abdm-fhir skill's mapping:

  symptoms         -> Observation (category: signs-and-symptoms)
  vitals           -> Observation (category: vital-signs)
  examination      -> Observation (category: exam)
  diagnosis        -> Condition (category: encounter-diagnosis)
  medical history  -> Condition (category: problem-list-item)
  medications      -> MedicationRequest (intent: order)
  labs             -> ServiceRequest / DiagnosticReport
  allergies        -> AllergyIntolerance
  advice           -> CarePlan (intent: plan)
  clinical notes   -> CarePlan (intent: proposal)
  follow-up        -> Appointment (appointmentType: FOLLOWUP)

Bundle rules followed: Bundle.type = document, first entry is Composition
referencing every other resource, every resource has a stable fullUrl
(urn:uuid), Patient carries the ABHA address as an identifier, timestamps
ISO 8601.

NOT YET VALIDATED against the real HL7 FHIR validator / NRCES IG -- run
that before shipping anything built here to a real HIU. See the abdm-fhir
skill's "Test before done" section for the validator command.

CONFIRM before relying on this: the exact identifier `system` URI used
for the ABHA address below is a placeholder -- check the NRCES IG
(https://nrces.in/ndhm/fhir/r4/) for the correct one.
"""
import uuid
from datetime import datetime, timezone

ABHA_IDENTIFIER_SYSTEM = "https://healthid.ndhm.gov.in"  # PLACEHOLDER -- confirm against NRCES IG


def _uuid_url():
    return f"urn:uuid:{uuid.uuid4()}"


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _patient_resource(row: dict, patient_url: str) -> dict:
    return {
        "fullUrl": patient_url,
        "resource": {
            "resourceType": "Patient",
            "identifier": [{"system": ABHA_IDENTIFIER_SYSTEM, "value": row["abha_address"]}],
            "name": [{"text": row.get("patient_name", "")}],
            "gender": {"M": "male", "F": "female"}.get(row.get("gender", ""), "unknown"),
        },
    }


def _practitioner_resource(row: dict, url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "Practitioner",
            "name": [{"text": row.get("practitioner_name", "")}],
        },
    }


def _symptom_observation(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                       "code": "signs-and-symptoms"}]}],
            "code": {"coding": [{"system": "http://snomed.info/sct",
                                  "code": row.get("symptoms_snomed_code", "")}],
                     "text": row.get("symptoms_text", "")},
            "subject": {"reference": patient_url},
            "effectiveDateTime": row.get("encounter_date", ""),
        },
    }


def _vitals_observation(row: dict, url: str, patient_url: str) -> dict:
    components = []
    if row.get("vitals_bp_systolic") or row.get("vitals_bp_diastolic"):
        components.append({"code": {"text": "Systolic BP"}, "valueQuantity": {"value": row.get("vitals_bp_systolic", ""), "unit": "mmHg"}})
        components.append({"code": {"text": "Diastolic BP"}, "valueQuantity": {"value": row.get("vitals_bp_diastolic", ""), "unit": "mmHg"}})
    if row.get("vitals_pulse"):
        components.append({"code": {"text": "Pulse"}, "valueQuantity": {"value": row.get("vitals_pulse", ""), "unit": "bpm"}})
    if row.get("vitals_temp_c"):
        components.append({"code": {"text": "Temperature"}, "valueQuantity": {"value": row.get("vitals_temp_c", ""), "unit": "Cel"}})
    if row.get("vitals_spo2"):
        components.append({"code": {"text": "SpO2"}, "valueQuantity": {"value": row.get("vitals_spo2", ""), "unit": "%"}})
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                       "code": "vital-signs"}]}],
            "code": {"text": "Vital signs panel"},
            "subject": {"reference": patient_url},
            "effectiveDateTime": row.get("encounter_date", ""),
            "component": components,
        },
    }


def _exam_observation(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                       "code": "exam"}]}],
            "code": {"text": "Examination findings"},
            "subject": {"reference": patient_url},
            "effectiveDateTime": row.get("encounter_date", ""),
            "valueString": row.get("examination_notes", ""),
        },
    }


def _diagnosis_condition(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "Condition",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                       "code": "encounter-diagnosis"}]}],
            "code": {"coding": [{"system": "http://snomed.info/sct",
                                  "code": row.get("diagnosis_snomed_code", "")}],
                     "text": row.get("diagnosis_text", "")},
            "subject": {"reference": patient_url},
        },
    }


def _medical_history_condition(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "Condition",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                       "code": "problem-list-item"}]}],
            "code": {"text": row.get("medical_history_text", "")},
            "subject": {"reference": patient_url},
        },
    }


def _medication_request(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {"text": row.get("medication_name", "")},
            "subject": {"reference": patient_url},
            "dosageInstruction": [{
                "text": f"{row.get('medication_dosage', '')} {row.get('medication_frequency', '')}".strip(),
                "timing": {"repeat": {
                    "frequency": row.get("medication_frequency", ""),
                    "duration": row.get("medication_duration_days", ""),
                    "durationUnit": "d",
                }},
            }],
        },
    }


def _allergy_intolerance(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "AllergyIntolerance",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "category": [row.get("allergy_category", "")],
            "code": {"text": row.get("allergy_text", "")},
            "patient": {"reference": patient_url},
        },
    }


def _advice_care_plan(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "CarePlan",
            "status": "active",
            "intent": "plan",
            "description": row.get("advice_notes", ""),
            "subject": {"reference": patient_url},
        },
    }


def _clinical_notes_care_plan(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "CarePlan",
            "status": "active",
            "intent": "proposal",
            "description": row.get("clinical_notes", ""),
            "subject": {"reference": patient_url},
        },
    }


def _followup_appointment(row: dict, url: str, patient_url: str) -> dict:
    return {
        "fullUrl": url,
        "resource": {
            "resourceType": "Appointment",
            "status": "proposed",
            "appointmentType": {"coding": [{"code": "FOLLOWUP"}]},
            "start": row.get("follow_up_date", ""),
            "participant": [{"actor": {"reference": patient_url}, "status": "needs-action"}],
        },
    }


def build_bundle(row: dict) -> dict:
    """Dispatches on row['hi_type'] and includes only the resources that
    apply. Every entry gets its own stable urn:uuid fullUrl. Composition
    is always first and references every other resource."""
    hi_type = row["hi_type"]
    patient_url = _uuid_url()
    entries = [_patient_resource(row, patient_url)]
    section_refs = []

    def add(builder_fn, condition):
        if condition:
            url = _uuid_url()
            entries.append(builder_fn(row, url, patient_url))
            section_refs.append(url)

    if row.get("practitioner_name"):
        practitioner_url = _uuid_url()
        entries.append(_practitioner_resource(row, practitioner_url))

    if hi_type == "OPConsultation":
        add(_symptom_observation, row.get("symptoms_text"))
        add(_vitals_observation, any([row.get("vitals_bp_systolic"), row.get("vitals_pulse"),
                                       row.get("vitals_temp_c"), row.get("vitals_spo2")]))
        add(_exam_observation, row.get("examination_notes"))
        add(_diagnosis_condition, row.get("diagnosis_text"))
        add(_medication_request, row.get("medication_name"))
        add(_advice_care_plan, row.get("advice_notes"))
        add(_clinical_notes_care_plan, row.get("clinical_notes"))
        add(_followup_appointment, row.get("follow_up_date"))
        add(_allergy_intolerance, row.get("allergy_text"))
        add(_medical_history_condition, row.get("medical_history_text"))

    elif hi_type == "Prescription":
        add(_medication_request, row.get("medication_name"))

    elif hi_type == "DiagnosticReport":
        # Minimal placeholder -- DiagnosticReport resource itself not yet
        # modeled; lab_test_* fields exist on the row but need a proper
        # DiagnosticReport + Observation(result) builder, not just text.
        add(_exam_observation, row.get("lab_result_value"))

    elif hi_type == "DischargeSummary":
        add(_diagnosis_condition, row.get("diagnosis_text"))
        add(_medication_request, row.get("medication_name"))
        add(_advice_care_plan, row.get("advice_notes"))

    elif hi_type == "ImmunizationRecord":
        entries.append({
            "fullUrl": _uuid_url(),
            "resource": {
                "resourceType": "Immunization",
                "status": "completed",
                "vaccineCode": {"text": row.get("immunization_vaccine_name", "")},
                "patient": {"reference": patient_url},
                "occurrenceDateTime": row.get("immunization_date", ""),
            },
        })

    elif hi_type == "HealthDocumentRecord":
        entries.append({
            "fullUrl": _uuid_url(),
            "resource": {
                "resourceType": "DocumentReference",
                "status": "current",
                "type": {"text": row.get("document_type", "")},
                "subject": {"reference": patient_url},
                # NOTE: actual base64 file content goes in content[].attachment.data --
                # not wired up here, this just carries the filename/type.
                "description": row.get("document_filename", ""),
            },
        })

    elif hi_type == "WellnessRecord":
        add(_vitals_observation, any([row.get("vitals_bp_systolic"), row.get("vitals_pulse")]))

    composition_url = _uuid_url()
    composition = {
        "fullUrl": composition_url,
        "resource": {
            "resourceType": "Composition",
            "status": "final",
            "type": {"text": hi_type},
            "subject": {"reference": patient_url},
            "date": _now_iso(),
            "title": row.get("display", hi_type),
            "section": [{"entry": [{"reference": e["fullUrl"]} for e in entries]}],
        },
    }

    return {
        "resourceType": "Bundle",
        "type": "document",
        "timestamp": _now_iso(),
        "entry": [composition] + entries,
    }


if __name__ == "__main__":
    import csv
    import json
    import os
    import sys

    # ---------------------------------------------------------
    # Get row ID from command line
    #
    # Example:
    # python src/fhir_builder.py P001
    # ---------------------------------------------------------

    if len(sys.argv) != 2:
        print("Usage:")
        print("  python src/fhir_builder.py P001")
        sys.exit(1)

    row_id = sys.argv[1]

    # ---------------------------------------------------------
    # Locate master_flat_table.csv
    # ---------------------------------------------------------

    project_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    csv_path = os.path.join(
        project_root,
        "data",
        "master_flat_table.csv"
    )

    # ---------------------------------------------------------
    # Read P001 from CSV
    # ---------------------------------------------------------

    if not os.path.exists(csv_path):
        print(f"ERROR: CSV file not found:")
        print(csv_path)
        sys.exit(1)

    row = None

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for csv_row in reader:
            if csv_row.get("row_id") == row_id:
                row = csv_row
                break

    if row is None:
        print(f"ERROR: row_id '{row_id}' not found in CSV")
        sys.exit(1)

    print(f"Found row: {row_id}")
    print(f"Patient: {row.get('patient_name', '')}")
    print(f"HI Type: {row.get('hi_type', '')}")
    print(f"Care Context: {row.get('care_context_id', '')}")

    # ---------------------------------------------------------
    # Build FHIR Bundle from the ACTUAL CSV row
    # ---------------------------------------------------------

    bundle = build_bundle(row)

    # ---------------------------------------------------------
    # Create output directory
    # ---------------------------------------------------------

    output_dir = os.path.join(
        project_root,
        "data",
        "bundles"
    )

    os.makedirs(output_dir, exist_ok=True)

    # ---------------------------------------------------------
    # Create output filename
    # ---------------------------------------------------------

    care_context_id = row.get(
        "care_context_id",
        "unknown"
    )

    output_filename = (
        f"{row_id}_{row.get('hi_type', 'Unknown')}_"
        f"{care_context_id}.json"
    )

    output_path = os.path.join(
        output_dir,
        output_filename
    )

    # ---------------------------------------------------------
    # Save FHIR Bundle
    # ---------------------------------------------------------

    with open(
            output_path,
            "w",
            encoding="utf-8"
    ) as f:
        json.dump(
            bundle,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("FHIR Bundle created successfully.")
    print(f"Entries: {len(bundle['entry'])}")
    print(f"Saved to:")
    print(output_path)