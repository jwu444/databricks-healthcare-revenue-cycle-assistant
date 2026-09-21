# Databricks notebook source
# DBTITLE 1,Title & Overview
# MAGIC %md
# MAGIC # Project 3 · Genie — Agent over the Dental Delta Tables
# MAGIC
# MAGIC ## Overview
# MAGIC Build a **Genie agent** so a non-technical person — a dental office manager — can ask questions of the
# MAGIC project-1 tables in plain English and get a correct answer **with the SQL shown**.
# MAGIC
# MAGIC Project 1 built the tables. Project 2 indexed the *documents*. This project makes the **structured** data
# MAGIC answerable in natural language. The split matters: this agent answers *"what is our denial rate?"*; project 2's
# MAGIC index answers *"what does a denial reason code mean?"* Leaving that gap is deliberate — project 4's supervisor
# MAGIC closes it.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC - Understand why **metadata quality drives Genie accuracy more than model choice does**
# MAGIC - Write table and column comments that make a schema self-describing
# MAGIC - Inventory the **actual** categorical values, and map user vocabulary onto them
# MAGIC - Encode a domain rule (the Sep–Aug benefit year) that the data cannot express on its own
# MAGIC - Author general instructions, sample questions, and question → SQL examples
# MAGIC - Test against known traps, then fix and re-test
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC | Requirement | Detail |
# MAGIC |---|---|
# MAGIC | Project 1 complete | `project_3_silver` (24 tables) and `project_3_gold` (8 tables) populated |
# MAGIC | SQL warehouse | Genie attaches to one; serverless is fine |
# MAGIC | CLI | `databricks genie ...` (v0.292.0+) |
# MAGIC
# MAGIC ## ⚠️ Use Silver and Gold, Not Bronze
# MAGIC
# MAGIC Attach **silver** (cleaned, typed, deduplicated) and **gold** (pre-aggregated) tables only.
# MAGIC
# MAGIC Bronze is raw CSV-shaped data with no comments — Genie would inherit every quirk project 1 cleaned up, and
# MAGIC accuracy tracks metadata quality. A verified difference in this workspace: **0 of 20 bronze tables carry a
# MAGIC comment, versus 22 of 24 silver and 8 of 8 gold.** That alone decides the layer.
# MAGIC
# MAGIC ## Table of Contents
# MAGIC
# MAGIC 1. Why Metadata Beats Model Choice
# MAGIC 2. Choose the Tables
# MAGIC 3. Audit and Fix Table / Column Comments
# MAGIC 4. Inventory the Actual Categorical Values ← **the step people skip**
# MAGIC 5. The Benefit-Year Rule
# MAGIC 6. Which Amount Column Means What
# MAGIC 7. Build the Agent Config
# MAGIC 8. Create the Genie Agent
# MAGIC 9. Test the Eight Questions
# MAGIC 10. Fix Failures and Re-Test
# MAGIC 11. Test in the AI Playground
# MAGIC 12. Export, Record Findings, Commit

# COMMAND ----------

# DBTITLE 1,Step 1: Why Metadata Beats Model Choice
# MAGIC %md
# MAGIC ## Step 1: Why Metadata Beats Model Choice
# MAGIC
# MAGIC 📖 **[Set up a Genie agent](https://docs.databricks.com/aws/en/genie-agents/set-up)**
# MAGIC
# MAGIC Genie turns a question into SQL. To do that it needs to know **what the columns mean** — and a column name is
# MAGIC a terrible specification. `network_status` could be a boolean, a code, or free text. Only the metadata says.
# MAGIC
# MAGIC A better model writes better SQL *given the same understanding of the schema*. It cannot guess that a benefit
# MAGIC year starts in September, that `denial_reason_code` says `'N/A'` rather than NULL when a claim was paid, or
# MAGIC that "revenue" maps to one of four different amount columns. **Those facts exist nowhere in the data.** Supply
# MAGIC them and a mid-tier model succeeds; withhold them and the best model available produces confident, wrong SQL.
# MAGIC
# MAGIC That is the paragraph the exercise asks you to be able to write. The rest of this notebook is the evidence.
# MAGIC
# MAGIC ### Where accuracy actually comes from
# MAGIC
# MAGIC | Lever | Effect | Cost |
# MAGIC |---|---|---|
# MAGIC | Table + column comments | High — the schema explains itself | Minutes |
# MAGIC | Correct categorical values / synonyms | High — wrong filters return 0 rows *silently* | Minutes |
# MAGIC | Domain rules (benefit year) | High — silently wrong answers otherwise | One paragraph |
# MAGIC | Question → SQL examples | High for the shapes it gets wrong | ~15 min |
# MAGIC | Fewer, better-chosen tables | Moderate — noise hurts | Free |
# MAGIC | Model choice | Low, by comparison | n/a |

