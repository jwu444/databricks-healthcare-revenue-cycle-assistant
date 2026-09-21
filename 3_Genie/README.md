# Project 3 · Genie — Agent over the Dental Delta Tables

## Overview

Build a **Genie agent** — `Dental Billing Analyst` — so a dental office manager can ask questions of the project-1 tables in plain English and get a correct answer with the SQL shown.

Project 1 built the tables. Project 2 indexed the **documents**. This project makes the **structured** data answerable in natural language. The split is deliberate: this agent answers *"what is our denial rate?"*; project 2's index answers *"what does a denial reason code mean?"* Project 4's supervisor closes the gap.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  SILVER — wavepoint_workshop.project_3_silver  (10 of 24)       │
│  Money:     claims_and_payments, invoices, invoice_lines,       │
│             claim_disputes                                      │
│  Reference: billing_codes, dental_offices, insurance_companies  │
│  Context:   patients, appointments, patient_benefit_years       │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼  metadata: table + column comments, value inventory,
    ▼            benefit-year rule, amount-column semantics
┌─────────────────────────────────────────────────────────────────┐
│  genie_agent.json  (version-controlled config)                  │
│  text_instructions · sample_questions · example_question_sqls   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼  databricks genie create-space / update-space
┌─────────────────────────────────────────────────────────────────┐
│  GENIE AGENT — "Dental Billing Analyst"                         │
│  natural language -> SQL -> answer, with the SQL shown          │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principle:** Genie accuracy is a metadata problem, not a model problem. A better model writes better SQL *given the same understanding of the schema* — it cannot guess that a benefit year starts in September, or that `denial_reason_code` stores `'N/A'` rather than NULL. Those facts exist nowhere in the data.

## Silver and Gold Only — Not Bronze

Bronze is raw CSV-shaped data. A measured difference in this workspace:

| Layer | Tables | With comments |
|---|---|---|
| `project_3_bronze` | 20 | **0** |
| `project_3_silver` | 24 | 22 |
| `project_3_gold` | 8 | 8 |

Since accuracy tracks metadata quality, the layer choice makes itself.

**Ten tables, not thirty-two.** Genie accuracy drops as you add tables it doesn't need — every extra table is another chance to join the wrong thing.

**Gold is held back on purpose.** `gold_payer_performance` already has `actual_denial_rate_pct`, which looks like a shortcut but creates two sources of truth: denial rate by payer from gold, by office from silver, and they can disagree. Pick one source per metric.

## A Note on Metric Views

**There are no Unity Catalog metric views in this workspace** — every object in silver and gold is a managed table.

The project-1 dashboard's 36 "datasets" are plain SQL inside `dental_billing.lvdash.json`. They are not catalog objects, so **Genie cannot attach them**. They remain useful as the source of curated business logic for the question → SQL examples. Promoting them to real UC metric views would make them attachable — a genuine improvement, out of scope here.

## Getting Started

Open the interactive guide: **[00_Instructions.py](./00_Instructions.py)** — a Databricks notebook with 20 cells (15 markdown, 5 SQL) that you execute inline as you read through each step.

## Project Contents

| File | Description |
|------|-------------|
| `00_Instructions.py` | Interactive step-by-step notebook guide |
| `README.md` | This overview file |
| `genie_agent.json` | Exported agent config — instructions, sample questions, SQL examples |

## Steps Covered

1. **Why Metadata Beats Model Choice** — where accuracy actually comes from
2. **Choose the Tables** — 10 silver tables, and why not gold or all 32
3. **Audit and Fix Comments** — unit, sentinel, and gotcha per column
4. **Inventory the Actual Values** — `SELECT DISTINCT` on every categorical column
5. **The Benefit-Year Rule** — Sep 1 → Aug 31, verified against the data
6. **Amount Column Semantics** — the four things users call "revenue"
7. **Build the Agent Config** — `genie_agent.json` format rules
8. **Create the Genie Agent** — `create-space`, then iterate with `update-space`
9. **Test the Eight Questions** — every query shape plus two traps
10. **Fix Failures and Re-Test** — fix instructions, not data
11. **Test in the AI Playground** — behavior as a tool vs. its own UI
12. **Export, Record Findings, Commit**

## Value Inventory

Generated with `SELECT DISTINCT` against `project_3_silver`. **Regenerate after any data reload** — never trust a value list you didn't produce yourself.

