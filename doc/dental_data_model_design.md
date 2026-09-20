# Dental Office Billing & Machine Learning Data Model Design

A relational data model for a dental group practice (MSO), designed for training predictive models on the revenue cycle: appointment attendance, claim denial, and patient balance collection.

The model is implemented by [`generate_dental_data.py`](generate_dental_data.py), which produces **20 referentially-integral tables** covering three benefit years (2023-09-01 → 2026-08-31). Generated output and its data dictionary live in [`data/`](data/README.md).

> **Revision note.** This is v2. Three things in v1 were wrong and have been corrected — most importantly the reminder relationship, where the diagram and the script contradicted each other. See [§2 Model Corrections](#2-model-corrections).

---

## 1. Entity-Relationship Architecture

### Coverage structure — who is covered, by whom, under what terms

```
                            [ Insurance_Networks ] (3)
                              │                   │
          ┌───────────────────┘                   └───────────────────┐
          ▼                                                           ▼
[ Office_Network_Participation ]                        [ Insurance_Company_Networks ]
   (each office joins 1–3)                                  (each company joins 1–3)
          │                                                           │
          ▼                                                           ▼
  [ Dental_Offices ] (20) ───►[ Office_Insurance_Network ]◄─── [ Insurance_Companies ] (9)
                                  DERIVED: In-Network                 │
                                  iff a network is shared             ▼
                                                          [ Insurance_Policies ] (35)
                                                                      │
                                    ┌─────────────────────────────────┼──────────────────┐
                                    ▼                                 ▼                  ▼
                       [ Primary_Policy_Holders ]            [ Coverage_Rules ] ◄─ [ Billing_Codes ]
                              (200)   │                       (policy × code)
                                      ▼
                          [ Policy_Dependents ] (596, 1–5 each)
                                      │
                                      ▼
                             [ Patients ] (796) ───► [ Patient_Benefit_Years ]
                                                      (deductible + annual max, per year)
```

### Activity and money — what happened, and who paid

```
[ Dental_Offices ] ──┐
                     ├──► [ Recall_Reminders ] ──► [ Appointments ] ──► [ Appointment_Reminders ]
[ Patients ] ────────┘     2 per patient/year      │   source_recall_id     1–3 per appointment
                           "you're due for a       │   is null for walk-ins  "your appointment
                            cleaning"              │   and follow-up care     is Tuesday at 2pm"
                                                   ▼
                                            [ Invoices ] ──► [ Invoice_Lines ] ──► [ Billing_Codes ]
                                                   │
                                                   ▼
                                       [ Claims_and_Payments ] ──► [ Claim_Disputes ]
```

### Relationships

| Child | Foreign key | Parent | Cardinality |
|---|---|---|---|
| `insurance_company_networks` | `insurance_company_id`, `network_id` | `insurance_companies`, `insurance_networks` | each company in 1–3 networks |
| `office_network_participation` | `office_id`, `network_id` | `dental_offices`, `insurance_networks` | each office in 1–3 networks |
| `office_insurance_network` | `office_id`, `insurance_company_id` | both | derived, every pair (20 × 9 = 180) |
| `insurance_policies` | `insurance_company_id` | `insurance_companies` | many policies per company |
| `coverage_rules` | `policy_id`, `billing_code_id` | `insurance_policies`, `billing_codes` | one rule per policy × code |
| `primary_policy_holders` | `policy_id`, `patient_id` | `insurance_policies`, `patients` | 1 subscriber : 1 patient |
| `policy_dependents` | `subscriber_id`, `patient_id` | `primary_policy_holders`, `patients` | 1–5 dependents per subscriber |
| `patient_benefit_years` | `patient_id`, `policy_id` | `patients`, `insurance_policies` | 1 row per patient per benefit year |
| `recall_reminders` | `office_id`, `patient_id` | `dental_offices`, `patients` | 2 per patient per benefit year |
| `appointments` | `office_id`, `patient_id`, `source_recall_id` | `dental_offices`, `patients`, `recall_reminders` | `source_recall_id` **nullable** |
| `appointment_reminders` | `appointment_id` | `appointments` | 1–3 per appointment |
| `invoices` | `appointment_id` | `appointments` | 1 : 1, completed appointments only |
| `invoice_lines` | `invoice_id`, `billing_code_id` | `invoices`, `billing_codes` | 1–5 lines per invoice |
| `claims_and_payments` | `invoice_id`, `policy_id` | `invoices`, `insurance_policies` | 1 : 1 with invoice |
| `claim_disputes` | `claim_id` | `claims_and_payments` | 0 : 1, denied claims only |

---

## 2. Model Corrections

### 2.1 Reminders pointed the wrong way — now two tables

**v1 said:** `Dental_Offices → Reminders → Appointments`.

**v1's script did the opposite:** it built the appointment first, then a reminder carrying `appointment_id` and `sent_timestamp = appointment_date − 2 days`. The diagram and the code could not both be right, and the script's reminder had no `office_id`, so the `Dental_Offices → Reminders` edge did not exist in the schema at all.

The underlying problem is that **a notice about an appointment that already exists cannot also be what causes that appointment**. Two different real-world objects were collapsed into one table:

| Table | What it is | Direction |
|---|---|---|
| `recall_reminders` | The recare notice: "you're due for a cleaning." Sent by an office to a patient **before any appointment exists**, and it is what prompts the booking. Carries `office_id` and `patient_id`. | **Parent** of `appointments` |
| `appointment_reminders` | The confirmation: "your appointment is Tuesday at 2pm." Sent about a booking that already exists. | **Child** of `appointments` |

Only recall-driven visits carry a `source_recall_id`; walk-ins, emergencies, and follow-up treatment leave it null (3,586 of 6,044 appointments come from a recall).

This split is also what makes the specification expressible: *2 cleaning reminders per patient per year* is a recall count, while *1–3 reminders per appointment* is a confirmation count. In v1's single table they were the same field and could not both hold.

### 2.2 Insurance networks are now first-class

**v1** linked each office to each insurance company directly and picked `network_status` at random per row — so the same office could be in-network with a payer on one claim and out-of-network on the next.

Networks are entities that both sides join independently, so the model now has `insurance_networks` (3), with companies joining 1–3 (`insurance_company_networks`) and offices joining 1–3 (`office_network_participation`). `office_insurance_network` is then **derived**: In-Network exactly when the two share at least one network, with `shared_network_id` recording which one. Status is now a stable consequence of structure, which is what makes the in/out-of-network fee difference meaningful across a patient's history.

### 2.3 Benefit accumulators belong to the patient, not the policy

**v1** kept `individual_deductible_met_ytd` and `family_deductible_met_ytd` on `insurance_policies`. A policy is an employer group covering many families, so one running total there would have every member of the group share a single deductible, with no reset between years.

`patient_benefit_years` now tracks `deductible_met`, `benefit_used`, and `benefit_remaining` **per patient, per benefit year**. Claims draw the annual maximum down in service-date order, and once it is exhausted the rest of that year's claims are denied `Max Benefit Exceeded` — reproducing a real failure mode instead of an arbitrary one.

---

## 3. Money Mechanics

Computed per invoice line, in this order:

```
contractual_writeoff       = standard_fee − allowed_amount          (in-network only)
deductible_applied         = drawn from patient_benefit_years, non-preventive lines only
estimated_insurance_amount = (allowed − deductible_applied − copay) × coinsurance,
                             capped at the patient's remaining annual maximum
estimated_patient_amount   = allowed_amount − estimated_insurance_amount
patient_balance            = estimated_copay_due − actual_patient_paid_at_visit
```

Plan design follows the standard dental split, held in `coverage_rules`:

| Category | Plan pays | Copay | Deductible applies |
|---|---|---|---|
| Preventive (exams, cleanings, x-rays, fluoride, sealants) | 100% | $0 | no |
| Basic (fillings, extractions, deep cleaning) | 80% | $20 | yes |
| Major (crowns, root canals, dentures, implants) | 50% | $50 | yes |

Allowed amounts differ by network status: in-network is 60–75% of the standard fee with the remainder written off contractually; out-of-network is 85–95% with no write-off, leaving the patient owing more.

---

## 4. Synthetic Data Generator

The generator is a standalone script, not inline code: **[`generate_dental_data.py`](generate_dental_data.py)**.

```bash
pip install pandas faker
python3 generate_dental_data.py      # ~2s, writes 20 CSVs to doc/data/
```

It is seeded (`SEED = 42`), so re-running reproduces the same dataset byte for byte. Scale is set by constants at the top of the file.

| Parameter | Value |
|---|---|
| Offices / networks / companies | 20 / 3 / 9 |
| Networks per company, per office | 1–3 |
| Primary policy holders | 200, each with 1–5 dependents (796 patients) |
| Cleaning recalls | 2 per patient per benefit year |
| Other services | 0–2 per patient per benefit year |
| Reminders per appointment | 1–3, at 14/7/3/2/1-day lead times |
| Benefit years | 2023-24, 2024-25, 2025-26 (Sep 1 → Aug 31) |

Output totals 50,760 rows: 4,776 recalls, 6,044 appointments, 11,789 appointment reminders, 5,232 invoices, 12,478 invoice lines, 5,232 claims, 132 disputes. Full column-level documentation is in [`data/README.md`](data/README.md).

### Behavioural rules worth knowing

- **No-shows are a patient trait, not a coin flip.** About 17% of patients carry a 30–55% no-show propensity and the rest 1–6%, which reproduces the observed pattern where a small minority of patients causes most missed appointments.
- **Seasonality is real.** December runs hottest (annual maximums expire), February and summer run cold.
- **Denial probability is built up from causes**, not assigned flat: a payer baseline of 8–22%, plus 25 points when major work goes out without prior authorization, plus 30 when the annual maximum is already exhausted, plus 5 out-of-network.
- **Visit composition is clinically sensible.** A cleaning visit bills a prophy (child or adult by age) plus an exam, with bitewings once a year and fluoride or sealants for younger patients — not a random draw from the code list.

---

## 5. Verified Characteristics

Every structural claim in this document is machine-checked by **[`validate_dental_data.py`](validate_dental_data.py)** — run it after any change to the generator:

```bash
python3 validate_dental_data.py     # exit 0 = doc and data agree
```

It verifies the 20 tables, all 27 foreign keys, every cardinality stated in §1, the money identities in §3, the plan design table, and that `network_status` really is derived (In-Network exactly when office and company share a network, and every claim agrees with `office_insurance_network`). Currently: all checks pass.

| Property | Generated | Real-world reference |
|---|---|---|
| Appointment status | 86.6% completed, 9.0% no-show, 4.5% cancelled | — |
| No-show concentration | worst 18% of patients → 73% of no-shows | 60–70% |
| Claim denial rate | 14.9% | 10–20% |
| Appeals overturned | 67% | ~69% |
| Mean days to adjudicate | 37.6 | 14–45 by payer |

## 6. Known Limitations

- **Appeal rate is deliberately high.** 17% of denials are appealed here against a real-world figure nearer 1%; at 1% the disputes table would hold ~8 rows. A staffed group practice appealing 17% is defensible, and it is one constant in the generator.
- **Procedure descriptions are plain-language, not ADA nomenclature**, which is copyrighted. The CDT code numbers themselves are facts and are real.
- **Fees are plausible commercial UCR amounts**, not calibrated to a published schedule. Real Medicaid allowed amounts for 325 CDT codes are available in the workshop repo at `doc/project-3/data/cdt-medicaid-allowed-amounts.csv`.
- **No secondary insurance or coordination of benefits**, and no capitation payment path — DHMO payers exist but adjudicate like PPO.
- **Patients never move between offices** inside the group.