# COMMAND ----------

# DBTITLE 1,Step 2: Choose the Tables
# MAGIC %md
# MAGIC ## Step 2: Choose the Tables
# MAGIC
# MAGIC Attach **10 tables, not all 32.** Genie accuracy drops as you add tables it does not need — every extra table
# MAGIC is another chance to join the wrong thing. Start narrow; add only when a real question demands it.
# MAGIC
# MAGIC | Group | Tables | Answers |
# MAGIC |---|---|---|
# MAGIC | **Money** | `claims_and_payments`, `invoices`, `invoice_lines`, `claim_disputes` | Denials, A/R, write-offs, appeals |
# MAGIC | **Reference** | `billing_codes`, `dental_offices`, `insurance_companies` | CDT codes, offices, payers |
# MAGIC | **Context** | `patients`, `appointments`, `patient_benefit_years` | Who, when, benefit consumption |
# MAGIC
# MAGIC All ten come from **`project_3_silver`**.
# MAGIC
# MAGIC ### Should you add the gold tables?
# MAGIC
# MAGIC Not at first. `gold_payer_performance` already contains `actual_denial_rate_pct`, which looks like a shortcut —
# MAGIC but it creates a trap: Genie may answer "denial rate by payer" from gold and "denial rate by office" from
# MAGIC silver, and the two can disagree if the gold table was built with different filters. **Pick one source of
# MAGIC truth per metric.** Silver answers everything here; add a gold table only when a question is too slow or too
# MAGIC complex against silver, and then say so explicitly in the instructions.
# MAGIC
# MAGIC ### A note on metric views
# MAGIC
# MAGIC There are **no Unity Catalog metric views** in this workspace — every object in silver and gold is a managed
# MAGIC table. The project-1 dashboard's 36 "datasets" are plain SQL inside `dental_billing.lvdash.json`; they are not
# MAGIC catalog objects and **Genie cannot attach them**.
# MAGIC
# MAGIC They are still useful: that SQL is curated business logic, and it is the natural source for the
# MAGIC question → SQL examples in Step 7. If you later promote them to real UC metric views, Genie *can* attach
# MAGIC those — a genuine improvement, and out of scope here.

# COMMAND ----------

# DBTITLE 1,Check Which Tables Have Comments
# MAGIC %sql
# MAGIC -- Genie reads these. Anything without a comment is a table Genie has to guess about.
# MAGIC SELECT
# MAGIC   table_schema,
# MAGIC   table_name,
# MAGIC   CASE WHEN comment IS NULL THEN 'MISSING' ELSE 'ok' END AS table_comment,
# MAGIC   left(coalesce(comment, ''), 70)                        AS comment_preview
# MAGIC FROM wavepoint_workshop.information_schema.tables
# MAGIC WHERE table_schema = 'project_3_silver'
# MAGIC   AND table_name IN (
# MAGIC     'claims_and_payments','invoices','invoice_lines','claim_disputes',
# MAGIC     'billing_codes','dental_offices','insurance_companies',
# MAGIC     'patients','appointments','patient_benefit_years')
# MAGIC ORDER BY table_name

# COMMAND ----------

# DBTITLE 1,Step 3: Audit and Fix Comments
# MAGIC %md
# MAGIC ## Step 3: Audit and Fix Table / Column Comments
# MAGIC
# MAGIC Project 1 commented most silver tables. What is usually missing is **column** comments on the columns that are
# MAGIC not self-evident. Run the audit below, then fill the gaps.
# MAGIC
# MAGIC Prioritise these — they are the ones a reader cannot infer from the name:
# MAGIC
# MAGIC `network_status` · `denial_reason_code` · `claim_status` · `days_to_adjudicate` ·
# MAGIC `total_contractual_writeoff` · `contractual_writeoff` · `deductible_met` ·
# MAGIC `benefit_used` / `benefit_remaining` · `patient_balance` · `estimated_insurance_amount` ·
# MAGIC `resulted_in_appointment` · `current_appeal_level`
# MAGIC
# MAGIC A good column comment states **the unit, the sentinel, and the gotcha** — not a restatement of the name:
# MAGIC
# MAGIC > ❌ `'The denial reason code'`
# MAGIC > ✅ `'Reason a claim was denied. Literal string N/A (not NULL) when the claim was paid. One of 7 denial values — see table comment.'`