| Column | Table | Actual values |
|---|---|---|
| `claim_status` | claims_and_payments | `clean-paid`, `denied` |
| `denial_reason_code` | claims_and_payments | `N/A`, `Prior Auth Required`, `Missing X-Ray`, `Max Benefit Exceeded`, `Coverage Terminated`, `Timely Filing Expired`, `Frequency Limit Exceeded`, `Coding Error` |
| `network_status` | claims_and_payments | `in-network`, `out-of-network` |
| `appointment_status` | appointments | `completed`, `no-show`, `cancelled` |
| `visit_type` | appointments | `restorative`, `cleaning`, `major`, `emergency` |
| `procedure_category` | billing_codes | `preventive`, `basic`, `major` |
| `payer_type` | insurance_companies | `commercial ppo`, `dhmo`, `medicaid` |
| `specialty_type` | dental_offices | `general dentistry`, `pediatric dentistry`, `orthodontics` |
| `dispute_reason_category` | claim_disputes | `administrative error`, `benefit limit`, `medical necessity` |
| `dispute_outcome` | claim_disputes | `overturned-paid`, `upheld-denied` |
| `coverage_tier` | primary_policy_holders | `employee + one`, `employee + family` |
| `recall_type` | recall_reminders | `cleaning` *(single value)* |
| `communication_channel` | recall_reminders | `email`, `sms`, `phone call` |
| `delivery_status` | recall_reminders | `delivered`, `bounced` |
| `patient_response` | recall_reminders | `scheduled`, `declined`, `no response`, `requested later date` |

### Four traps this exposes

1. **Everything is lowercase.** Users type "Denied", "In-Network", "PPO" — each returns **zero rows and no error**. A wrong filter is worse than a crash, because the user believes the answer.
2. **`denial_reason_code` uses the literal string `N/A`, not NULL.** `WHERE denial_reason_code IS NOT NULL` matches *every* row including paid claims, quietly inflating every denial metric.
3. **`claim_status` has only two values** — no pending state, so denial rate is simply `denied / all`.
4. **Compound values are hyphenated:** `clean-paid`, `overturned-paid`, `upheld-denied`, `out-of-network`. Nobody speaks that way, so each needs a synonym.

## The Benefit-Year Rule

**A benefit year runs September 1 → August 31.** Not January–December. This is the single highest-value instruction in the config.

Verified — every fact table starts and ends exactly on those boundaries:

```
claims.service_date            2023-09-01  ->  2026-08-31   (5,232 rows)
appointments.appointment_date  2023-09-01  ->  2026-08-31   (6,044 rows)
invoices.service_date          2023-09-01  ->  2026-08-31   (5,232 rows)
```

Three benefit years, 796 patients each: `2023-24`, `2024-25`, `2025-26`.

**It cannot be inferred from the schema.** `patient_benefit_years` has no date columns at all — only the `benefit_year` string, with no `year_start_date` to join on. Mapping a service date to a benefit year requires the rule to be written into SQL:

```sql
concat(
  cast(year(service_date) - CASE WHEN month(service_date) >= 9 THEN 0 ELSE 1 END AS string), '-',
  right(cast(year(service_date) - CASE WHEN month(service_date) >= 9 THEN -1 ELSE 0 END AS string), 2)
) AS benefit_year
```

Without it, Genie silently uses `year(service_date)` and every year-over-year number is wrong in a way that looks entirely plausible.

## Amount Columns — the Four Meanings of "Revenue"

| Column | Table | Meaning | User phrase |
|---|---|---|---|
| `total_gross_amount` | invoices | Charged at full fee schedule | "production", "billed" |
| `total_allowed_amount` | invoices | What the contract permits | "allowed", "contracted" |
| `total_contractual_writeoff` | invoices | gross − allowed, never collectible | "write-off", "leakage" |
| `amount_paid` | claims_and_payments | What the payer actually sent | "collections", "paid" |
| `patient_balance` | invoices | Still owed by the patient | "A/R", "outstanding" |

```
total_gross_amount − total_allowed_amount = total_contractual_writeoff
```

Write-off is **contractual leakage**, not bad debt — it was never collectible.

## Test Results

Fill in as you work through Step 9. Getting a wrong answer is the point — the write-up of what you changed is worth more than a clean first run.

