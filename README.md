# Eka Care ABDM M1 + M2 Setup

This README explains how to run the project from a fresh clone and reach the `abha.link_care_context` webhook with status `LINKED`.

## 1. Clone the Project

```powershell
git clone <REPOSITORY_URL>

```

## 2. Create Python Virtual Environment

```powershell
python -m venv venv
```

Activate it:

```powershell
venv\Scripts\activate
```

You should see:

```text
(venv)
```

## 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

If `requirements.txt` is not available, install the required packages defined by the project.

## 4. Configure Eka Credentials

Configure the Eka Care sandbox credentials required by:

```text
src/config.py
```

The configuration should contain the required values such as:

```text
EKA_ENV
EKA_CLIENT_ID
EKA_CLIENT_SECRET
EKA_HIP_ID
```

Do not commit client secrets or other credentials to Git.

## 5. M1 – ABHA Authentication

Complete the M1 ABHA authentication flow using the Eka Care sandbox.

After successful M1 authentication, obtain:

```text
ABHA Address
ABHA Number
OID / Eka Patient ID
Patient Name
Gender
Date of Birth
Mobile Number
```

Save the M1 response in:

```text
data/M1-sandbox.json
```

Example:

```text
ABHA Address = testinguser12@sbx
OID          = 178789437141310
```

## 6. Start the Webhook Server

The webhook server must be running **before** sending the Care Context Link request.

Open **Terminal 1**:

```powershell
venv\Scripts\activate
python src/webhook_server.py
```

Expected output:

```text
Running on http://127.0.0.1:5000
```

The application webhook endpoint is:

```text
http://127.0.0.1:5000/webhooks/eka
```

Keep this terminal running.

## 7. Start ngrok

Open **Terminal 2**.

Run:

```powershell
ngrok http 5000
```

ngrok will provide an HTTPS URL similar to:

```text
https://xxxx.ngrok-free.app
```

The complete webhook URL is:

```text
https://xxxx.ngrok-free.app/webhooks/eka
```

## 8. Register the Webhook in Eka Care

The Flask route:

```python
@app.route("/webhooks/eka", methods=["POST"])
```

only creates the endpoint in our application.

It does **not** automatically register the webhook with Eka.

Register the public URL:

```text
https://xxxx.ngrok-free.app/webhooks/eka
```

with Eka's webhook subscription API.

Register at least:

```text
abha.link_care_context
```

After registration, verify that Eka shows the webhook subscription as active.

## 9. Run M2 Phase 1

Open **Terminal 3**.

Activate the environment:

```powershell
venv\Scripts\activate
```

Run:

```powershell
python scripts/run_phase1_for_row.py `
  --row-id P001 `
  --m1-json "D:\path\to\m2_pipeline\data\M1-sandbox.json" `
  --encounter-id ENC-P001-001 `
  --encounter-date 2026-08-28 `
  --hi-type OPConsultation
```

Change the M1 JSON path to the actual location on your machine.

## 10. What the Script Does

`run_phase1_for_row.py` performs:

```text
M1 JSON
   ↓
Read patient identity
   ↓
Create a new record
   ↓
Generate Care Context
   ↓
Call Eka Care Link API
   ↓
Receive HTTP 202
   ↓
Wait for webhook
```

Expected output:

```text
Link request sent (202). Awaiting webhook for final status.
```

## 11. Important: 202 Is Not LINKED

When the Link API returns:

```text
202
```

it means Eka accepted the request for processing.

It does **not** mean the Care Context is already linked.

The final status is received asynchronously through:

```text
abha.link_care_context
```

## 12. Receive the Webhook

Eka sends the webhook to:

```text
https://xxxx.ngrok-free.app/webhooks/eka
```

ngrok forwards it to:

```text
http://127.0.0.1:5000/webhooks/eka
```

Flask receives it in:

```text
src/webhook_server.py
```

Expected payload:

```json
{
  "event": "abha.link_care_context",
  "data": {
    "care_context_id": "cc-xxxx",
    "status": "LINKED",
    "error": null
  }
}
```

## 13. Verify LINKED Status

The webhook server finds the matching record using:

```text
care_context_id
```

and updates the local record.

Expected:

```text
link_request_status = sent
link_status         = LINKED
linked_at           = <timestamp>
```

Check:

```text
data/master_flat_table.csv
```

## 14. Webhook Payload Backup

Every received webhook is saved as:

```text
data/webhook_last.json
```

This is useful for debugging.

## 15. Multiple Records for the Same Patient

The same patient can have multiple encounters.

Example:

```text
R001 | P001 | ENC-P001-001 | OPConsultation
R002 | P001 | ENC-P001-002 | Prescription
R003 | P001 | ENC-P001-003 | DiagnosticReport
```

The patient remains:

```text
P001
```

Each new encounter gets:

```text
new record_id
new encounter_id
new care_context_id
```

Example:

```powershell
python scripts/run_phase1_for_row.py `
  --row-id P001 `
  --m1-json "D:\path\to\M1-sandbox.json" `
  --encounter-id ENC-P001-002 `
  --encounter-date 2026-08-28 `
  --hi-type Prescription
```

## 16. Files Used for Phase 1

You normally only need to run:

```text
src/webhook_server.py
```

and:

```text
scripts/run_phase1_for_row.py
```

The other files are called automatically.

```text
src/
├── config.py
│     Configuration
├── eka_client.py
│     Eka API calls
├── flat_table_manager.py
│     CSV/record management
├── webhook_server.py
│     Receives Eka webhooks
├── fhir_builder.py
│     Used later for Phase 2
├── encryption.py
│     Used later for Phase 2
└── logging_utils.py
      Logging
```

## 17. Terminal Setup

### Terminal 1 – Flask

```powershell
venv\Scripts\activate
python src/webhook_server.py
```

### Terminal 2 – ngrok

```powershell
ngrok http 5000
```

### Terminal 3 – M2 Phase 1

```powershell
venv\Scripts\activate

python scripts/run_phase1_for_row.py `
  --row-id P001 `
  --m1-json "D:\path\to\M1-sandbox.json" `
  --encounter-id ENC-P001-001 `
  --encounter-date 2026-08-28 `
  --hi-type OPConsultation
```

## 18. Expected End Result

```text
M1
 ↓
ABHA Address + OID
 ↓
M2 Phase 1
 ↓
Create Care Context
 ↓
Eka Care Link API
 ↓
202 Accepted
 ↓
Eka processes request
 ↓
abha.link_care_context
 ↓
ngrok
 ↓
Flask webhook
 ↓
Find Care Context
 ↓
Update CSV
 ↓
LINKED
```

At the end, verify:

```text
data/master_flat_table.csv
```

and confirm:

```text
link_status = LINKED
```

Also check:

```text
data/webhook_last.json
```

to confirm that the webhook was received.