# COMMAND ----------

# DBTITLE 1,Audit Column Comments on the 10 Tables
# MAGIC %sql
# MAGIC -- Every row returned is a column Genie will have to guess the meaning of.
# MAGIC SELECT table_name, column_name, data_type
# MAGIC FROM wavepoint_workshop.information_schema.columns
# MAGIC WHERE table_schema = 'project_3_silver'
# MAGIC   AND table_name IN (
# MAGIC     'claims_and_payments','invoices','invoice_lines','claim_disputes',
# MAGIC     'billing_codes','dental_offices','insurance_companies',
# MAGIC     'patients','appointments','patient_benefit_years')
# MAGIC   AND comment IS NULL
# MAGIC   AND column_name NOT LIKE '\_%'          -- skip _silver_loaded_at housekeeping
# MAGIC ORDER BY table_name, ordinal_position

# COMMAND ----------

# DBTITLE 1,Add the High-Value Column Comments
# MAGIC %sql
# MAGIC -- Each comment states the unit, the sentinel value, and the trap.
# MAGIC -- Extend this list with whatever the audit above returned.
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.claims_and_payments ALTER COLUMN claim_status
# MAGIC   COMMENT 'Adjudication outcome. Exactly two values: clean-paid, denied. There is no pending/submitted state, so denial rate = denied / all claims.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.claims_and_payments ALTER COLUMN denial_reason_code
# MAGIC   COMMENT 'Why a claim was denied. Literal string N/A (NOT NULL) when claim_status = clean-paid. Filter denial_reason_code <> \'N/A\', never IS NOT NULL.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.claims_and_payments ALTER COLUMN network_status
# MAGIC   COMMENT 'Whether the office was contracted with the payer for this claim: in-network or out-of-network (lowercase, hyphenated).';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.claims_and_payments ALTER COLUMN amount_paid
# MAGIC   COMMENT 'USD the payer actually remitted. This is collections, not revenue. 0 for denied claims.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.invoices ALTER COLUMN total_gross_amount
# MAGIC   COMMENT 'USD charged at full fee schedule before any contractual adjustment. Not what you get paid.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.invoices ALTER COLUMN total_allowed_amount
# MAGIC   COMMENT 'USD the payer contract permits. total_gross_amount - total_allowed_amount = total_contractual_writeoff.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.invoices ALTER COLUMN total_contractual_writeoff
# MAGIC   COMMENT 'USD written off under contract, never collectible. This is revenue leakage, not bad debt.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.invoices ALTER COLUMN patient_balance
# MAGIC   COMMENT 'USD still owed by the patient after insurance. Drives A/R aging against due_date.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.patient_benefit_years ALTER COLUMN benefit_year
# MAGIC   COMMENT 'Benefit year label: 2023-24, 2024-25, 2025-26. Runs Sep 1 to Aug 31, NOT the calendar year.';
# MAGIC
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.patient_benefit_years ALTER COLUMN benefit_remaining
# MAGIC   COMMENT 'USD of annual_maximum still available this benefit year. Resets every Sep 1.'

# COMMAND ----------

