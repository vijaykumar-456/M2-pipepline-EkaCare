"""
fhir_builder.py
Converts each row of master_flat_table_V3_HIS_source.csv into an ABDM-compliant
FHIR Bundle (type=document), branching on `hi_type` per the confirmed NRCES specs.

One row -> one Bundle JSON file.
"""

import pandas as pd
import json
import os
import uuid
import math
from datetime import datetime

CSV_PATH = "/home/claude/master_flat_table_V4_final.csv"
OUT_DIR = "/home/claude/fhir_bundles_generated_v4"
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def u():
    """New urn:uuid: reference id."""
    return f"urn:uuid:{uuid.uuid4()}"


def is_filled(val):
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    return str(val).strip() != ""


def to_fhir_date(d):
    """dd-mm-yyyy -> yyyy-mm-dd. Returns None if blank/unparseable."""
    if not is_filled(d):
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(d).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def entry(full_url, resource):
    return {"fullUrl": full_url, "resource": resource}


# ---------------------------------------------------------------------------
# resource builders (each returns (fullUrl, resourceDict))
# ---------------------------------------------------------------------------

def build_patient(row):
    fu = u()
    res = {
        "resourceType": "Patient",
        "id": fu.split(":")[-1],
        "identifier": [],
        "name": [{"text": row["patient_name"]}],
        "gender": {"M": "male", "F": "female"}.get(row.get("gender", ""), "unknown"),
    }
    if is_filled(row.get("year_of_birth")):
        res["birthDate"] = f"{row['year_of_birth']}-01-01"
    if is_filled(row.get("abha_address")):
        res["identifier"].append({"system": "https://healthid.ndhm.gov.in", "value": row["abha_address"]})
    if is_filled(row.get("abha_number")):
        res["identifier"].append({"system": "https://abdm.gov.in/abha-number", "value": row["abha_number"]})
    if is_filled(row.get("mobile_number")):
        res["telecom"] = [{"system": "phone", "value": row["mobile_number"]}]
    if not res["identifier"]:
        del res["identifier"]
    return fu, res


def build_practitioner(row):
    fu = u()
    res = {"resourceType": "Practitioner", "id": fu.split(":")[-1], "name": [{"text": row["practitioner_name"]}]}
    return fu, res


def build_organization(row):
    fu = u()
    res = {"resourceType": "Organization", "id": fu.split(":")[-1], "name": row.get("hip_id") or row.get("clinic_id") or "Unknown Facility"}
    return fu, res


def build_encounter(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "Encounter",
        "id": fu.split(":")[-1],
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "subject": {"reference": patient_ref},
    }
    d = to_fhir_date(row.get("encounter_date"))
    if d:
        res["period"] = {"start": f"{d}T00:00:00+05:30"}
    return fu, res


def build_condition(row, patient_ref, text_field, code_field, category_text):
    fu = u()
    res = {
        "resourceType": "Condition",
        "id": fu.split(":")[-1],
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
        "code": {"text": row[text_field]},
        "subject": {"reference": patient_ref},
    }
    if is_filled(row.get(code_field)):
        res["code"]["coding"] = [{"system": "http://snomed.info/sct", "code": str(row[code_field]), "display": row[text_field]}]
    return fu, res


def build_observation_vitals(row, patient_ref):
    """One Observation per populated vitals field -> returns list of (fullUrl, resource)."""
    out = []
    vitals_map = [
        ("vitals_bp_systolic", "8480-6", "Systolic blood pressure", "mmHg"),
        ("vitals_bp_diastolic", "8462-4", "Diastolic blood pressure", "mmHg"),
        ("vitals_pulse", "8867-4", "Heart rate", "beats/min"),
        ("vitals_temp_c", "8310-5", "Body temperature", "Cel"),
        ("vitals_spo2", "59408-5", "Oxygen saturation", "%"),
    ]
    for field, loinc, display, unit in vitals_map:
        if is_filled(row.get(field)):
            fu = u()
            res = {
                "resourceType": "Observation",
                "id": fu.split(":")[-1],
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": display}]},
                "subject": {"reference": patient_ref},
                "valueQuantity": {"value": float(row[field]), "unit": unit},
            }
            out.append((fu, res))
    return out


