import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")

sys.path.insert(0, SRC_PATH)

import flat_table_manager as ftm


ftm.set_clinical_data(
    "P001",
    practitioner_name="Dr. Test",
    symptoms_text="Mild fever, headache",
    symptoms_snomed_code="386661006",
    vitals_bp_systolic="120",
    vitals_bp_diastolic="80",
    vitals_pulse="78",
    vitals_temp_c="37.5",
    vitals_spo2="98",
    diagnosis_text="Viral fever",
    diagnosis_snomed_code="386661006",
    medication_name="Paracetamol",
    medication_dosage="500 mg",
    medication_frequency="TDS",
    medication_duration_days="3",
    clinical_notes="Patient advised rest and adequate fluids."
)

print("Clinical data added successfully.")