# DBTITLE 1,Step 4: Inventory the Actual Values
# MAGIC %md
# MAGIC ## Step 4: Inventory the Actual Categorical Values
# MAGIC
# MAGIC # This is the step people skip, and it is where accuracy is won or lost.
# MAGIC
# MAGIC If Genie filters `claim_status = 'Denied'` and the column stores `'denied'`, the query returns **zero rows and
# MAGIC no error**. The user sees "0 claims were denied" and believes it. A wrong filter is worse than a crash.
# MAGIC
# MAGIC Run `SELECT DISTINCT` on every categorical column and write the results down. **Verified values in this
# MAGIC workspace** (run the next cell to confirm on your own data):
# MAGIC
# MAGIC | Column | Table | Actual values |
# MAGIC |---|---|---|
# MAGIC | `claim_status` | claims_and_payments | `clean-paid`, `denied` |
# MAGIC | `denial_reason_code` | claims_and_payments | `N/A`, `Prior Auth Required`, `Missing X-Ray`, `Max Benefit Exceeded`, `Coverage Terminated`, `Timely Filing Expired`, `Frequency Limit Exceeded`, `Coding Error` |
# MAGIC | `network_status` | claims_and_payments | `in-network`, `out-of-network` |
# MAGIC | `appointment_status` | appointments | `completed`, `no-show`, `cancelled` |
# MAGIC | `visit_type` | appointments | `restorative`, `cleaning`, `major`, `emergency` |
# MAGIC | `procedure_category` | billing_codes | `preventive`, `basic`, `major` |
# MAGIC | `payer_type` | insurance_companies | `commercial ppo`, `dhmo`, `medicaid` |
# MAGIC | `specialty_type` | dental_offices | `general dentistry`, `pediatric dentistry`, `orthodontics` |
# MAGIC | `dispute_reason_category` | claim_disputes | `administrative error`, `benefit limit`, `medical necessity` |
# MAGIC | `dispute_outcome` | claim_disputes | `overturned-paid`, `upheld-denied` |
# MAGIC | `coverage_tier` | primary_policy_holders | `employee + one`, `employee + family` |
# MAGIC | `recall_type` | recall_reminders | `cleaning` *(single value)* |
# MAGIC | `communication_channel` | recall_reminders | `email`, `sms`, `phone call` |
# MAGIC | `delivery_status` | recall_reminders | `delivered`, `bounced` |
# MAGIC | `patient_response` | recall_reminders | `scheduled`, `declined`, `no response`, `requested later date` |
# MAGIC
# MAGIC ### Four traps this inventory exposes
# MAGIC
# MAGIC 1. **Everything is lowercase.** Users type "Denied", "In-Network", "PPO". Every one of those returns nothing.
# MAGIC 2. **`denial_reason_code` uses the literal string `N/A`, not NULL.** `WHERE denial_reason_code IS NOT NULL`
# MAGIC    matches *every* row — including paid claims — and quietly inflates every denial metric.
# MAGIC 3. **`claim_status` has only two values.** No pending state, so denial rate is simply `denied / all`.
# MAGIC 4. **Compound values are hyphenated:** `clean-paid`, `overturned-paid`, `upheld-denied`, `out-of-network`.
# MAGIC    Nobody speaks that way, so every one needs a synonym.

# COMMAND ----------

# DBTITLE 1,Re-Run the Value Inventory Yourself
# MAGIC %sql
# MAGIC -- Never trust a value list you did not generate. Re-run this whenever the data reloads.
# MAGIC SELECT 'claim_status'            AS column_name, claim_status            AS value, count(*) AS n FROM wavepoint_workshop.project_3_silver.claims_and_payments GROUP BY claim_status
# MAGIC UNION ALL SELECT 'denial_reason_code',      denial_reason_code,      count(*) FROM wavepoint_workshop.project_3_silver.claims_and_payments GROUP BY denial_reason_code
# MAGIC UNION ALL SELECT 'network_status',          network_status,          count(*) FROM wavepoint_workshop.project_3_silver.claims_and_payments GROUP BY network_status
# MAGIC UNION ALL SELECT 'appointment_status',      appointment_status,      count(*) FROM wavepoint_workshop.project_3_silver.appointments        GROUP BY appointment_status
# MAGIC UNION ALL SELECT 'visit_type',              visit_type,              count(*) FROM wavepoint_workshop.project_3_silver.appointments        GROUP BY visit_type
# MAGIC UNION ALL SELECT 'procedure_category',      procedure_category,      count(*) FROM wavepoint_workshop.project_3_silver.billing_codes       GROUP BY procedure_category
# MAGIC UNION ALL SELECT 'payer_type',              payer_type,              count(*) FROM wavepoint_workshop.project_3_silver.insurance_companies GROUP BY payer_type
# MAGIC UNION ALL SELECT 'specialty_type',          specialty_type,          count(*) FROM wavepoint_workshop.project_3_silver.dental_offices      GROUP BY specialty_type
# MAGIC UNION ALL SELECT 'dispute_reason_category', dispute_reason_category, count(*) FROM wavepoint_workshop.project_3_silver.claim_disputes      GROUP BY dispute_reason_category
# MAGIC UNION ALL SELECT 'dispute_outcome',         dispute_outcome,         count(*) FROM wavepoint_workshop.project_3_silver.claim_disputes      GROUP BY dispute_outcome
# MAGIC ORDER BY column_name, value

# COMMAND ----------