def build_observation_text(row, patient_ref, text_field, loinc, display):
    fu = u()
    res = {
        "resourceType": "Observation",
        "id": fu.split(":")[-1],
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": display}]},
        "subject": {"reference": patient_ref},
        "valueString": row[text_field],
    }
    return fu, res


def build_allergy(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "AllergyIntolerance",
        "id": fu.split(":")[-1],
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active"}]},
        "code": {"text": row["allergy_text"]},
        "patient": {"reference": patient_ref},
    }
    if is_filled(row.get("allergy_category")):
        res["category"] = [row["allergy_category"].lower()]
    return fu, res


def build_medication_request(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "MedicationRequest",
        "id": fu.split(":")[-1],
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {"text": row["medication_name"]},
        "subject": {"reference": patient_ref},
    }
    dosage_parts = []
    if is_filled(row.get("medication_dosage")):
        dosage_parts.append(row["medication_dosage"])
    if is_filled(row.get("medication_frequency")):
        dosage_parts.append(row["medication_frequency"])
    if is_filled(row.get("medication_duration_days")):
        dosage_parts.append(f"for {row['medication_duration_days']} days")
    if dosage_parts:
        res["dosageInstruction"] = [{"text": ", ".join(dosage_parts)}]
    return fu, res


def build_procedure(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "Procedure",
        "id": fu.split(":")[-1],
        "status": "completed",
        "code": {"text": row["procedure_text"]},
        "subject": {"reference": patient_ref},
    }
    if is_filled(row.get("procedure_snomed_code")):
        res["code"]["coding"] = [{"system": "http://snomed.info/sct", "code": str(row["procedure_snomed_code"]), "display": row["procedure_text"]}]
    return fu, res


def build_family_history(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "FamilyMemberHistory",
        "id": fu.split(":")[-1],
        "status": "completed",
        "patient": {"reference": patient_ref},
        "note": [{"text": row["family_history_text"]}],
        "relationship": {"text": "Family member"},
    }
    return fu, res


def build_service_request(row, patient_ref, text):
    fu = u()
    res = {
        "resourceType": "ServiceRequest",
        "id": fu.split(":")[-1],
        "status": "active",
        "intent": "order",
        "code": {"text": text},
        "subject": {"reference": patient_ref},
    }
    return fu, res


def build_diagnostic_report(row, patient_ref, imaging=False):
    fu = u()
    profile = "DiagnosticReportImaging" if imaging else "DiagnosticReportLab"
    res = {
        "resourceType": "DiagnosticReport",
        "id": fu.split(":")[-1],
        "meta": {"profile": [f"https://nrces.in/ndhm/fhir/r4/StructureDefinition/{profile}"]},
        "status": "final",
        "code": {"text": row.get("lab_test_name") or row.get("diagnostic_imaging_modality") or "Diagnostic Report"},
        "subject": {"reference": patient_ref},
    }
    if is_filled(row.get("lab_test_loinc_code")):
        res["code"]["coding"] = [{"system": "http://loinc.org", "code": row["lab_test_loinc_code"], "display": row.get("lab_test_name", "")}]
    if is_filled(row.get("lab_result_value")):
        res["conclusion"] = row["lab_result_value"]
    d = to_fhir_date(row.get("encounter_date"))
    if d:
        res["issued"] = f"{d}T09:00:00+05:30"
    return fu, res


def build_document_reference(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "DocumentReference",
        "id": fu.split(":")[-1],
        "status": "current",
        "subject": {"reference": patient_ref},
        "content": [{"attachment": {}}],
    }
    att = res["content"][0]["attachment"]
    if is_filled(row.get("document_mime_type")):
        att["contentType"] = row["document_mime_type"]
    if is_filled(row.get("document_url")):
        att["url"] = row["document_url"]
    if is_filled(row.get("document_description")):
        att["title"] = row["document_description"]
    if is_filled(row.get("document_size_kb")):
        try:
            att["size"] = int(float(row["document_size_kb"]) * 1024)  # bytes
        except ValueError:
            pass
    if is_filled(row.get("document_type")):
        res["type"] = {"text": row["document_type"]}
    return fu, res


