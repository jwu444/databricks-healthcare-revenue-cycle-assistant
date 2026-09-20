"""
Synthetic dental group-practice (MSO) billing data generator.

Implements the model in doc/dental_data_model_design.md with two corrections and
several additions - see MODEL NOTES below.

Scale (per assignment):
    20 dental offices
    3 insurance networks
    9 insurance companies, each participating in 1-3 networks
    200 primary policy holders, each with 1-5 dependents
    2 cleaning recall reminders per patient per benefit year
    1-3 confirmation reminders per appointment
    0-2 additional (non-cleaning) services per patient per benefit year

Period: three benefit years, 2023-09-01 through 2026-08-31.

MODEL NOTES - where this differs from the design doc
----------------------------------------------------
1. Reminders split in two. The doc's diagram shows
   Dental_Offices -> Reminders -> Appointments, but its script builds the
   opposite: a reminder carrying appointment_id, sent two days before a known
   appointment. A notice sent about an appointment that already exists cannot
   also be what causes it. The two real-world things are separated here:

     recall_reminders      - "you are due for a cleaning", sent by an office to
                             a patient before any appointment exists. Parent of
                             appointments via appointments.source_recall_id.
                             This is the diagram's intent, and it is what the
                             "2 reminders per patient per year" requirement means.
     appointment_reminders - "your appointment is Tuesday at 2pm", a child of an
                             existing appointment. This is what the doc's script
                             actually built.

   Note that recall_reminders carries office_id and patient_id directly; in the
   doc's version reminders had neither, so the Dental_Offices -> Reminders edge
   in the diagram did not exist in the schema.

2. Networks are a first-class entity. The doc linked offices to insurance
   companies directly. Here, companies participate in networks and offices
   contract with networks; office_insurance_network is derived from a shared
   network, so in-network status is a consequence of the structure rather than a
   coin flip.

3. Benefit accumulators moved to the patient. The doc kept deductible_met_ytd on
   the policy, which would make a family share one running total across years.
   patient_benefit_years holds per-patient, per-year deductible and annual
   maximum consumption, and claims draw the maximum down in date order.

Usage:  python3 generate_dental_data.py
Output: doc/data/*.csv  (deterministic; seeded)
"""

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
SEED = 42
NUM_OFFICES = 20
NUM_NETWORKS = 3
NUM_INSURANCE_CO = 9
NUM_SUBSCRIBERS = 200
DEPENDENTS_PER_SUBSCRIBER = (1, 5)
CLEANINGS_PER_YEAR = 2
OTHER_SERVICES_PER_YEAR = (0, 2)

PERIOD_START = date(2023, 9, 1)
BENEFIT_YEARS = [
    ("2023-24", date(2023, 9, 1), date(2024, 8, 31)),
    ("2024-25", date(2024, 9, 1), date(2025, 8, 31)),
    ("2025-26", date(2025, 9, 1), date(2026, 8, 31)),
]

OUT_DIR = Path(__file__).parent / "data"

fake = Faker()
Faker.seed(SEED)
random.seed(SEED)

# ----------------------------------------------------------------------------
# Reference data
# ----------------------------------------------------------------------------
# Real CDT code numbers with short generic descriptions. Full ADA nomenclature is
# copyrighted, so descriptions here are plain-language, not the ADA wording.
BILLING_CODES = [
    # code,   description,                      category,     UCR fee, prior auth
    ("D0120", "Periodic oral exam",             "preventive",    75.0, False),
    ("D0150", "Comprehensive oral exam",        "preventive",   120.0, False),
    ("D0274", "Bitewing x-rays, four films",    "preventive",    85.0, False),
    ("D0140", "Limited problem-focused exam",   "preventive",    95.0, False),
    ("D0210", "Full mouth x-ray series",        "preventive",   160.0, False),
    ("D1110", "Adult cleaning",                 "preventive",   120.0, False),
    ("D1120", "Child cleaning",                 "preventive",    95.0, False),
    ("D1206", "Fluoride varnish",               "preventive",    45.0, False),
    ("D1351", "Sealant, per tooth",             "preventive",    65.0, False),
    ("D2140", "Amalgam filling, one surface",   "basic",        175.0, False),
    ("D2391", "Composite filling, one surface", "basic",        210.0, False),
    ("D2392", "Composite filling, two surface", "basic",        265.0, False),
    ("D4341", "Deep cleaning, per quadrant",    "basic",        295.0, False),
    ("D7140", "Simple extraction",              "basic",        225.0, False),
    ("D2740", "Porcelain crown",                "major",       1250.0, True),
    ("D2750", "Porcelain-metal crown",          "major",       1150.0, True),
    ("D2950", "Core buildup",                   "major",        320.0, False),
    ("D3220", "Pulpotomy",                      "major",        280.0, False),
    ("D3330", "Root canal, molar",              "major",       1100.0, True),
    ("D5110", "Complete upper denture",         "major",       1650.0, True),
    ("D6010", "Surgical implant placement",     "major",       2200.0, True),
    ("D7210", "Surgical extraction",            "major",        395.0, False),
]