# DBTITLE 1,Step 5: The Benefit-Year Rule
# MAGIC %md
# MAGIC ## Step 5: The Benefit-Year Rule
# MAGIC
# MAGIC # The single highest-value instruction in the whole config.
# MAGIC
# MAGIC **A benefit year runs September 1 → August 31.** Not January–December.
# MAGIC
# MAGIC Verified against the data — every fact table starts and ends exactly on those boundaries:
# MAGIC
# MAGIC ```
# MAGIC claims.service_date          2023-09-01  ->  2026-08-31   (5,232 rows)
# MAGIC appointments.appointment_date 2023-09-01  ->  2026-08-31   (6,044 rows)
# MAGIC invoices.service_date         2023-09-01  ->  2026-08-31   (5,232 rows)
# MAGIC ```
# MAGIC
# MAGIC Three benefit years, 796 patients each: **`2023-24`, `2024-25`, `2025-26`**.
# MAGIC
# MAGIC ### Why this cannot be inferred
# MAGIC
# MAGIC `patient_benefit_years` has **no date columns at all** — only the `benefit_year` string. There is no
# MAGIC `year_start_date` to join on. So mapping a service date to a benefit year *requires* the Sep–Aug rule to be
# MAGIC written into SQL:
# MAGIC
# MAGIC ```sql
# MAGIC concat(
# MAGIC   cast(year(service_date) - CASE WHEN month(service_date) >= 9 THEN 0 ELSE 1 END AS string),
# MAGIC   '-',
# MAGIC   right(cast(year(service_date) - CASE WHEN month(service_date) >= 9 THEN -1 ELSE 0 END AS string), 2)
# MAGIC ) AS benefit_year
# MAGIC ```
# MAGIC
# MAGIC Without that instruction Genie will silently use `year(service_date)`, and every year-over-year number will be
# MAGIC wrong in a way that looks completely plausible. **This is exactly what the Step 9 trap question tests.**

# COMMAND ----------

# DBTITLE 1,Verify the Benefit-Year Boundaries
# MAGIC %sql
# MAGIC -- Confirms Sep 1 -> Aug 31 and that the derived label matches patient_benefit_years.
# MAGIC SELECT
# MAGIC   concat(
# MAGIC     cast(year(service_date) - CASE WHEN month(service_date) >= 9 THEN 0 ELSE 1 END AS string), '-',
# MAGIC     right(cast(year(service_date) - CASE WHEN month(service_date) >= 9 THEN -1 ELSE 0 END AS string), 2)
# MAGIC   )                        AS derived_benefit_year,
# MAGIC   count(*)                 AS claims,
# MAGIC   min(service_date)        AS first_service,
# MAGIC   max(service_date)        AS last_service
# MAGIC FROM wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC GROUP BY 1
# MAGIC ORDER BY 1

# COMMAND ----------

# DBTITLE 1,Step 6: Which Amount Column Means What
# MAGIC %md
# MAGIC ## Step 6: Which Amount Column Means What
# MAGIC
# MAGIC Users say **"revenue"** and mean any of four different numbers. Genie has to be told which.
# MAGIC
# MAGIC | Column | Table | Meaning | User phrase |
# MAGIC |---|---|---|---|
# MAGIC | `total_gross_amount` | invoices | Charged at full fee schedule | "production", "billed" |
# MAGIC | `total_allowed_amount` | invoices | What the contract permits | "allowed", "contracted" |
# MAGIC | `total_contractual_writeoff` | invoices | gross − allowed, never collectible | "write-off", "leakage" |
# MAGIC | `amount_paid` | claims_and_payments | What the payer actually sent | "collections", "paid" |
# MAGIC | `patient_balance` | invoices | Still owed by the patient | "A/R", "outstanding" |
# MAGIC
# MAGIC The identity worth stating outright, because it is the one people get backwards:
# MAGIC
# MAGIC ```
# MAGIC total_gross_amount − total_allowed_amount = total_contractual_writeoff
# MAGIC ```
# MAGIC
# MAGIC Write-off is **contractual leakage**, not bad debt — it was never collectible. Line-level equivalents live in
# MAGIC `invoice_lines` as `allowed_amount` and `contractual_writeoff`.

# COMMAND ----------