def build_binary(row):
    """Prescription attachments use Binary, not DocumentReference, per spec."""
    fu = u()
    res = {
        "resourceType": "Binary",
        "id": fu.split(":")[-1],
        "contentType": row.get("document_mime_type") or "application/octet-stream",
    }
    # In a real system this would carry base64 'data'. We keep a placeholder
    # and preserve the source URL in an extension so downstream systems can fetch it.
    if is_filled(row.get("document_url")):
        res["extension"] = [{
            "url": "http://example.org/fhir/StructureDefinition/source-url",
            "valueUrl": row["document_url"]
        }]
    res["data"] = "PLACEHOLDER_BASE64=="
    return fu, res


def build_immunization(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "Immunization",
        "id": fu.split(":")[-1],
        "status": "completed",
        "vaccineCode": {"text": row["immunization_vaccine_name"]},
        "patient": {"reference": patient_ref},
    }
    d = to_fhir_date(row.get("immunization_date"))
    if d:
        res["occurrenceDateTime"] = f"{d}T09:00:00+05:30"
    if is_filled(row.get("immunization_dose_number")):
        res["protocolApplied"] = [{"doseNumberPositiveInt": int(float(row["immunization_dose_number"]))}]
    return fu, res


def build_immunization_recommendation(row, patient_ref):
    fu = u()
    res = {
        "resourceType": "ImmunizationRecommendation",
        "id": fu.split(":")[-1],
        "patient": {"reference": patient_ref},
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30"),
        "recommendation": [{
            "forecastStatus": {"text": "due"},
        }]
    }
    d = to_fhir_date(row.get("immunization_next_due_date"))
    if d:
        res["recommendation"][0]["dateCriterion"] = [{
            "code": {"coding": [{"system": "http://loinc.org", "code": "30980-7", "display": "Date vaccine due"}]},
            "value": f"{d}T00:00:00+05:30"
        }]
    return fu, res


def build_wellness_observation(row, patient_ref, field, loinc, display, unit, profile):
    fu = u()
    res = {
        "resourceType": "Observation",
        "id": fu.split(":")[-1],
        "meta": {"profile": [f"https://nrces.in/ndhm/fhir/r4/StructureDefinition/{profile}"]},
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": loinc, "display": display}]},
        "subject": {"reference": patient_ref},
        "valueQuantity": {"value": float(row[field]), "unit": unit},
    }
    return fu, res


# ---------------------------------------------------------------------------
# Composition + Bundle assembly per hi_type
# ---------------------------------------------------------------------------

COMPOSITION_META = {
    "OPConsultation": ("OPConsultRecord", "371530004", "Clinical consultation report"),
    "DiagnosticReport": ("DiagnosticReportRecord", "721981007", "Diagnostic studies report"),
    "Prescription": ("PrescriptionRecord", "440545006", "Prescription record"),
    "DischargeSummary": ("DischargeSummaryRecord", "373942005", "Discharge summary"),
    "HealthDocumentRecord": ("HealthDocumentRecord", "419891008", "Record artifact"),
    "ImmunizationRecord": ("ImmunizationRecord", "41000179103", "Immunization record"),
    "WellnessRecord": ("WellnessRecord", "410097008", "Wellness assessment"),
}


