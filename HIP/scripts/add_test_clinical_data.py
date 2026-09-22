import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src"
    )
)

import flat_table_manager as ftm


SYNTHETIC_DATA = {

    # R001 - OPConsultation
    "R001": {
        "practitioner_name": "Dr. Arun Kumar",
        "symptoms_text": "Fever, cough and sore throat",
        "symptoms_snomed_code": "267102003",
        "vitals_bp_systolic": "120",
        "vitals_bp_diastolic": "80",
        "vitals_pulse": "82",
        "vitals_temp_c": "38.2",
        "vitals_spo2": "98",
        "examination_notes": "Mild throat congestion. No respiratory distress.",
        "diagnosis_text": "Acute upper respiratory infection",
        "diagnosis_snomed_code": "54150009",
        "medical_history_text": "No significant past medical history",
        "advice_notes": "Rest, adequate fluids and follow-up if symptoms worsen.",
        "clinical_notes": "Patient evaluated during outpatient consultation.",
        "follow_up_date": "2026-09-01",
    },

    # R003 - HealthDocumentRecord
    "R003": {
        "practitioner_name": "Dr. Arun Kumar",
        "document_type": "Clinical Report",
        "document_filename": "clinical_report_P001_005.pdf",
        "clinical_notes": "Synthetic clinical document associated with the patient encounter.",
        "advice_notes": "Document available for future clinical reference.",
    },

    # R004 - Prescription
    "R004": {
        "practitioner_name": "Dr. Arun Kumar",
        "medication_name": "Paracetamol",
        "medication_dosage": "500 mg",
        "medication_frequency": "Twice daily",
        "medication_duration_days": "3",
        "advice_notes": "Take after food. Maintain adequate hydration.",
        "clinical_notes": "Medication prescribed for symptomatic fever management.",
    },

    # R005 - DiagnosticReport
    "R005": {
        "practitioner_name": "Dr. Arun Kumar",
        "lab_test_name": "Complete Blood Count",
        "lab_test_loinc_code": "57021-8",
        "lab_result_value": "Hemoglobin 13.8 g/dL; WBC 7200/uL; Platelets 245000/uL",
        "clinical_notes": "CBC performed as part of clinical evaluation.",
        "advice_notes": "Review laboratory results during follow-up consultation.",
    },
}


def main():

    print("Adding synthetic clinical data...")
    print()

    for record_id, clinical_data in SYNTHETIC_DATA.items():

        try:
            # Read existing record using your existing function.
            row = ftm.get_row(record_id)

            print(
                f"{record_id} | "
                f"Patient: {row.get('patient_name')} | "
                f"HI Type: {row.get('hi_type')} | "
                f"Care Context: {row.get('care_context_id')}"
            )

            # Update ONLY clinical fields.
            ftm.set_clinical_data(
                record_id,
                **clinical_data
            )

            print(
                f"  Updated {len(clinical_data)} clinical fields."
            )

        except ValueError as e:
            print(f"  ERROR: {e}")

        except Exception as e:
            print(f"  ERROR updating {record_id}: {e}")

        print()

    print("Done.")
    print()
    print("Existing records were updated.")
    print("No new Care Contexts were created.")
    print("record_id, care_context_id and link_status were not changed.")


if __name__ == "__main__":
    main()