# DBTITLE 1,Step 7: Build the Agent Config
# MAGIC %md
# MAGIC ## Step 7: Build the Agent Config
# MAGIC
# MAGIC Author the agent as a **local JSON file** (`genie_agent.json`) so it is version-controlled and reviewable in a
# MAGIC PR, rather than clicked together in the UI. This repo keeps it beside this notebook.
# MAGIC
# MAGIC ### Format rules that will bite you
# MAGIC
# MAGIC | Rule | Detail |
# MAGIC |---|---|
# MAGIC | Every item needs an `id` | 32-char lowercase hex, **unique across all three lists combined** |
# MAGIC | Text fields are **arrays** | `"question": ["..."]`, not `"question": "..."` |
# MAGIC | `text_instructions` takes **at most one item** | Merge all guidance into a single entry |
# MAGIC | Sort order matters | `data_sources.tables` by `identifier`; `example_question_sqls` and `text_instructions` by `id` |
# MAGIC
# MAGIC A simple scheme that satisfies all of it: prefix per list plus a counter —
# MAGIC `1…0001` for sample questions, `2…0001` for SQL examples, `3…0001` for the single text instruction.
# MAGIC
# MAGIC ### What goes in the instructions
# MAGIC
# MAGIC Everything you established in Steps 3–6:
# MAGIC
# MAGIC 1. **Persona** — who is asking, and that SQL should be shown
# MAGIC 2. **Table guide** — which table answers which kind of question
# MAGIC 3. **The benefit-year rule** — with the SQL expression from Step 5
# MAGIC 4. **Amount-column semantics** — the four meanings of "revenue"
# MAGIC 5. **Value mappings** — every synonym from Step 4 (`Denied` → `denied`, `PPO` → `commercial ppo`, …)
# MAGIC 6. **The `N/A` trap** — filter `denial_reason_code <> 'N/A'`, never `IS NOT NULL`
# MAGIC 7. **Vocabulary** — CDT code, allowed amount, contractual write-off, prior auth, A/R aging, annual maximum,
# MAGIC    in-network, denial reason code, appeal level
# MAGIC 8. **Scope limit** — this agent answers questions about *data*. Definitional questions belong to project 2's
# MAGIC    document index; say so rather than guessing

# COMMAND ----------

# DBTITLE 1,Step 8: Create the Genie Agent
# MAGIC %md
# MAGIC ## Step 8: Create the Genie Agent
# MAGIC
# MAGIC Name it **`Dental Billing Analyst`**, attached to your SQL warehouse.
# MAGIC
# MAGIC ```bash
# MAGIC # parent_path must ALREADY EXIST or create fails with "Tree node ... does not exist"
# MAGIC databricks workspace mkdirs /Workspace/Users/<you>/genie_spaces --profile DEFAULT
# MAGIC
# MAGIC databricks genie create-space --profile DEFAULT --json "{
# MAGIC   \"warehouse_id\": \"<WAREHOUSE_ID>\",
# MAGIC   \"title\": \"Dental Billing Analyst\",
# MAGIC   \"description\": \"Claims, denials, A/R and appointments for the dental practice group. Benefit years run Sep 1 to Aug 31.\",
# MAGIC   \"parent_path\": \"/Workspace/Users/<you>/genie_spaces\",
# MAGIC   \"serialized_space\": $(cat genie_agent.json | jq -c '.' | jq -Rs '.')
# MAGIC }"
# MAGIC ```
# MAGIC
# MAGIC **Keep the returned space id** — project 4 attaches this agent to a supervisor.
# MAGIC
# MAGIC Iterate with `update-space` rather than rebuilding:
# MAGIC
# MAGIC ```bash
# MAGIC databricks genie update-space <SPACE_ID> --profile DEFAULT \
# MAGIC   --json "{\"serialized_space\": $(cat genie_agent.json | jq -c '.' | jq -Rs '.')}"
# MAGIC ```

# COMMAND ----------