def build_bundle_for_row(row):
    hi_type = row.get("hi_type", "").strip()
    if hi_type not in COMPOSITION_META:
        return None  # skip rows with unrecognized/blank hi_type

    profile, comp_code, comp_display = COMPOSITION_META[hi_type]
    entries = []

    patient_fu, patient_res = build_patient(row)
    entries.append(entry(patient_fu, patient_res))

    practitioner_fu = None
    if is_filled(row.get("practitioner_name")):
        practitioner_fu, practitioner_res = build_practitioner(row)
        entries.append(entry(practitioner_fu, practitioner_res))

    org_fu = None
    if is_filled(row.get("hip_id")) or is_filled(row.get("clinic_id")):
        org_fu, org_res = build_organization(row)
        entries.append(entry(org_fu, org_res))

    encounter_fu = None
    if is_filled(row.get("encounter_id")):
        encounter_fu, encounter_res = build_encounter(row, patient_fu)
        entries.append(entry(encounter_fu, encounter_res))

    sections = []

    def add_section(title, code, code_display, refs):
        if refs:
            sec = {"title": title, "entry": [{"reference": r} for r in refs]}
            if code:
                sec["code"] = {"coding": [{"system": "http://snomed.info/sct", "code": code, "display": code_display}]}
            sections.append(sec)

    # ---------------- OPConsultation & DischargeSummary (rich, multi-section) ----------------
    if hi_type in ("OPConsultation", "DischargeSummary"):
        cc_refs = []
        if is_filled(row.get("symptoms_text")):
            fu, res = build_condition(row, patient_fu, "symptoms_text", "symptoms_snomed_code", "Chief complaint")
            entries.append(entry(fu, res)); cc_refs.append(fu)
        add_section("Chief Complaints", "422843007", "Chief complaint section", cc_refs)

        pe_refs = [fu for fu, res in build_observation_vitals(row, patient_fu)]
        # need to also append these entries to the bundle
        for fu, res in build_observation_vitals(row, patient_fu):
            pass  # placeholder, real append handled below
        vitals_pairs = build_observation_vitals(row, patient_fu)
        pe_refs = []
        for fu, res in vitals_pairs:
            entries.append(entry(fu, res)); pe_refs.append(fu)
        if is_filled(row.get("examination_notes")):
            fu, res = build_observation_text(row, patient_fu, "examination_notes", "425044008", "Physical exam finding")
            entries.append(entry(fu, res)); pe_refs.append(fu)
        add_section("Physical Examination", "425044008", "Physical exam section", pe_refs)

        allergy_refs = []
        if is_filled(row.get("allergy_text")):
            fu, res = build_allergy(row, patient_fu)
            entries.append(entry(fu, res)); allergy_refs.append(fu)
        add_section("Allergies", "722446000", "Allergy record", allergy_refs)

        mh_code = "371529009" if hi_type == "OPConsultation" else "1003642006"
        mh_refs = []
        if is_filled(row.get("diagnosis_text")):
            fu, res = build_condition(row, patient_fu, "diagnosis_text", "diagnosis_snomed_code", "Diagnosis")
            entries.append(entry(fu, res)); mh_refs.append(fu)
        if is_filled(row.get("medical_history_text")):
            fu, res = build_observation_text(row, patient_fu, "medical_history_text", "1003642006", "Medical history note")
            entries.append(entry(fu, res)); mh_refs.append(fu)
        add_section("Medical History", mh_code, "History and physical report", mh_refs)

        fh_refs = []
        if is_filled(row.get("family_history_text")):
            fu, res = build_family_history(row, patient_fu)
            entries.append(entry(fu, res)); fh_refs.append(fu)
        add_section("Family History", "422432008", "Family history section", fh_refs)

        if hi_type == "OPConsultation":
            ia_refs = []
            if is_filled(row.get("lab_test_name")):
                fu, res = build_service_request(row, patient_fu, row["lab_test_name"])
                entries.append(entry(fu, res)); ia_refs.append(fu)
            add_section("Investigation Advice", "721963009", "Order document", ia_refs)

            med_code = "721912009"
        else:
            inv_refs = []
            if is_filled(row.get("lab_test_name")) or is_filled(row.get("diagnostic_report_category")):
                imaging = str(row.get("diagnostic_report_category", "")).lower() == "imaging"
                fu, res = build_diagnostic_report(row, patient_fu, imaging=imaging)
                entries.append(entry(fu, res)); inv_refs.append(fu)
            add_section("Investigations", "721981007", "Diagnostic studies report", inv_refs)
            med_code = "1003606003"

        med_refs = []
        if is_filled(row.get("medication_name")):
            fu, res = build_medication_request(row, patient_fu)
            entries.append(entry(fu, res)); med_refs.append(fu)
        add_section("Medications", med_code, "Medication section", med_refs)

        proc_code = "371525003" if hi_type == "OPConsultation" else "1003640003"
        proc_refs = []
        if is_filled(row.get("procedure_text")):
            fu, res = build_procedure(row, patient_fu)
            entries.append(entry(fu, res)); proc_refs.append(fu)
        add_section("Procedure" if hi_type == "OPConsultation" else "Procedures", proc_code, "Procedure section", proc_refs)

        if hi_type == "OPConsultation":
            fu_refs = []
            if is_filled(row.get("follow_up_date")):
                fu, res = u(), {
                    "resourceType": "Appointment", "id": None, "status": "booked",
                    "start": f"{to_fhir_date(row['follow_up_date'])}T10:00:00+05:30",
                    "participant": [{"actor": {"reference": patient_fu}, "status": "accepted"}]
                }
                res["id"] = fu.split(":")[-1]
                entries.append(entry(fu, res)); fu_refs.append(fu)
            add_section("Follow Up", "390906007", "Follow-up encounter", fu_refs)

            ref_refs = []
            if is_filled(row.get("referral_text")):
                fu, res = build_service_request(row, patient_fu, row["referral_text"])
                entries.append(entry(fu, res)); ref_refs.append(fu)
            add_section("Referral", "306206005", "Referral to service", ref_refs)
        else:
            cp_refs = []
            if is_filled(row.get("advice_notes")):
                fu, res = u(), {
                    "resourceType": "CarePlan", "id": None, "status": "active", "intent": "plan",
                    "subject": {"reference": patient_fu}, "description": row["advice_notes"]
                }
                res["id"] = fu.split(":")[-1]
                entries.append(entry(fu, res)); cp_refs.append(fu)
            add_section("Care Plan", "734163000", "Care plan", cp_refs)

        doc_refs = []
        if is_filled(row.get("document_url")):
            fu, res = build_document_reference(row, patient_fu)
            entries.append(entry(fu, res)); doc_refs.append(fu)
        add_section("Document Reference", comp_code, comp_display, doc_refs)

    # ---------------- DiagnosticReportRecord ----------------
    elif hi_type == "DiagnosticReport":
        refs = []
        imaging = str(row.get("diagnostic_report_category", "")).lower() == "imaging"
        fu, res = build_diagnostic_report(row, patient_fu, imaging=imaging)
        entries.append(entry(fu, res)); refs.append(fu)
        if is_filled(row.get("document_url")):
            fu2, res2 = build_document_reference(row, patient_fu)
            entries.append(entry(fu2, res2)); refs.append(fu2)
        add_section("Investigation", "721981007", "Diagnostic studies report", refs)

    # ---------------- PrescriptionRecord ----------------
    elif hi_type == "Prescription":
        refs = []
        if is_filled(row.get("medication_name")):
            fu, res = build_medication_request(row, patient_fu)
            entries.append(entry(fu, res)); refs.append(fu)
        if is_filled(row.get("document_url")):
            fu, res = build_binary(row)  # Binary, not DocumentReference
            entries.append(entry(fu, res)); refs.append(fu)
        sec = {"entry": [{"reference": r} for r in refs]}
        if refs:
            sections.append(sec)

    # ---------------- HealthDocumentRecord ----------------
    elif hi_type == "HealthDocumentRecord":
        refs = []
        if is_filled(row.get("document_url")):
            fu, res = build_document_reference(row, patient_fu)
            entries.append(entry(fu, res)); refs.append(fu)
        sec = {"entry": [{"reference": r} for r in refs]}
        if refs:
            sections.append(sec)

    # ---------------- ImmunizationRecord ----------------
    elif hi_type == "ImmunizationRecord":
        refs = []
        if is_filled(row.get("immunization_vaccine_name")):
            fu, res = build_immunization(row, patient_fu)
            entries.append(entry(fu, res)); refs.append(fu)
        if is_filled(row.get("immunization_next_due_date")):
            fu, res = build_immunization_recommendation(row, patient_fu)
            entries.append(entry(fu, res)); refs.append(fu)
        if is_filled(row.get("document_url")):
            fu, res = build_document_reference(row, patient_fu)
            entries.append(entry(fu, res)); refs.append(fu)
        sec = {"entry": [{"reference": r} for r in refs]}
        if refs:
            sections.append(sec)

    # ---------------- WellnessRecord ----------------
    elif hi_type == "WellnessRecord":
        vitals_pairs = build_observation_vitals(row, patient_fu)
        vit_refs = []
        for fu, res in vitals_pairs:
            entries.append(entry(fu, res)); vit_refs.append(fu)
        add_section("Vital Signs", None, None, vit_refs)

        body_refs = []
        if is_filled(row.get("wellness_weight_kg")):
            fu, res = build_wellness_observation(row, patient_fu, "wellness_weight_kg", "29463-7", "Body weight", "kg", "ObservationBodyMeasurement")
            entries.append(entry(fu, res)); body_refs.append(fu)
        add_section("Body Measurement", None, None, body_refs)

        act_refs = []
        if is_filled(row.get("wellness_steps")):
            fu, res = build_wellness_observation(row, patient_fu, "wellness_steps", "55423-8", "Number of steps", "steps", "ObservationPhysicalActivity")
            entries.append(entry(fu, res)); act_refs.append(fu)
        add_section("Physical Activity", None, None, act_refs)

        life_refs = []
        if is_filled(row.get("wellness_sleep_hours")):
            fu, res = build_wellness_observation(row, patient_fu, "wellness_sleep_hours", "93832-4", "Sleep duration", "h", "ObservationLifestyle")
            entries.append(entry(fu, res)); life_refs.append(fu)
        add_section("Lifestyle", None, None, life_refs)

        doc_refs = []
        if is_filled(row.get("document_url")):
            fu, res = build_document_reference(row, patient_fu)
            entries.append(entry(fu, res)); doc_refs.append(fu)
        add_section("Other Wellness Records", None, None, doc_refs)

    if not sections:
        return None  # nothing to bundle for this row

    composition_id = str(uuid.uuid4())
    composition = {
        "resourceType": "Composition",
        "id": composition_id,
        "meta": {"profile": [f"https://nrces.in/ndhm/fhir/r4/StructureDefinition/{profile}"]},
        "language": "en-IN",
        "status": "final",
        "type": {"coding": [{"system": "http://snomed.info/sct", "code": comp_code, "display": comp_display}]},
        "subject": {"reference": patient_fu},
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30"),
        "title": f"{hi_type} Record",
        "section": sections,
    }
    if practitioner_fu:
        composition["author"] = [{"reference": practitioner_fu}]
    if encounter_fu:
        composition["encounter"] = {"reference": encounter_fu}
    if org_fu:
        composition["custodian"] = {"reference": org_fu}

    bundle = {
        "resourceType": "Bundle",
        "id": f"{hi_type}-{row.get('record_id', '')}",
        "meta": {"profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle"]},
        "identifier": {"system": "http://hip.in", "value": f"bundle-{row.get('record_id', '')}"},
        "type": "document",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+05:30"),
        "entry": [entry(f"urn:uuid:{composition_id}", composition)] + entries,
    }
    return bundle


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

generated = 0
skipped = 0
for _, row in df.iterrows():
    bundle = build_bundle_for_row(row)
    if bundle is None:
        skipped += 1
        continue
    fname = f"{row['record_id']}_{row['hi_type']}.json"
    with open(os.path.join(OUT_DIR, fname), "w") as f:
        json.dump(bundle, f, indent=2)
    generated += 1

print(f"Generated: {generated} bundles")
print(f"Skipped (no data / unrecognized hi_type): {skipped}")