| # | Question | Shape | Verdict | Notes |
|---|---|---|---|---|
| 1 | How many claims did we submit in the 2024-25 benefit year? | aggregate | ✅ pass | **1,728**. Applied the Sep–Aug rule and stated the date range in the answer |
| 2 | Show me the claims denied for Max Benefit Exceeded. | filter | ✅ pass | Used `claim_status = 'denied'` — avoided the `N/A` trap |
| 3 | What's our denial rate by insurance company? | group-by | ✅ pass | 10.2%–26.1%; Gill Health highest at 26.1% (97/371) |
| 4 | Which procedure categories have the deepest contractual write-off? | join | ✅ pass | `preventive` $250,251.56 (27.5%). Correct `invoice_lines` → `billing_codes` join |
| 5 | Show monthly completed appointments across all three benefit years. | time series | ✅ pass | 36 months, Sep 2023 → Aug 2026, labelled by benefit year |
| 6 | Which five offices have the most outstanding patient balance >90 days past due? | rank + date math | ✅ pass | Lawrence Dental Care $12,764.36 (48 invoices) |
| 7 | 🪤 How many claims did we file in 2025? | benefit-year trap | ✅ pass | **Exceeded the bar** — split into 2024-25 (1,137) and 2025-26 (634), explained the overlap, then asked which was meant |
| 8 | 🪤 Which patients are most likely to no-show next month? | unanswerable | ✅ pass | Declined: *"records historical data only and does not include any predictive models"*, then offered historical no-show counts |

**8 of 8 correct on the first run**, so no fixes were required.

### Why it passed first try

Not luck — the known failure modes were pre-empted with **verified** facts rather than guesses. Before any config was written:

- `SELECT DISTINCT` was run on 15 categorical columns, so every value mapping is real
- The Sep–Aug boundary was confirmed against the data (`2023-09-01 → 2026-08-31`), not assumed
- Every join key was checked to exist in `information_schema.columns`
- All five example queries were **executed** before being taught to Genie

The `N/A`-not-NULL trap and the lowercase-value trap were both written into the instructions before Genie could fall into them.

Worth stating plainly: the exercise says *"getting a wrong answer is the point"*. A clean run means the learning landed in the **preparation** rather than the debugging. The instructive artifact here is the value inventory and the benefit-year verification above, not a list of fixes.

Genie also improved on the supplied examples unprompted, replacing `nullif`-guarded division with `try_divide`.

**Q7** is ambiguous — calendar 2025 spans two benefit years. A good answer uses the benefit year *and says so*, or asks which you meant.

**Q8** has no answer in this data, which records what happened, not what will happen. A good answer declines and may offer historical no-show rates instead. Same honesty test as project 2's *"largest outstanding invoice"*.

## Agent Details

| | |
|---|---|
| Name | `Dental Billing Analyst` |
| **Space ID** | **`01f1a99230b81b2eb2a86a65b7d1d3a9`** — project 4 attaches this agent to a supervisor |
| Warehouse | `1479880691331647` (Serverless Starter) |
| Parent path | `/Workspace/Users/<your-email>/genie_spaces` |
| Tables | 10 from `project_3_silver` |
| Config | [`genie_agent.json`](./genie_agent.json) — 1 text instruction, 6 sample questions, 5 question→SQL examples |

## Troubleshooting

| Problem | Fix |
|---|---|
| `sample_question.id must be provided` | Every item needs a 32-char hex `id`, unique across all three lists |
| `Expected an array for question` | Use `["text"]`, not `"text"` |
| `text_instructions must contain at most one item` | Merge all guidance into one entry |
| `Tree node with path ... does not exist` | `databricks workspace mkdirs <parent_path>` first |
| Empty `serialized_space` on export | You need CAN EDIT on the agent |
| Answers return 0 rows | Value casing — re-run the inventory above |
| Denial counts too high | The `N/A` trap — `IS NOT NULL` matches paid claims |

## Additional Resources

- [Set up a Genie agent](https://docs.databricks.com/aws/en/genie-agents/set-up)
- [Genie best practices](https://docs.databricks.com/aws/en/genie/best-practices)
- [Metric views](https://docs.databricks.com/aws/en/dashboards/metric-views)
- [AI Playground](https://docs.databricks.com/aws/en/large-language-models/ai-playground)
- Data dictionary: [`doc/data/README.md`](../doc/data/README.md)
- ER diagram: [`doc/dental_data_model_design.md`](../doc/dental_data_model_design.md)

## Questions?

Ask **Databricks Assistant (Genie Code)** for help at any step!