# DBTITLE 1,Step 9: Test the Eight Questions
# MAGIC %md
# MAGIC ## Step 9: Test the Eight Questions
# MAGIC
# MAGIC Cover every query shape, plus two traps. For each: **record the question, whether it was right, and what you
# MAGIC changed if it was not.**
# MAGIC
# MAGIC | # | Shape | Question |
# MAGIC |---|---|---|
# MAGIC | 1 | Simple aggregate | *How many claims did we submit in the 2024-25 benefit year?* |
# MAGIC | 2 | Filter | *Show me the claims denied for Max Benefit Exceeded.* |
# MAGIC | 3 | Group-by | *What's our denial rate by insurance company?* |
# MAGIC | 4 | Two-table join | *Which procedure categories have the deepest contractual write-off?* |
# MAGIC | 5 | Time series | *Show monthly completed appointments across all three benefit years.* |
# MAGIC | 6 | Ranking + date math | *Which five offices have the most outstanding patient balance more than 90 days past due?* |
# MAGIC | 7 | 🪤 **Benefit-year trap** | *How many claims did we file in 2025?* |
# MAGIC | 8 | 🪤 **Unanswerable** | *Which patients are most likely to no-show next month?* |
# MAGIC
# MAGIC ### What the two traps are really testing
# MAGIC
# MAGIC **Q7** — "2025" is ambiguous. Calendar 2025 spans parts of two benefit years. A good answer either uses the
# MAGIC benefit year *and says so*, or asks which you meant. A bad answer silently uses `year(service_date)` and
# MAGIC presents a confident number with no caveat.
# MAGIC
# MAGIC **Q8** — the data records what *happened*, not what *will happen*. There is no propensity model here. A good
# MAGIC answer declines and explains why; it may reasonably offer historical no-show rates instead. A bad answer
# MAGIC invents a ranking and presents it as prediction. **This is the same honesty test as project 2's
# MAGIC *"largest outstanding invoice"* question** — and the same split project 4's supervisor must learn to route.

# COMMAND ----------

# DBTITLE 1,Ask the Agent from the CLI
# MAGIC %md
# MAGIC Testing from the CLI keeps a record you can paste into the README, and shows the generated SQL:
# MAGIC
# MAGIC ```bash
# MAGIC SPACE=<SPACE_ID>
# MAGIC
# MAGIC # async — returns ids immediately
# MAGIC databricks genie start-conversation --no-wait $SPACE \
# MAGIC   "How many claims did we submit in the 2024-25 benefit year?" --profile DEFAULT
# MAGIC
# MAGIC # poll until COMPLETED / FAILED
# MAGIC databricks genie get-message $SPACE $CONV $MSG --profile DEFAULT | jq '{status, error}'
# MAGIC
# MAGIC # pull the SQL Genie wrote — this is what you are grading
# MAGIC databricks genie get-message $SPACE $CONV $MSG --profile DEFAULT \
# MAGIC   | jq '.attachments[] | {sql: .query.query, text: .text.content}'
# MAGIC ```
# MAGIC
# MAGIC **Read the SQL, not just the number.** A right answer from wrong SQL is luck, and it will not survive the next
# MAGIC question.

# COMMAND ----------

# DBTITLE 1,Step 10: Fix Failures and Re-Test
# MAGIC %md
# MAGIC ## Step 10: Fix Failures and Re-Test
# MAGIC
# MAGIC **Getting a wrong answer is the point of the exercise.** The write-up of what you changed is worth more than a
# MAGIC clean first run.
# MAGIC
# MAGIC | Symptom | Fix |
# MAGIC |---|---|
# MAGIC | Returns 0 rows for a real filter | Value mapping — Genie used `Denied`, data has `denied` |
# MAGIC | Denial counts too high | The `N/A` trap — it used `IS NOT NULL` |
# MAGIC | Year numbers look plausible but wrong | Benefit-year rule not applied |
# MAGIC | Joins the wrong tables | Add a question → SQL example for that shape |
# MAGIC | "Revenue" answers the wrong column | Sharpen the amount-column instruction |
# MAGIC | Confidently answers Q8 | Add an explicit scope limit: decline predictions |
# MAGIC
# MAGIC Fix in the **instructions**, not by rewriting the data. Then push with `update-space` and **re-ask every failed
# MAGIC question** to confirm it now passes.

# COMMAND ----------

# DBTITLE 1,Step 11: Test in the AI Playground
# MAGIC %md
# MAGIC ## Step 11: Test in the AI Playground
# MAGIC
# MAGIC 📖 **[AI Playground](https://docs.databricks.com/aws/en/large-language-models/ai-playground)**
# MAGIC
# MAGIC Exercise the agent from the Playground as well, so you know how it behaves **as a tool** rather than in its own
# MAGIC UI. In its own UI a person reads the SQL and sanity-checks it. As a tool, an LLM consumes the result and
# MAGIC narrates it — the SQL is no longer in front of a human.
# MAGIC
# MAGIC Ask Q7 (the benefit-year trap) in both places and compare. If the caveat about which year definition was used
# MAGIC survives in the Genie UI but disappears in the Playground narration, that is worth writing down — it is
# MAGIC exactly the failure mode project 4's supervisor has to manage.

