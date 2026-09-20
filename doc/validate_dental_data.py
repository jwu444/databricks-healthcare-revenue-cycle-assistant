"""
Consistency check: does the generated data match dental_data_model_design.md?

Verifies every structural claim the design doc makes - entities, foreign keys,
cardinalities, money identities, plan design - plus the quoted row counts and
statistics. Run it after any change to generate_dental_data.py; if the doc and
the data disagree, one of them is wrong.

Usage:  python3 validate_dental_data.py     (exit 0 = consistent, 1 = drift)
"""

import glob
import os
import sys

import pandas as pd

D = os.path.join(os.path.dirname(__file__), "data")
t = {os.path.basename(p)[:-4]: pd.read_csv(p) for p in glob.glob(f"{D}/*.csv")}
failures = []


def check(cond, label, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"   [{detail}]" if detail and not cond else ""))
    if not cond:
        failures.append(label)


def section(name):
    print(f"\n=== {name} ===")


# --- foreign keys the doc's relationship table declares --------------------
FOREIGN_KEYS = [
    ("insurance_company_networks", "insurance_company_id", "insurance_companies", "insurance_company_id"),
    ("insurance_company_networks", "network_id", "insurance_networks", "network_id"),
    ("office_network_participation", "office_id", "dental_offices", "office_id"),
    ("office_network_participation", "network_id", "insurance_networks", "network_id"),
    ("office_insurance_network", "office_id", "dental_offices", "office_id"),
    ("office_insurance_network", "insurance_company_id", "insurance_companies", "insurance_company_id"),
    ("insurance_policies", "insurance_company_id", "insurance_companies", "insurance_company_id"),
    ("coverage_rules", "policy_id", "insurance_policies", "policy_id"),
    ("coverage_rules", "billing_code_id", "billing_codes", "billing_code_id"),
    ("primary_policy_holders", "policy_id", "insurance_policies", "policy_id"),
    ("primary_policy_holders", "patient_id", "patients", "patient_id"),
    ("policy_dependents", "subscriber_id", "primary_policy_holders", "subscriber_id"),
    ("policy_dependents", "patient_id", "patients", "patient_id"),
    ("patient_benefit_years", "patient_id", "patients", "patient_id"),
    ("patient_benefit_years", "policy_id", "insurance_policies", "policy_id"),
    ("recall_reminders", "office_id", "dental_offices", "office_id"),
    ("recall_reminders", "patient_id", "patients", "patient_id"),
    ("appointments", "office_id", "dental_offices", "office_id"),
    ("appointments", "patient_id", "patients", "patient_id"),
    ("appointments", "source_recall_id", "recall_reminders", "recall_id"),
    ("appointment_reminders", "appointment_id", "appointments", "appointment_id"),
    ("invoices", "appointment_id", "appointments", "appointment_id"),
    ("invoice_lines", "invoice_id", "invoices", "invoice_id"),
    ("invoice_lines", "billing_code_id", "billing_codes", "billing_code_id"),
    ("claims_and_payments", "invoice_id", "invoices", "invoice_id"),
    ("claims_and_payments", "policy_id", "insurance_policies", "policy_id"),
    ("claim_disputes", "claim_id", "claims_and_payments", "claim_id"),
]

section("tables")
EXPECTED = {"dental_offices", "insurance_networks", "insurance_companies", "insurance_company_networks",
            "office_network_participation", "office_insurance_network", "insurance_policies", "billing_codes",
            "coverage_rules", "patients", "primary_policy_holders", "policy_dependents", "patient_benefit_years",
            "recall_reminders", "appointments", "appointment_reminders", "invoices", "invoice_lines",
            "claims_and_payments", "claim_disputes"}
check(set(t) == EXPECTED, "the 20 documented tables are exactly the CSVs present",
      f"missing {EXPECTED - set(t)}, extra {set(t) - EXPECTED}")

section("foreign keys")
for child, ccol, parent, pcol in FOREIGN_KEYS:
    resolves = (ccol in t[child].columns and pcol in t[parent].columns
                and set(t[child][ccol].dropna()).issubset(set(t[parent][pcol])))
    check(resolves, f"{child}.{ccol} -> {parent}.{pcol}")

section("cardinality")
check(t["insurance_company_networks"].groupby("insurance_company_id").size().between(1, 3).all(),
      "each insurance company participates in 1-3 networks")
check(t["office_network_participation"].groupby("office_id").size().between(1, 3).all(),
      "each office contracts with 1-3 networks")
check(len(t["office_insurance_network"]) == len(t["dental_offices"]) * len(t["insurance_companies"]),
      "office_insurance_network covers every office x company pair")
check(t["policy_dependents"].groupby("subscriber_id").size().between(1, 5).all(),
      "each policy holder has 1-5 dependents")
check(len(t["coverage_rules"]) == len(t["insurance_policies"]) * len(t["billing_codes"])
      and (t["coverage_rules"].groupby(["policy_id", "billing_code_id"]).size() == 1).all(),
      "one coverage rule per policy x billing code")
check((t["patient_benefit_years"].groupby(["patient_id", "benefit_year"]).size() == 1).all(),
      "one benefit-year row per patient per year")
check((t["recall_reminders"].groupby(["patient_id", "benefit_year"]).size() == 2).all(),
      "2 cleaning recalls per patient per benefit year")