# Coinsurance the plan pays, by procedure category - the standard 100/80/50 split
PLAN_COINSURANCE = {"preventive": 1.00, "basic": 0.80, "major": 0.50}
PLAN_COPAY = {"preventive": 0.0, "basic": 20.0, "major": 50.0}

DENIAL_REASONS = [
    ("Missing X-Ray", 0.22),
    ("Prior Auth Required", 0.18),
    ("Max Benefit Exceeded", 0.16),
    ("Frequency Limit Exceeded", 0.15),
    ("Coverage Terminated", 0.11),
    ("Coding Error", 0.10),
    ("Timely Filing Expired", 0.08),
]

# Month multipliers: December spike (patients burning the annual maximum before
# it resets), summer dip, January slow start after deductibles reset.
MONTH_WEIGHT = {1: 0.85, 2: 1.00, 3: 1.10, 4: 1.05, 5: 1.05, 6: 0.90,
                7: 0.80, 8: 0.95, 9: 1.10, 10: 1.10, 11: 1.05, 12: 1.35}


def weighted_choice(pairs):
    vals, weights = zip(*pairs)
    return random.choices(vals, weights=weights)[0]


def random_date_in(start, end):
    """Pick a date in [start, end], biased by month seasonality."""
    span = (end - start).days
    for _ in range(12):
        d = start + timedelta(days=random.randint(0, span))
        if random.random() < MONTH_WEIGHT[d.month] / max(MONTH_WEIGHT.values()):
            return d
    return start + timedelta(days=random.randint(0, span))


