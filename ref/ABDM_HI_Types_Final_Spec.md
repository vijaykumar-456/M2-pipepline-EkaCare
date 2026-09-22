# ABDM HI Types — Final Confirmed Specs

Source: live NRCES/ABDM FHIR Implementation Guide (nrces.in), verified section-by-section.
All resources sit loose in the Bundle; the Composition is always `entry[0]` and links to everything else by reference.

---

## 1. OPConsultRecord

`Composition.type = 371530004 "Clinical consultation report"`

| # | Section | Card. | SNOMED code | Entry resource(s) |
|---|---------|-------|-------------|---------------------|
| 1 | ChiefComplaints | 0..1 | 422843007 | Condition |
| 2 | PhysicalExamination | 0..1 | 425044008 | Observation |
| 3 | Allergies | 0..1 | 722446000 | AllergyIntolerance |
| 4 | MedicalHistory | 0..1 | 371529009 "History and physical report" | Condition \| Procedure |
| 5 | FamilyHistory | 0..1 | 422432008 | FamilyMemberHistory |
| 6 | InvestigationAdvice | 0..1 | 721963009 "Order document" | ServiceRequest |
| 7 | Medications | 0..1 | 721912009 "Medication summary document" | MedicationStatement \| MedicationRequest |
| 8 | FollowUp | 0..1 | 390906007 | Appointment |
| 9 | Procedure | 0..1 | 371525003 | Procedure |
| 10 | Referral | 0..1 | 306206005 | ServiceRequest |
| 11 | OtherObservations | 0..1 | 404684003 | Observation |
| 12 | DocumentReference | 0..1 | 371530004 | DocumentReference |

At least 1 of the 12 sections must be present. Sections are `Open At End` — you can add custom ones beyond these 12 if needed.

---

## 2. DiagnosticReportRecord

`Composition.type = 721981007 "Diagnostic studies report"`

| # | Section | Card. | Entry resource(s) |
|---|---------|-------|---------------------|
| 1 | Investigation | 1..1 | DiagnosticReportLab **or** DiagnosticReportImaging — pick the profile matching the actual test type, never both/either interchangeably |

---

## 3. PrescriptionRecord

`Composition.type = 440545006 "Prescription record"`

| # | Section | Card. | Entry resource(s) |
|---|---------|-------|---------------------|
| 1 | (single, unnamed, **closed** slice) | 1..1 | MedicationRequest (1..\*) + Binary (0..1) |

Nothing else is permitted in this section — no CarePlan/Advice, no DocumentReference for attachments (must be `Binary`).

---

## 4. DischargeSummaryRecord

`Composition.type = 373942005 "Discharge summary"`

| # | Section | Card. | SNOMED code | Entry resource(s) |
|---|---------|-------|-------------|---------------------|
| 1 | ChiefComplaints | 0..1 | 422843007 | Condition |
| 2 | PhysicalExamination | 0..1 | 425044008 | Observation |
| 3 | Allergies | 0..1 | 722446000 | AllergyIntolerance |
| 4 | MedicalHistory | 0..1 | 1003642006 "Past medical history section" | Procedure \| Condition |
| 5 | FamilyHistory | 0..1 | 422432008 | FamilyMemberHistory |
| 6 | Investigations | 0..1 | 721981007 | DiagnosticReportLab \| DiagnosticReportImaging |
| 7 | Medications | 0..1 | 1003606003 "Medication history section" | MedicationRequest |
| 8 | Procedures | 0..1 | 1003640003 "History of past procedure section" | Procedure |
| 9 | CarePlan | 0..1 | 734163000 | CarePlan |
| 10 | DocumentReference | 0..1 | 373942005 | DocumentReference |

At least 1 of the 10 sections must be present.

**Note:** MedicalHistory and Medications use different SNOMED codes here than in OPConsultRecord — don't reuse codes across profiles even for same-named sections.

---

## 5. HealthDocumentRecord

`Composition.type = 419891008 "Record artifact"`

| # | Section | Card. | Entry resource(s) |
|---|---------|-------|---------------------|
| 1 | (single, unnamed) | 1..1 | DocumentReference (1..\*) |

Simplest profile — a digital folder for scanned/legacy documents.

---

## 6. ImmunizationRecord

`Composition.type = 41000179103 "Immunization record"`

| # | Section | Card. | Entry resource(s) |
|---|---------|-------|---------------------|
| 1 | (single, unnamed, **closed** slice — exactly these 3 types) | 1..1 | Immunization (1..\*) + ImmunizationRecommendation (0..1) + DocumentReference (0..\*) |

---

## 7. WellnessRecord

`Composition.type` — wellness-specific (no single fixed SNOMED code confirmed; sections are sliced by `title`, not `code`)

| # | Section title (free-form, open-ended) | Entry resource(s) |
|---|----------------------------------------|---------------------|
| — | Any title, add as many as needed | ObservationVitalSigns, ObservationBodyMeasurement, ObservationPhysicalActivity, ObservationGeneralAssessment, ObservationWomenHealth, ObservationLifestyle, generic Observation, DocumentReference |

Only profile with open-ended (non-fixed) section list.

---

## Quick-reference: structural pattern by type

| Pattern | Types |
|---|---|
| Rich multi-section, fixed names, each 0..1 | OPConsultRecord (12 sections), DischargeSummaryRecord (10 sections) |
| Single fixed section, one resource choice | DiagnosticReportRecord, HealthDocumentRecord |
| Single fixed section, closed set of resource types | PrescriptionRecord, ImmunizationRecord |
| Open-ended sections | WellnessRecord only |

## Known bugs to fix in `fhir_builder.py` (confirmed against spec)

1. **DiagnosticReportRecord** — always emits `DiagnosticReportLab`, never `DiagnosticReportImaging` for imaging studies.
2. **PrescriptionRecord** — creates an illegal extra "Advice" section (CarePlan/Observation) not permitted by the closed slice.
3. **PrescriptionRecord** — attaches scanned Rx via `DocumentReference` instead of the required `Binary`.
4. **OPConsultRecord** — missing `FamilyHistory`, `Referral`, `OtherObservations` sections; `MedicalHistory` and `Medications` sections likely using the wrong (DischargeSummary) SNOMED codes instead of their own (371529009 / 721912009).