check(t["appointment_reminders"].groupby("appointment_id").size().between(1, 3).all()
      and t["appointment_reminders"].appointment_id.nunique() == len(t["appointments"]),
      "1-3 reminders on every appointment")
other = t["appointments"][t["appointments"].source_recall_id.isna()].groupby(["patient_id", "benefit_year"]).size()
check(other.between(0, 2).all(), "0-2 non-recall services per patient per benefit year")
check(t["appointments"].source_recall_id.isna().any(),
      "source_recall_id is nullable - walk-ins and follow-ups exist")
check(t["invoice_lines"].groupby("invoice_id").size().between(1, 5).all(), "1-5 lines per invoice")
check(len(t["invoices"]) == t["invoices"].appointment_id.nunique(), "invoice is 1:1 with appointment")
check(len(t["claims_and_payments"]) == t["claims_and_payments"].invoice_id.nunique(), "claim is 1:1 with invoice")
check(set(t["invoices"].appointment_id)
      == set(t["appointments"].query("appointment_status == 'Completed'").appointment_id),
      "invoices exist for exactly the completed appointments")
check(set(t["claim_disputes"].claim_id).issubset(set(t["claims_and_payments"].query("claim_status == 'Denied'").claim_id))
      and (t["claim_disputes"].groupby("claim_id").size() <= 1).all(),
      "0-1 dispute per claim, only on denied claims")

section("money identities")
lines, codes, inv = t["invoice_lines"], t["billing_codes"].set_index("billing_code_id"), t["invoices"]
joined = lines.join(codes[["standard_fee", "in_network_allowed_amount", "out_network_allowed_amount"]],
                    on="billing_code_id")
in_net = joined[joined.contractual_writeoff > 0]
check(((in_net.standard_fee - in_net.allowed_amount - in_net.contractual_writeoff).abs() < 0.02).all(),
      "contractual_writeoff = standard_fee - allowed_amount (in-network)")
check((lines.estimated_patient_amount - (lines.allowed_amount - lines.estimated_insurance_amount)).abs().max() < 0.02,
      "estimated_patient_amount = allowed - estimated_insurance_amount")
# NB: join on invoice_id - invoices are ordered by service date, not by id
agg = lines.groupby("invoice_id").agg(gross=("unit_price", "sum"), allowed=("allowed_amount", "sum")).round(2)
j = inv.set_index("invoice_id").join(agg)
check((j.total_gross_amount - j.gross).abs().max() < 0.02, "invoice gross = sum of line unit prices")
check((j.total_allowed_amount - j.allowed).abs().max() < 0.02, "invoice allowed = sum of line allowed amounts")
check(((inv.estimated_copay_due - inv.actual_patient_paid_at_visit - inv.patient_balance).abs() < 0.02).all(),
      "patient_balance = estimated_copay_due - actual_patient_paid_at_visit")
by = t["patient_benefit_years"]
check((by.benefit_used <= by.annual_maximum + 0.01).all(), "benefit_used never exceeds the annual maximum")
check(((by.annual_maximum - by.benefit_used - by.benefit_remaining).abs() < 0.02).all(),
      "benefit_remaining = annual_maximum - benefit_used")

section("plan design")
rules = t["coverage_rules"].merge(t["billing_codes"][["billing_code_id", "procedure_category"]], on="billing_code_id")
for cat, coins, copay, ded in [("preventive", 1.0, 0.0, False), ("basic", 0.8, 20.0, True), ("major", 0.5, 50.0, True)]:
    g = rules[rules.procedure_category == cat]
    check((g.coinsurance_percentage == coins).all() and (g.copay_flat_amount == copay).all()
          and (g.deductible_applies == ded).all(),
          f"{cat}: {coins:.0%} coinsurance, ${copay:.0f} copay, deductible={'yes' if ded else 'no'}")
ratio_in = codes.in_network_allowed_amount / codes.standard_fee
ratio_out = codes.out_network_allowed_amount / codes.standard_fee
check(ratio_in.between(0.60, 0.75).all(), "in-network allowed is 60-75% of the standard fee")
check(ratio_out.between(0.85, 0.95).all(), "out-of-network allowed is 85-95% of the standard fee")

section("network status is derived, not random")
off_nets = t["office_network_participation"].groupby("office_id").network_id.apply(set).to_dict()
co_nets = t["insurance_company_networks"].groupby("insurance_company_id").network_id.apply(set).to_dict()
bad = [(r.office_id, r.insurance_company_id) for r in t["office_insurance_network"].itertuples()
       if (r.network_status == "In-Network") != bool(off_nets[r.office_id] & co_nets[r.insurance_company_id])]
check(not bad, "In-Network exactly when office and company share a network", f"{len(bad)} mismatches")
claims = t["claims_and_payments"].merge(
    t["office_insurance_network"][["office_id", "insurance_company_id", "network_status"]],
    on=["office_id", "insurance_company_id"], suffixes=("", "_ref"))
check((claims.network_status == claims.network_status_ref).all(),
      "every claim's network_status agrees with office_insurance_network")

print()
if failures:
    print(f"{len(failures)} INCONSISTENCIES between the doc and the data:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("Data is consistent with dental_data_model_design.md")