# COMMAND ----------

# DBTITLE 1,Step 12: Export, Record Findings, Commit
# MAGIC %md
# MAGIC ## Step 12: Export, Record Findings, Commit
# MAGIC
# MAGIC ### 12.1 Export the config
# MAGIC
# MAGIC ```bash
# MAGIC databricks genie get-space <SPACE_ID> --include-serialized-space -o json --profile DEFAULT \
# MAGIC   | jq '.serialized_space | fromjson' > 3_Genie/genie_agent.json
# MAGIC ```
# MAGIC
# MAGIC `fromjson` unwraps the string blob into a real object, so the committed file is readable and diffable.
# MAGIC
# MAGIC ### 12.2 Done when
# MAGIC
# MAGIC - [ ] The agent answers **at least 7 of 8** test questions correctly
# MAGIC - [ ] The **benefit-year trap** is answered correctly, or the agent states which definition it used
# MAGIC - [ ] `genie_agent.json` exported and committed under `3_Genie/`
# MAGIC - [ ] `README.md` carries the **question → verdict → fix** table and the **value inventory**
# MAGIC - [ ] You can explain in one paragraph *why metadata quality drives Genie accuracy more than model choice*
# MAGIC - [ ] **Space id recorded** — project 4 attaches this agent to a supervisor
# MAGIC
# MAGIC ### 12.3 Commit
# MAGIC
# MAGIC ```bash
# MAGIC git add 3_Genie/
# MAGIC git commit -m "Add project 3 (3_Genie): Genie agent over dental Delta tables"
# MAGIC git push
# MAGIC ```

# COMMAND ----------

# DBTITLE 1,Next Steps & Resources
# MAGIC %md
# MAGIC ## Next Steps & Resources
# MAGIC
# MAGIC ### What you built
# MAGIC
# MAGIC ```
# MAGIC project_3_silver (10 curated tables, commented)
# MAGIC   → value inventory + benefit-year rule + amount semantics
# MAGIC   → genie_agent.json  (instructions, sample questions, SQL examples)
# MAGIC   → Genie agent "Dental Billing Analyst"
# MAGIC   → plain-English questions answered with SQL shown
# MAGIC ```
# MAGIC
# MAGIC You now have both halves of the workshop's question space: this agent answers **"what do the numbers say?"**,
# MAGIC and project 2's index answers **"what does this term mean?"** Project 4 puts a supervisor in front of both and
# MAGIC has to route each question to the right one.
# MAGIC
# MAGIC ### Ideas to push further
# MAGIC
# MAGIC | Try | Why |
# MAGIC |---|---|
# MAGIC | Promote dashboard datasets to **UC metric views** | Then Genie *can* attach them, and metric definitions stop being duplicated |
# MAGIC | Add `benchmarks` to the config | Regression-test accuracy after every instruction change |
# MAGIC | Add a gold table for one metric | Watch for the two-sources-of-truth trap from Step 2 |
# MAGIC | Remove a column comment and re-ask | The fastest way to *feel* why metadata drives accuracy |
# MAGIC
# MAGIC ### Documentation
# MAGIC
# MAGIC - 📖 [Set up a Genie agent](https://docs.databricks.com/aws/en/genie-agents/set-up)
# MAGIC - 📖 [Genie best practices](https://docs.databricks.com/aws/en/genie/best-practices)
# MAGIC - 📖 [Metric views](https://docs.databricks.com/aws/en/dashboards/metric-views)
# MAGIC - 📖 [AI Playground](https://docs.databricks.com/aws/en/large-language-models/ai-playground)
# MAGIC
# MAGIC ### Troubleshooting
# MAGIC
# MAGIC | Problem | Fix |
# MAGIC |---|---|
# MAGIC | `sample_question.id must be provided` | Every item needs a 32-char hex `id` |
# MAGIC | `Expected an array for question` | Use `["text"]`, not `"text"` |
# MAGIC | `text_instructions must contain at most one item` | Merge all guidance into one entry |
# MAGIC | `Tree node with path ... does not exist` | `databricks workspace mkdirs <parent_path>` first |
# MAGIC | Empty `serialized_space` on export | You need CAN EDIT on the agent |
# MAGIC | Answers return 0 rows | Value casing — re-run the Step 4 inventory |
# MAGIC
# MAGIC ### Questions?
# MAGIC
# MAGIC Ask **Databricks Assistant (Genie Code)** for help at any step!