def business_datetime(d):
    """Put a date into a plausible appointment slot on a weekday."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return datetime(d.year, d.month, d.day, random.randint(8, 16), random.choice([0, 15, 30, 45]))


# Lead times an office actually uses, furthest out first. An appointment gets
# 1-3 reminders drawn from these, so a patient may get a save-the-date, a
# confirmation, and a day-before nudge.
REMINDER_LEAD_DAYS = [14, 7, 3, 2, 1]


def make_appointment_reminders(next_id, appointment_id, appt_dt, status):
    """1-3 reminders for one appointment. Returns (rows, next_id)."""
    rows = []
    n = weighted_choice([(1, 0.30), (2, 0.45), (3, 0.25)])
    leads = sorted(random.sample(REMINDER_LEAD_DAYS, n), reverse=True)
    for i, lead in enumerate(leads):
        is_last = i == len(leads) - 1
        # further out is email, closer in is SMS, phone for a final confirmation
        channel = weighted_choice([("Email", 0.60), ("SMS", 0.35), ("Phone Call", 0.05)]) if lead >= 7 \
            else weighted_choice([("SMS", 0.65), ("Phone Call", 0.20), ("Email", 0.15)])
        if status == "Completed":
            response = weighted_choice([("Confirmed", 0.75), ("No Response", 0.25)]) if is_last \
                else weighted_choice([("No Response", 0.60), ("Confirmed", 0.40)])
        else:
            response = weighted_choice([("No Response", 0.70), ("Requested Reschedule", 0.30)])
        rows.append({
            "appointment_reminder_id": next_id, "appointment_id": appointment_id,
            "reminder_sequence": i + 1, "lead_days": lead,
            "communication_channel": channel,
            "sent_timestamp": appt_dt - timedelta(days=lead),
            "delivery_status": weighted_choice([("Delivered", 0.97), ("Bounced", 0.03)]),
            "patient_response": response,
        })
        next_id += 1
    return rows, next_id


print("Generating synthetic dental data model...")

# ----------------------------------------------------------------------------
# 1. Dental offices
# ----------------------------------------------------------------------------
STATES = ["VA", "MD", "DC", "NC", "PA"]
offices = []
for i in range(1, NUM_OFFICES + 1):
    specialty = weighted_choice([("General Dentistry", 0.70), ("Pediatric Dentistry", 0.15),
                                 ("Orthodontics", 0.10), ("Oral Surgery", 0.05)])
    offices.append({
        "office_id": i,
        "office_name": f"{fake.last_name()} Dental Care",
        "city": fake.city(),
        "state": random.choice(STATES),
        "zip_code": fake.zipcode(),
        "specialty_type": specialty,
        "provider_count": random.randint(2, 8),
        "opened_date": fake.date_between(start_date="-15y", end_date="-2y"),
    })
df_offices = pd.DataFrame(offices)

# ----------------------------------------------------------------------------
# 2. Insurance networks, companies, and participation
# ----------------------------------------------------------------------------
NETWORK_NAMES = ["Atlantic Dental Network", "Summit Preferred Dental", "Keystone Care Network"]
df_networks = pd.DataFrame([
    {"network_id": i + 1,
     "network_name": NETWORK_NAMES[i],
     "network_type": ["PPO", "PPO", "DHMO"][i],
     "region": ["Mid-Atlantic", "National", "Regional"][i]}
    for i in range(NUM_NETWORKS)
])

ins_companies = []
for i in range(1, NUM_INSURANCE_CO + 1):
    payer_type = weighted_choice([("Commercial PPO", 0.60), ("DHMO", 0.22), ("Medicaid", 0.18)])
    ins_companies.append({
        "insurance_company_id": i,
        "company_name": f"{fake.last_name()} {random.choice(['Health', 'Dental', 'Benefit'])} Insurance",
        "payer_type": payer_type,
        "average_reimbursement_turnaround_days": random.randint(14, 45),
        "denial_rate_baseline": round(random.uniform(0.08, 0.22), 3),
    })
df_ins_companies = pd.DataFrame(ins_companies)

# Each company participates in 1-3 networks
company_networks, cn_id = [], 1
for _, co in df_ins_companies.iterrows():
    for net_id in random.sample(range(1, NUM_NETWORKS + 1), random.randint(1, NUM_NETWORKS)):
        company_networks.append({
            "company_network_id": cn_id,
            "insurance_company_id": int(co["insurance_company_id"]),
            "network_id": net_id,
            "participation_start_date": fake.date_between(start_date="-8y", end_date="-1y"),
        })
        cn_id += 1
df_company_networks = pd.DataFrame(company_networks)

# Each office contracts with 1-3 networks
office_networks, on_id = [], 1
for _, off in df_offices.iterrows():
    for net_id in random.sample(range(1, NUM_NETWORKS + 1), random.randint(1, NUM_NETWORKS)):
        office_networks.append({
            "office_network_id": on_id,
            "office_id": int(off["office_id"]),
            "network_id": net_id,
            "contract_start_date": fake.date_between(start_date="-6y", end_date="-1y"),
        })
        on_id += 1
df_office_networks = pd.DataFrame(office_networks)

# office <-> company status, derived: in-network iff they share a network
office_net_map = df_office_networks.groupby("office_id")["network_id"].apply(set).to_dict()
company_net_map = df_company_networks.groupby("insurance_company_id")["network_id"].apply(set).to_dict()

office_insurance, assoc_id = [], 1
for o_id, o_nets in office_net_map.items():
    for c_id, c_nets in company_net_map.items():
        shared = o_nets & c_nets
        office_insurance.append({
            "association_id": assoc_id,
            "office_id": o_id,
            "insurance_company_id": c_id,
            "shared_network_id": min(shared) if shared else None,
            "network_status": "In-Network" if shared else "Out-of-Network",
        })
        assoc_id += 1
df_office_insurance = pd.DataFrame(office_insurance)
NETWORK_STATUS = {(r.office_id, r.insurance_company_id): r.network_status
                  for r in df_office_insurance.itertuples()}

# ----------------------------------------------------------------------------
# 3. Policies (employer groups)
# ----------------------------------------------------------------------------
NUM_POLICIES = 35
policies = []
for i in range(1, NUM_POLICIES + 1):
    ded = random.choice([50.0, 75.0, 100.0, 150.0])
    policies.append({
        "policy_id": i,
        "insurance_company_id": random.randint(1, NUM_INSURANCE_CO),
        "policy_group_number": f"GRP-{random.randint(10000, 99999)}",
        "group_name": f"{fake.company()}",
        "individual_deductible_per_year": ded,
        "family_deductible_per_year": ded * 3,
        "annual_maximum_benefit": random.choice([1000.0, 1500.0, 2000.0, 2500.0]),
        "waiting_period_months_major": random.choice([0, 0, 6, 12]),
        "effective_date": fake.date_between(start_date="-6y", end_date="-1y"),
    })
df_policies = pd.DataFrame(policies)
POLICY = {r.policy_id: r for r in df_policies.itertuples()}

# ----------------------------------------------------------------------------
# 4. Patients, subscribers, dependents
# ----------------------------------------------------------------------------
patients, subscribers, dependents = [], [], []
patient_id = 1
dep_id = 1

for sub_id in range(1, NUM_SUBSCRIBERS + 1):
    policy_id = random.randint(1, NUM_POLICIES)

    # primary policy holder
    sub_patient_id = patient_id
    patients.append({
        "patient_id": patient_id, "first_name": fake.first_name(), "last_name": fake.last_name(),
        "age": random.randint(26, 68), "gender": weighted_choice([("F", 0.51), ("M", 0.47), ("O", 0.02)]),
        "zip_code": fake.zipcode(), "state": random.choice(STATES),
        "enrollment_date": fake.date_between(start_date="-6y", end_date=PERIOD_START),
        "patient_role": "Subscriber",
    })
    patient_id += 1

    subscribers.append({
        "subscriber_id": sub_id, "policy_id": policy_id, "patient_id": sub_patient_id,
        "employment_status": weighted_choice([("Employed", 0.82), ("Retired", 0.11), ("Unemployed", 0.07)]),
        "coverage_tier": None,  # filled after dependents are known
    })

    n_deps = random.randint(*DEPENDENTS_PER_SUBSCRIBER)
    has_spouse = random.random() < 0.75
    for k in range(n_deps):
        if k == 0 and has_spouse:
            rel, age = "Spouse", random.randint(25, 66)
        else:
            rel, age = "Child", random.randint(2, 24)
        patients.append({
            "patient_id": patient_id, "first_name": fake.first_name(), "last_name": fake.last_name(),
            "age": age, "gender": weighted_choice([("F", 0.50), ("M", 0.48), ("O", 0.02)]),
            "zip_code": fake.zipcode(), "state": random.choice(STATES),
            "enrollment_date": fake.date_between(start_date="-6y", end_date=PERIOD_START),
            "patient_role": "Dependent",
        })
        dependents.append({
            "dependent_id": dep_id, "subscriber_id": sub_id, "patient_id": patient_id,
            "relationship_to_subscriber": rel,
        })
        dep_id += 1
        patient_id += 1

    subscribers[-1]["coverage_tier"] = "Employee + Family" if n_deps > 1 else "Employee + One"

df_patients = pd.DataFrame(patients)
df_subscribers = pd.DataFrame(subscribers)
df_dependents = pd.DataFrame(dependents)

# patient -> policy lookup (dependents inherit the subscriber's policy)
patient_policy = {r.patient_id: r.policy_id for r in df_subscribers.itertuples()}
sub_policy = dict(patient_policy)
for r in df_dependents.itertuples():
    patient_policy[r.patient_id] = sub_policy[
        df_subscribers.loc[df_subscribers["subscriber_id"] == r.subscriber_id, "patient_id"].iloc[0]]

# Each patient has a home office and a personal no-show propensity. Per the
# domain research, 60-70% of no-shows come from 15-20% of patients, so this is a
# patient-level trait rather than an independent coin flip per appointment.
patient_office, patient_noshow = {}, {}
for pid in df_patients["patient_id"]:
    patient_office[pid] = random.randint(1, NUM_OFFICES)
    patient_noshow[pid] = random.uniform(0.30, 0.55) if random.random() < 0.17 else random.uniform(0.01, 0.06)

# ----------------------------------------------------------------------------
# 5. Billing codes and coverage rules
# ----------------------------------------------------------------------------
billing_codes = []
for i, (code, desc, cat, fee, auth) in enumerate(BILLING_CODES, start=1):
    billing_codes.append({
        "billing_code_id": i, "ada_procedure_code": code, "description": desc,
        "procedure_category": cat, "standard_fee": fee,
        "in_network_allowed_amount": round(fee * random.uniform(0.60, 0.75), 2),
        "out_network_allowed_amount": round(fee * random.uniform(0.85, 0.95), 2),
        "requires_prior_auth": auth,
    })
df_billing_codes = pd.DataFrame(billing_codes)
CODE = {r.billing_code_id: r for r in df_billing_codes.itertuples()}
CODES_BY_CAT = df_billing_codes.groupby("procedure_category")["billing_code_id"].apply(list).to_dict()
CODE_BY_CDT = {r.ada_procedure_code: r.billing_code_id for r in df_billing_codes.itertuples()}

coverage_rules, rule_id = [], 1
for p_id in df_policies["policy_id"]:
    for bc in df_billing_codes.itertuples():
        coverage_rules.append({
            "rule_id": rule_id, "policy_id": int(p_id), "billing_code_id": bc.billing_code_id,
            "copay_flat_amount": PLAN_COPAY[bc.procedure_category],
            "coinsurance_percentage": PLAN_COINSURANCE[bc.procedure_category],
            "deductible_applies": bc.procedure_category != "preventive",
            "frequency_limit_per_year": 2 if bc.procedure_category == "preventive" else None,
        })
        rule_id += 1
df_coverage_rules = pd.DataFrame(coverage_rules)
RULE = {(r.policy_id, r.billing_code_id): r for r in df_coverage_rules.itertuples()}

# ----------------------------------------------------------------------------
# 6. Recall reminders -> appointments -> appointment reminders
# ----------------------------------------------------------------------------
recalls, appointments, appt_reminders = [], [], []
recall_id = appt_id = appt_rem_id = 1

for py_label, py_start, py_end in BENEFIT_YEARS:
    for pid in df_patients["patient_id"]:
        office_id = patient_office[pid]
        age = int(df_patients.loc[df_patients["patient_id"] == pid, "age"].iloc[0])

        # --- 2 cleaning recalls per patient per year, roughly six months apart
        for half in range(CLEANINGS_PER_YEAR):
            win_start = py_start + timedelta(days=half * 182)
            win_end = min(win_start + timedelta(days=181), py_end)
            due = random_date_in(win_start, win_end)
            sent = due - timedelta(days=random.randint(7, 21))

            channel = weighted_choice([("SMS", 0.45), ("Email", 0.40), ("Phone Call", 0.15)])
            delivery = weighted_choice([("Delivered", 0.96), ("Bounced", 0.04)])
            booked = delivery == "Delivered" and random.random() < 0.78
            response = ("Scheduled" if booked else
                        weighted_choice([("No Response", 0.62), ("Declined", 0.23), ("Requested Later Date", 0.15)]))

            recalls.append({
                "recall_id": recall_id, "office_id": office_id, "patient_id": int(pid),
                "benefit_year": py_label, "recall_type": "Cleaning",
                "due_date": due, "sent_timestamp": datetime(sent.year, sent.month, sent.day, 9, 0),
                "communication_channel": channel, "delivery_status": delivery,
                "patient_response": response, "resulted_in_appointment": booked,
            })

            if booked:
                appt_date = due + timedelta(days=random.randint(0, 30))
                if appt_date > py_end:
                    appt_date = py_end
                status = weighted_choice([("No-Show", patient_noshow[pid]),
                                          ("Cancelled", 0.05),
                                          ("Completed", 1 - patient_noshow[pid] - 0.05)])
                appointments.append({
                    "appointment_id": appt_id, "office_id": office_id, "patient_id": int(pid),
                    "source_recall_id": recall_id, "visit_type": "Cleaning",
                    "benefit_year": py_label,
                    "appointment_date_time": business_datetime(appt_date),
                    "appointment_status": status,
                })
                # 1-3 confirmation reminders - children of the appointment
                rows, appt_rem_id = make_appointment_reminders(
                    appt_rem_id, appt_id, appointments[-1]["appointment_date_time"], status)
                appt_reminders.extend(rows)
                appt_id += 1
            recall_id += 1

        # --- 0-2 other (non-cleaning) services per patient per year
        for _ in range(random.randint(*OTHER_SERVICES_PER_YEAR)):
            appt_date = random_date_in(py_start, py_end)
            status = weighted_choice([("No-Show", patient_noshow[pid] * 0.6),
                                      ("Cancelled", 0.04),
                                      ("Completed", 1 - patient_noshow[pid] * 0.6 - 0.04)])
            visit_type = weighted_choice([("Restorative", 0.55), ("Emergency", 0.25), ("Major", 0.20)])
            appointments.append({
                "appointment_id": appt_id, "office_id": office_id, "patient_id": int(pid),
                "source_recall_id": None, "visit_type": visit_type, "benefit_year": py_label,
                "appointment_date_time": business_datetime(appt_date),
                "appointment_status": status,
            })
            rows, appt_rem_id = make_appointment_reminders(
                appt_rem_id, appt_id, appointments[-1]["appointment_date_time"], status)
            appt_reminders.extend(rows)
            appt_id += 1

df_recalls = pd.DataFrame(recalls)
df_appointments = pd.DataFrame(appointments).sort_values("appointment_date_time").reset_index(drop=True)
df_appt_reminders = pd.DataFrame(appt_reminders)

# ----------------------------------------------------------------------------
# 7. Benefit-year accumulators per patient
# ----------------------------------------------------------------------------
accum = {}  # (patient_id, benefit_year) -> dict
for pid in df_patients["patient_id"]:
    pol = POLICY[patient_policy[int(pid)]]
    for label, _, _ in BENEFIT_YEARS:
        accum[(int(pid), label)] = {
            "deductible_limit": pol.individual_deductible_per_year, "deductible_met": 0.0,
            "annual_maximum": pol.annual_maximum_benefit, "benefit_used": 0.0,
        }

# ----------------------------------------------------------------------------
# 8. Invoices, lines, claims, disputes
# ----------------------------------------------------------------------------
def visit_codes(visit_type, age, seen_codes_this_year):
    """Pick a clinically sensible set of procedures for one visit."""
    if visit_type == "Cleaning":
        codes = [CODE_BY_CDT["D1120" if age < 14 else "D1110"],
                 CODE_BY_CDT["D0150" if "exam" not in seen_codes_this_year else "D0120"]]
        if "bitewing" not in seen_codes_this_year:
            codes.append(CODE_BY_CDT["D0274"])
            seen_codes_this_year.add("bitewing")
        if age < 18 and random.random() < 0.55:
            codes.append(CODE_BY_CDT["D1206"])
        if age < 16 and random.random() < 0.20:
            codes.append(CODE_BY_CDT["D1351"])
        seen_codes_this_year.add("exam")
        return codes
    if visit_type == "Restorative":
        return random.sample(CODES_BY_CAT["basic"], k=random.randint(1, 2))
    if visit_type == "Emergency":
        return [CODE_BY_CDT["D0140"], random.choice(CODES_BY_CAT["basic"])]
    return random.sample(CODES_BY_CAT["major"], k=1) + (
        [CODE_BY_CDT["D2950"]] if random.random() < 0.35 else [])


invoices, invoice_lines, claims, disputes = [], [], [], []
line_id = claim_id = dispute_id = 1
seen_by_patient_year = {}

completed = df_appointments[df_appointments["appointment_status"] == "Completed"]

for appt in completed.itertuples():
    pid, oid, py = appt.patient_id, appt.office_id, appt.benefit_year
    policy_id = patient_policy[pid]
    pol = POLICY[policy_id]
    co_id = pol.insurance_company_id
    net_status = NETWORK_STATUS[(oid, co_id)]
    acc = accum[(pid, py)]
    age = int(df_patients.loc[df_patients["patient_id"] == pid, "age"].iloc[0])
    seen = seen_by_patient_year.setdefault((pid, py), set())

    code_ids = visit_codes(appt.visit_type, age, seen)
    svc_date = appt.appointment_date_time.date()

    gross = allowed_total = ins_est = pat_resp = writeoff_total = 0.0
    needs_auth = False

    for bc_id in code_ids:
        code = CODE[bc_id]
        rule = RULE[(policy_id, bc_id)]
        allowed = code.in_network_allowed_amount if net_status == "In-Network" else code.out_network_allowed_amount
        writeoff = round(code.standard_fee - allowed, 2) if net_status == "In-Network" else 0.0

        ded_applied = 0.0
        if rule.deductible_applies and acc["deductible_met"] < acc["deductible_limit"]:
            ded_applied = min(acc["deductible_limit"] - acc["deductible_met"], allowed)
            acc["deductible_met"] += ded_applied

        base = max(allowed - ded_applied - rule.copay_flat_amount, 0.0)
        est_ins = round(base * rule.coinsurance_percentage, 2)
        remaining = max(acc["annual_maximum"] - acc["benefit_used"], 0.0)
        est_ins = min(est_ins, remaining)
        acc["benefit_used"] += est_ins
        est_pat = round(allowed - est_ins, 2)
        needs_auth = needs_auth or code.requires_prior_auth

        invoice_lines.append({
            "line_id": line_id, "invoice_id": appt.appointment_id, "billing_code_id": bc_id,
            "ada_procedure_code": code.ada_procedure_code, "procedure_category": code.procedure_category,
            "unit_price": code.standard_fee, "quantity": 1, "allowed_amount": allowed,
            "contractual_writeoff": writeoff, "deductible_applied": round(ded_applied, 2),
            "estimated_insurance_amount": est_ins, "estimated_patient_amount": est_pat,
            "discount_applied": 0.0,
        })
        line_id += 1
        gross += code.standard_fee
        allowed_total += allowed
        writeoff_total += writeoff
        ins_est += est_ins
        pat_resp += est_pat

    paid_at_visit = round(pat_resp * weighted_choice([(1.0, 0.55), (0.5, 0.15), (0.0, 0.30)]), 2)
    invoices.append({
        "invoice_id": appt.appointment_id, "appointment_id": appt.appointment_id,
        "office_id": oid, "patient_id": pid, "policy_id": policy_id, "benefit_year": py,
        "service_date": svc_date,
        "total_gross_amount": round(gross, 2), "total_allowed_amount": round(allowed_total, 2),
        "total_contractual_writeoff": round(writeoff_total, 2),
        "estimated_insurance_responsibility": round(ins_est, 2),
        "estimated_copay_due": round(pat_resp, 2),
        "actual_patient_paid_at_visit": paid_at_visit,
        "patient_balance": round(pat_resp - paid_at_visit, 2),
        "due_date": svc_date + timedelta(days=30),
    })

    # ---- claim adjudication
    co = df_ins_companies.loc[df_ins_companies["insurance_company_id"] == co_id].iloc[0]
    p_denial = float(co["denial_rate_baseline"])
    if needs_auth and random.random() < 0.5:
        p_denial += 0.25                      # major work submitted without auth
    if acc["benefit_used"] >= acc["annual_maximum"]:
        p_denial += 0.30                      # annual maximum exhausted
    if net_status == "Out-of-Network":
        p_denial += 0.05
    is_denied = random.random() < min(p_denial, 0.85)

    submitted = svc_date + timedelta(days=random.randint(0, 5))
    turnaround = int(co["average_reimbursement_turnaround_days"]) + random.randint(-5, 12)
    adjudicated = submitted + timedelta(days=max(turnaround, 5))

    if is_denied:
        reason = ("Max Benefit Exceeded" if acc["benefit_used"] >= acc["annual_maximum"]
                  else "Prior Auth Required" if needs_auth
                  else weighted_choice(DENIAL_REASONS))
        status, amt_paid = "Denied", 0.0
    else:
        reason, status, amt_paid = None, "Clean-Paid", round(ins_est, 2)

    claims.append({
        "claim_id": claim_id, "invoice_id": appt.appointment_id, "policy_id": policy_id,
        "patient_id": pid, "office_id": oid, "insurance_company_id": int(co_id),
        "network_status": net_status, "benefit_year": py,
        "service_date": svc_date, "submitted_date": submitted,
        "adjudicated_date": adjudicated, "days_to_adjudicate": (adjudicated - submitted).days,
        "amount_claimed": round(ins_est, 2), "amount_paid": amt_paid,
        "claim_status": status, "denial_reason_code": reason,
        "required_prior_auth": needs_auth,
    })

    # ---- disputes: only ~1 in 6 denials is ever appealed, and most appeals win
    if is_denied and random.random() < 0.17:
        outcome = weighted_choice([("Overturned-Paid", 0.66), ("Upheld-Denied", 0.34)])
        disputes.append({
            "dispute_id": dispute_id, "claim_id": claim_id,
            "dispute_date": adjudicated + timedelta(days=random.randint(5, 45)),
            "dispute_reason_category": ("Medical Necessity" if reason in ("Prior Auth Required", "Missing X-Ray")
                                        else "Benefit Limit" if reason == "Max Benefit Exceeded"
                                        else "Administrative Error"),
            "current_appeal_level": random.choice([1, 1, 1, 2]),
            "dispute_outcome": outcome,
            "resolved_date": adjudicated + timedelta(days=random.randint(46, 120)),
            "amount_recovered": round(ins_est, 2) if outcome == "Overturned-Paid" else 0.0,
        })
        dispute_id += 1
    claim_id += 1

df_invoices = pd.DataFrame(invoices)
df_invoice_lines = pd.DataFrame(invoice_lines)
df_claims = pd.DataFrame(claims)
df_disputes = pd.DataFrame(disputes)

df_benefit_years = pd.DataFrame([
    {"patient_id": pid, "benefit_year": py, "policy_id": patient_policy[pid],
     "individual_deductible": v["deductible_limit"], "deductible_met": round(v["deductible_met"], 2),
     "annual_maximum": v["annual_maximum"], "benefit_used": round(v["benefit_used"], 2),
     "benefit_remaining": round(max(v["annual_maximum"] - v["benefit_used"], 0.0), 2)}
    for (pid, py), v in accum.items()
])

# ----------------------------------------------------------------------------
# 9. Write CSVs
# ----------------------------------------------------------------------------
OUT_DIR.mkdir(parents=True, exist_ok=True)
tables = {
    "dental_offices": df_offices,
    "insurance_networks": df_networks,
    "insurance_companies": df_ins_companies,
    "insurance_company_networks": df_company_networks,
    "office_network_participation": df_office_networks,
    "office_insurance_network": df_office_insurance,
    "insurance_policies": df_policies,
    "patients": df_patients,
    "primary_policy_holders": df_subscribers,
    "policy_dependents": df_dependents,
    "billing_codes": df_billing_codes,
    "coverage_rules": df_coverage_rules,
    "recall_reminders": df_recalls,
    "appointments": df_appointments,
    "appointment_reminders": df_appt_reminders,
    "patient_benefit_years": df_benefit_years,
    "invoices": df_invoices,
    "invoice_lines": df_invoice_lines,
    "claims_and_payments": df_claims,
    "claim_disputes": df_disputes,
}
for name, df in tables.items():
    df.to_csv(OUT_DIR / f"{name}.csv", index=False)
    print(f"  {name:32} {len(df):>7,} rows")

print(f"\nWrote {len(tables)} CSV files to {OUT_DIR}")
