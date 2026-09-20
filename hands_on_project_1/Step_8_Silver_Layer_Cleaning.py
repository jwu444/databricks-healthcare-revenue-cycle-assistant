# Databricks notebook source
# DBTITLE 1,Silver Layer: Cleaning & Enrichment
# MAGIC %md
# MAGIC # Silver Layer: Clean and Enrich Bronze Data
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC This notebook transforms all 20 bronze tables into silver tables by applying **data cleaning**, **standardization**, and **enrichment** rules.
# MAGIC
# MAGIC ### Transformations Applied
# MAGIC
# MAGIC | Category | What We Do |
# MAGIC |----------|------------|
# MAGIC | **Text Standardization** | Normalize all categorical text columns to lowercase (e.g., `"No-Show"` → `"no-show"`) |
# MAGIC | **Null Handling** | Replace nulls with sensible defaults (e.g., `source_recall_id` nulls → `0`, `denial_reason_code` nulls → `'N/A'`) |
# MAGIC | **Derived Columns** | Add business-relevant computed columns (e.g., `age_group`, `is_no_show`, `is_denied`, `unpaid_amount`, `is_overdue`) |
# MAGIC | **Audit Columns** | Add `_silver_loaded_at` timestamp to every table for lineage tracking |
# MAGIC
# MAGIC ### Table Groups
# MAGIC
# MAGIC 1. **Reference & Structure** (9 tables): offices, insurance, policies, billing codes, coverage rules
# MAGIC 2. **People** (4 tables): patients, policy holders, dependents, benefit years
# MAGIC 3. **Activity** (3 tables): recalls, appointments, appointment reminders
# MAGIC 4. **Money** (4 tables): invoices, invoice lines, claims, disputes
# MAGIC
# MAGIC ### Naming Convention
# MAGIC
# MAGIC - Bronze schema: `wavepoint_workshop.project_3_bronze`
# MAGIC - Silver schema: `wavepoint_workshop.project_3_silver`
# MAGIC - All silver tables use `CREATE OR REPLACE TABLE` for idempotent re-runs

# COMMAND ----------

# DBTITLE 1,Create Silver Schema
# MAGIC %sql
# MAGIC -- Create Silver schema if not already created in Step 2
# MAGIC CREATE SCHEMA IF NOT EXISTS wavepoint_workshop.project_3_silver
# MAGIC COMMENT 'Silver layer: Cleaned, validated, and enriched data';

# COMMAND ----------

# DBTITLE 1,Reference & Structure Tables
# MAGIC %md
# MAGIC ## 1. Reference & Structure Tables (9 tables)
# MAGIC
# MAGIC These tables are reference and configuration data. Cleaning focuses on:
# MAGIC - Standardizing text columns to lowercase
# MAGIC - Handling null values in `shared_network_id`
# MAGIC - Preserving all original data types (dates, doubles, booleans)

# COMMAND ----------

# DBTITLE 1,Create Reference Silver Tables
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- 1.1 dental_offices
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.dental_offices
# MAGIC COMMENT 'Silver: Cleaned dental office reference data'
# MAGIC AS SELECT
# MAGIC   office_id,
# MAGIC   office_name,
# MAGIC   city,
# MAGIC   UPPER(state) AS state,
# MAGIC   zip_code,
# MAGIC   LOWER(specialty_type) AS specialty_type,
# MAGIC   provider_count,
# MAGIC   opened_date,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.dental_offices;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.2 insurance_companies
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.insurance_companies
# MAGIC COMMENT 'Silver: Cleaned insurance company reference data'
# MAGIC AS SELECT
# MAGIC   insurance_company_id,
# MAGIC   company_name,
# MAGIC   LOWER(payer_type) AS payer_type,
# MAGIC   average_reimbursement_turnaround_days,
# MAGIC   denial_rate_baseline,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.insurance_companies;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.3 insurance_networks
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.insurance_networks
# MAGIC COMMENT 'Silver: Cleaned insurance network reference data'
# MAGIC AS SELECT
# MAGIC   network_id,
# MAGIC   network_name,
# MAGIC   LOWER(network_type) AS network_type,
# MAGIC   LOWER(region) AS region,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.insurance_networks;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.4 insurance_company_networks
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.insurance_company_networks
# MAGIC COMMENT 'Silver: Cleaned insurance company-network mappings'
# MAGIC AS SELECT
# MAGIC   company_network_id,
# MAGIC   insurance_company_id,
# MAGIC   network_id,
# MAGIC   participation_start_date,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.insurance_company_networks;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.5 office_network_participation
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.office_network_participation
# MAGIC COMMENT 'Silver: Cleaned office-network participation'
# MAGIC AS SELECT
# MAGIC   office_network_id,
# MAGIC   office_id,
# MAGIC   network_id,
# MAGIC   contract_start_date,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.office_network_participation;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.6 office_insurance_network
# MAGIC -- Null fix: shared_network_id has 25 nulls -> COALESCE to 0
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.office_insurance_network
# MAGIC COMMENT 'Silver: Cleaned office-insurance associations'
# MAGIC AS SELECT
# MAGIC   association_id,
# MAGIC   office_id,
# MAGIC   insurance_company_id,
# MAGIC   COALESCE(shared_network_id, 0) AS shared_network_id,
# MAGIC   LOWER(network_status) AS network_status,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.office_insurance_network;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.7 insurance_policies
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.insurance_policies
# MAGIC COMMENT 'Silver: Cleaned insurance policy reference data'
# MAGIC AS SELECT
# MAGIC   policy_id,
# MAGIC   insurance_company_id,
# MAGIC   policy_group_number,
# MAGIC   group_name,
# MAGIC   individual_deductible_per_year,
# MAGIC   family_deductible_per_year,
# MAGIC   annual_maximum_benefit,
# MAGIC   waiting_period_months_major,
# MAGIC   effective_date,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.insurance_policies;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.8 billing_codes
# MAGIC -- procedure_category already lowercase, keep as-is
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.billing_codes
# MAGIC COMMENT 'Silver: Cleaned billing code reference data'
# MAGIC AS SELECT
# MAGIC   billing_code_id,
# MAGIC   ada_procedure_code,
# MAGIC   description,
# MAGIC   LOWER(procedure_category) AS procedure_category,
# MAGIC   standard_fee,
# MAGIC   in_network_allowed_amount,
# MAGIC   out_network_allowed_amount,
# MAGIC   requires_prior_auth,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.billing_codes;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 1.9 coverage_rules
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.coverage_rules
# MAGIC COMMENT 'Silver: Cleaned coverage rules'
# MAGIC AS SELECT
# MAGIC   rule_id,
# MAGIC   policy_id,
# MAGIC   billing_code_id,
# MAGIC   copay_flat_amount,
# MAGIC   coinsurance_percentage,
# MAGIC   deductible_applies,
# MAGIC   frequency_limit_per_year,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.coverage_rules;

# COMMAND ----------

# DBTITLE 1,People Tables
# MAGIC %md
# MAGIC ## 2. People Tables (4 tables)
# MAGIC
# MAGIC These tables contain patient and policy holder information. Enrichment includes:
# MAGIC - **patients**: Add `age_group` (child/young_adult/adult/middle_aged/senior), expand gender codes to full words
# MAGIC - **primary_policy_holders**: Standardize employment_status and coverage_tier to lowercase
# MAGIC - **policy_dependents**: Standardize relationship_to_subscriber to lowercase
# MAGIC - **patient_benefit_years**: Add `deductible_met_pct`, `benefit_used_pct`, `is_benefit_exhausted` derived columns

# COMMAND ----------

# DBTITLE 1,Create People Silver Tables
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- 2.1 patients
# MAGIC -- Enrichment: age_group, gender expansion, state UPPER
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.patients
# MAGIC COMMENT 'Silver: Cleaned and enriched patient data'
# MAGIC AS SELECT
# MAGIC   patient_id,
# MAGIC   first_name,
# MAGIC   last_name,
# MAGIC   age,
# MAGIC   CASE
# MAGIC     WHEN age < 18 THEN 'child'
# MAGIC     WHEN age BETWEEN 18 AND 30 THEN 'young_adult'
# MAGIC     WHEN age BETWEEN 31 AND 50 THEN 'adult'
# MAGIC     WHEN age BETWEEN 51 AND 65 THEN 'middle_aged'
# MAGIC     ELSE 'senior'
# MAGIC   END AS age_group,
# MAGIC   CASE
# MAGIC     WHEN gender = 'M' THEN 'male'
# MAGIC     WHEN gender = 'F' THEN 'female'
# MAGIC     WHEN gender = 'O' THEN 'other'
# MAGIC     ELSE LOWER(gender)
# MAGIC   END AS gender,
# MAGIC   zip_code,
# MAGIC   UPPER(state) AS state,
# MAGIC   enrollment_date,
# MAGIC   LOWER(patient_role) AS patient_role,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.patients;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 2.2 primary_policy_holders
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.primary_policy_holders
# MAGIC COMMENT 'Silver: Cleaned primary policy holder data'
# MAGIC AS SELECT
# MAGIC   subscriber_id,
# MAGIC   policy_id,
# MAGIC   patient_id,
# MAGIC   LOWER(employment_status) AS employment_status,
# MAGIC   LOWER(coverage_tier) AS coverage_tier,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.primary_policy_holders;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 2.3 policy_dependents
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.policy_dependents
# MAGIC COMMENT 'Silver: Cleaned policy dependent data'
# MAGIC AS SELECT
# MAGIC   dependent_id,
# MAGIC   subscriber_id,
# MAGIC   patient_id,
# MAGIC   LOWER(relationship_to_subscriber) AS relationship_to_subscriber,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.policy_dependents;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 2.4 patient_benefit_years
# MAGIC -- Enrichment: deductible_met_pct, benefit_used_pct, is_benefit_exhausted
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.patient_benefit_years
# MAGIC COMMENT 'Silver: Enriched patient benefit year data with derived metrics'
# MAGIC AS SELECT
# MAGIC   patient_id,
# MAGIC   benefit_year,
# MAGIC   policy_id,
# MAGIC   individual_deductible,
# MAGIC   deductible_met,
# MAGIC   annual_maximum,
# MAGIC   benefit_used,
# MAGIC   benefit_remaining,
# MAGIC   CASE
# MAGIC     WHEN individual_deductible > 0 THEN ROUND(deductible_met / individual_deductible * 100, 2)
# MAGIC     ELSE 0
# MAGIC   END AS deductible_met_pct,
# MAGIC   CASE
# MAGIC     WHEN annual_maximum > 0 THEN ROUND(benefit_used / annual_maximum * 100, 2)
# MAGIC     ELSE 0
# MAGIC   END AS benefit_used_pct,
# MAGIC   (benefit_remaining <= 0) AS is_benefit_exhausted,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.patient_benefit_years;

# COMMAND ----------

# DBTITLE 1,Activity Tables
# MAGIC %md
# MAGIC ## 3. Activity Tables (3 tables)
# MAGIC
# MAGIC These tables track patient outreach and appointments. Enrichment includes:
# MAGIC - **recall_reminders**: Standardize all categorical columns to lowercase
# MAGIC - **appointments**: Add `is_no_show`, `is_cancelled` boolean flags, `appointment_date` (date only), `day_of_week` name; fill `source_recall_id` nulls with 0
# MAGIC - **appointment_reminders**: Standardize communication_channel, delivery_status, patient_response to lowercase

# COMMAND ----------

# DBTITLE 1,Create Activity Silver Tables
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- 3.1 recall_reminders
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.recall_reminders
# MAGIC COMMENT 'Silver: Cleaned recall reminder data'
# MAGIC AS SELECT
# MAGIC   recall_id,
# MAGIC   office_id,
# MAGIC   patient_id,
# MAGIC   benefit_year,
# MAGIC   LOWER(recall_type) AS recall_type,
# MAGIC   due_date,
# MAGIC   sent_timestamp,
# MAGIC   LOWER(communication_channel) AS communication_channel,
# MAGIC   LOWER(delivery_status) AS delivery_status,
# MAGIC   LOWER(patient_response) AS patient_response,
# MAGIC   resulted_in_appointment,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.recall_reminders;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 3.2 appointments
# MAGIC -- Enrichment: is_no_show, is_cancelled, appointment_date, day_of_week
# MAGIC -- Null fix: source_recall_id has 2458 nulls (40.7%) -> COALESCE to 0
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.appointments
# MAGIC COMMENT 'Silver: Cleaned and enriched appointment data'
# MAGIC AS SELECT
# MAGIC   appointment_id,
# MAGIC   office_id,
# MAGIC   patient_id,
# MAGIC   COALESCE(source_recall_id, 0) AS source_recall_id,
# MAGIC   LOWER(visit_type) AS visit_type,
# MAGIC   benefit_year,
# MAGIC   CAST(appointment_date_time AS DATE) AS appointment_date,
# MAGIC   DATE_FORMAT(appointment_date_time, 'EEEE') AS day_of_week,
# MAGIC   appointment_date_time,
# MAGIC   LOWER(appointment_status) AS appointment_status,
# MAGIC   (appointment_status = 'No-Show') AS is_no_show,
# MAGIC   (appointment_status = 'Cancelled') AS is_cancelled,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.appointments;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 3.3 appointment_reminders
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.appointment_reminders
# MAGIC COMMENT 'Silver: Cleaned appointment reminder data'
# MAGIC AS SELECT
# MAGIC   appointment_reminder_id,
# MAGIC   appointment_id,
# MAGIC   reminder_sequence,
# MAGIC   lead_days,
# MAGIC   LOWER(communication_channel) AS communication_channel,
# MAGIC   sent_timestamp,
# MAGIC   LOWER(delivery_status) AS delivery_status,
# MAGIC   LOWER(patient_response) AS patient_response,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.appointment_reminders;

# COMMAND ----------

# DBTITLE 1,Money Tables
# MAGIC %md
# MAGIC ## 4. Money Tables (4 tables)
# MAGIC
# MAGIC These tables contain financial transactions. Enrichment includes:
# MAGIC - **invoices**: Add `is_overdue`, `has_patient_balance`, `days_overdue` derived columns
# MAGIC - **invoice_lines**: Standardize `procedure_category` to lowercase
# MAGIC - **claims_and_payments**: Add `is_denied`, `unpaid_amount`; fill `denial_reason_code` nulls with `'N/A'` (non-denied claims) or `'UNKNOWN'` (denied claims without a code); standardize `claim_status` and `network_status` to lowercase
# MAGIC - **claim_disputes**: Standardize `dispute_reason_category` and `dispute_outcome` to lowercase

# COMMAND ----------

# DBTITLE 1,Create Money Silver Tables
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- 4.1 invoices
# MAGIC -- Enrichment: is_overdue, has_patient_balance, days_overdue
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.invoices
# MAGIC COMMENT 'Silver: Cleaned and enriched invoice data'
# MAGIC AS SELECT
# MAGIC   invoice_id,
# MAGIC   appointment_id,
# MAGIC   office_id,
# MAGIC   patient_id,
# MAGIC   policy_id,
# MAGIC   benefit_year,
# MAGIC   service_date,
# MAGIC   total_gross_amount,
# MAGIC   total_allowed_amount,
# MAGIC   total_contractual_writeoff,
# MAGIC   estimated_insurance_responsibility,
# MAGIC   estimated_copay_due,
# MAGIC   actual_patient_paid_at_visit,
# MAGIC   patient_balance,
# MAGIC   (patient_balance > 0) AS has_patient_balance,
# MAGIC   due_date,
# MAGIC   (CURRENT_DATE() > due_date AND patient_balance > 0) AS is_overdue,
# MAGIC   CASE
# MAGIC     WHEN CURRENT_DATE() > due_date AND patient_balance > 0 THEN DATEDIFF(CURRENT_DATE(), due_date)
# MAGIC     ELSE 0
# MAGIC   END AS days_overdue,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.invoices;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 4.2 invoice_lines
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.invoice_lines
# MAGIC COMMENT 'Silver: Cleaned invoice line items'
# MAGIC AS SELECT
# MAGIC   line_id,
# MAGIC   invoice_id,
# MAGIC   billing_code_id,
# MAGIC   ada_procedure_code,
# MAGIC   LOWER(procedure_category) AS procedure_category,
# MAGIC   unit_price,
# MAGIC   quantity,
# MAGIC   allowed_amount,
# MAGIC   contractual_writeoff,
# MAGIC   deductible_applied,
# MAGIC   estimated_insurance_amount,
# MAGIC   estimated_patient_amount,
# MAGIC   discount_applied,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.invoice_lines;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 4.3 claims_and_payments
# MAGIC -- Enrichment: is_denied, unpaid_amount
# MAGIC -- Null fix: denial_reason_code has 4454 nulls (85.1%) -> context-aware COALESCE
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC COMMENT 'Silver: Cleaned and enriched claims and payments data'
# MAGIC AS SELECT
# MAGIC   claim_id,
# MAGIC   invoice_id,
# MAGIC   policy_id,
# MAGIC   patient_id,
# MAGIC   office_id,
# MAGIC   insurance_company_id,
# MAGIC   LOWER(network_status) AS network_status,
# MAGIC   benefit_year,
# MAGIC   service_date,
# MAGIC   submitted_date,
# MAGIC   adjudicated_date,
# MAGIC   days_to_adjudicate,
# MAGIC   amount_claimed,
# MAGIC   amount_paid,
# MAGIC   (amount_claimed - amount_paid) AS unpaid_amount,
# MAGIC   LOWER(claim_status) AS claim_status,
# MAGIC   (claim_status = 'Denied') AS is_denied,
# MAGIC   COALESCE(denial_reason_code, CASE WHEN claim_status = 'Denied' THEN 'UNKNOWN' ELSE 'N/A' END) AS denial_reason_code,
# MAGIC   required_prior_auth,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.claims_and_payments;
# MAGIC
# MAGIC -- ============================================
# MAGIC -- 4.4 claim_disputes
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.claim_disputes
# MAGIC COMMENT 'Silver: Cleaned claim dispute data'
# MAGIC AS SELECT
# MAGIC   dispute_id,
# MAGIC   claim_id,
# MAGIC   dispute_date,
# MAGIC   LOWER(dispute_reason_category) AS dispute_reason_category,
# MAGIC   current_appeal_level,
# MAGIC   LOWER(dispute_outcome) AS dispute_outcome,
# MAGIC   resolved_date,
# MAGIC   amount_recovered,
# MAGIC   CURRENT_TIMESTAMP() AS _silver_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_bronze.claim_disputes;

# COMMAND ----------

# DBTITLE 1,Verification
# MAGIC %md
# MAGIC ## 5. Verification
# MAGIC
# MAGIC Run the queries below to verify that:
# MAGIC 1. All 20 silver tables were created
# MAGIC 2. Row counts match between bronze and silver
# MAGIC 3. Data quality fixes were applied correctly
# MAGIC 4. Enrichment columns have valid values

# COMMAND ----------

# DBTITLE 1,Verify Silver Tables
# MAGIC %sql
# MAGIC -- 5.1 List all silver tables
# MAGIC SHOW TABLES IN wavepoint_workshop.project_3_silver;

# COMMAND ----------

# DBTITLE 1,Verify Row Counts
# MAGIC %sql
# MAGIC -- 5.2 Compare row counts: bronze vs silver
# MAGIC WITH bronze_counts AS (
# MAGIC   SELECT 'bronze' AS layer, 'appointment_reminders' AS tbl, COUNT(*) AS cnt FROM wavepoint_workshop.project_3_bronze.appointment_reminders
# MAGIC   UNION ALL SELECT 'bronze', 'appointments', COUNT(*) FROM wavepoint_workshop.project_3_bronze.appointments
# MAGIC   UNION ALL SELECT 'bronze', 'billing_codes', COUNT(*) FROM wavepoint_workshop.project_3_bronze.billing_codes
# MAGIC   UNION ALL SELECT 'bronze', 'claim_disputes', COUNT(*) FROM wavepoint_workshop.project_3_bronze.claim_disputes
# MAGIC   UNION ALL SELECT 'bronze', 'claims_and_payments', COUNT(*) FROM wavepoint_workshop.project_3_bronze.claims_and_payments
# MAGIC   UNION ALL SELECT 'bronze', 'coverage_rules', COUNT(*) FROM wavepoint_workshop.project_3_bronze.coverage_rules
# MAGIC   UNION ALL SELECT 'bronze', 'dental_offices', COUNT(*) FROM wavepoint_workshop.project_3_bronze.dental_offices
# MAGIC   UNION ALL SELECT 'bronze', 'insurance_companies', COUNT(*) FROM wavepoint_workshop.project_3_bronze.insurance_companies
# MAGIC   UNION ALL SELECT 'bronze', 'insurance_company_networks', COUNT(*) FROM wavepoint_workshop.project_3_bronze.insurance_company_networks
# MAGIC   UNION ALL SELECT 'bronze', 'insurance_networks', COUNT(*) FROM wavepoint_workshop.project_3_bronze.insurance_networks
# MAGIC   UNION ALL SELECT 'bronze', 'insurance_policies', COUNT(*) FROM wavepoint_workshop.project_3_bronze.insurance_policies
# MAGIC   UNION ALL SELECT 'bronze', 'invoice_lines', COUNT(*) FROM wavepoint_workshop.project_3_bronze.invoice_lines
# MAGIC   UNION ALL SELECT 'bronze', 'invoices', COUNT(*) FROM wavepoint_workshop.project_3_bronze.invoices
# MAGIC   UNION ALL SELECT 'bronze', 'office_insurance_network', COUNT(*) FROM wavepoint_workshop.project_3_bronze.office_insurance_network
# MAGIC   UNION ALL SELECT 'bronze', 'office_network_participation', COUNT(*) FROM wavepoint_workshop.project_3_bronze.office_network_participation
# MAGIC   UNION ALL SELECT 'bronze', 'patient_benefit_years', COUNT(*) FROM wavepoint_workshop.project_3_bronze.patient_benefit_years
# MAGIC   UNION ALL SELECT 'bronze', 'patients', COUNT(*) FROM wavepoint_workshop.project_3_bronze.patients
# MAGIC   UNION ALL SELECT 'bronze', 'policy_dependents', COUNT(*) FROM wavepoint_workshop.project_3_bronze.policy_dependents
# MAGIC   UNION ALL SELECT 'bronze', 'primary_policy_holders', COUNT(*) FROM wavepoint_workshop.project_3_bronze.primary_policy_holders
# MAGIC   UNION ALL SELECT 'bronze', 'recall_reminders', COUNT(*) FROM wavepoint_workshop.project_3_bronze.recall_reminders
# MAGIC ),
# MAGIC silver_counts AS (
# MAGIC   SELECT 'silver' AS layer, 'appointment_reminders' AS tbl, COUNT(*) AS cnt FROM wavepoint_workshop.project_3_silver.appointment_reminders
# MAGIC   UNION ALL SELECT 'silver', 'appointments', COUNT(*) FROM wavepoint_workshop.project_3_silver.appointments
# MAGIC   UNION ALL SELECT 'silver', 'billing_codes', COUNT(*) FROM wavepoint_workshop.project_3_silver.billing_codes
# MAGIC   UNION ALL SELECT 'silver', 'claim_disputes', COUNT(*) FROM wavepoint_workshop.project_3_silver.claim_disputes
# MAGIC   UNION ALL SELECT 'silver', 'claims_and_payments', COUNT(*) FROM wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC   UNION ALL SELECT 'silver', 'coverage_rules', COUNT(*) FROM wavepoint_workshop.project_3_silver.coverage_rules
# MAGIC   UNION ALL SELECT 'silver', 'dental_offices', COUNT(*) FROM wavepoint_workshop.project_3_silver.dental_offices
# MAGIC   UNION ALL SELECT 'silver', 'insurance_companies', COUNT(*) FROM wavepoint_workshop.project_3_silver.insurance_companies
# MAGIC   UNION ALL SELECT 'silver', 'insurance_company_networks', COUNT(*) FROM wavepoint_workshop.project_3_silver.insurance_company_networks
# MAGIC   UNION ALL SELECT 'silver', 'insurance_networks', COUNT(*) FROM wavepoint_workshop.project_3_silver.insurance_networks
# MAGIC   UNION ALL SELECT 'silver', 'insurance_policies', COUNT(*) FROM wavepoint_workshop.project_3_silver.insurance_policies
# MAGIC   UNION ALL SELECT 'silver', 'invoice_lines', COUNT(*) FROM wavepoint_workshop.project_3_silver.invoice_lines
# MAGIC   UNION ALL SELECT 'silver', 'invoices', COUNT(*) FROM wavepoint_workshop.project_3_silver.invoices
# MAGIC   UNION ALL SELECT 'silver', 'office_insurance_network', COUNT(*) FROM wavepoint_workshop.project_3_silver.office_insurance_network
# MAGIC   UNION ALL SELECT 'silver', 'office_network_participation', COUNT(*) FROM wavepoint_workshop.project_3_silver.office_network_participation
# MAGIC   UNION ALL SELECT 'silver', 'patient_benefit_years', COUNT(*) FROM wavepoint_workshop.project_3_silver.patient_benefit_years
# MAGIC   UNION ALL SELECT 'silver', 'patients', COUNT(*) FROM wavepoint_workshop.project_3_silver.patients
# MAGIC   UNION ALL SELECT 'silver', 'policy_dependents', COUNT(*) FROM wavepoint_workshop.project_3_silver.policy_dependents
# MAGIC   UNION ALL SELECT 'silver', 'primary_policy_holders', COUNT(*) FROM wavepoint_workshop.project_3_silver.primary_policy_holders
# MAGIC   UNION ALL SELECT 'silver', 'recall_reminders', COUNT(*) FROM wavepoint_workshop.project_3_silver.recall_reminders
# MAGIC )
# MAGIC SELECT
# MAGIC   b.tbl AS table_name,
# MAGIC   b.cnt AS bronze_rows,
# MAGIC   s.cnt AS silver_rows,
# MAGIC   (b.cnt = s.cnt) AS match
# MAGIC FROM bronze_counts b
# MAGIC JOIN silver_counts s ON b.tbl = s.tbl
# MAGIC ORDER BY b.tbl;

# COMMAND ----------

# DBTITLE 1,Verify Data Quality Fixes
# MAGIC %sql
# MAGIC -- 5.3 Verify data quality fixes
# MAGIC
# MAGIC -- Check appointment_status is now lowercase
# MAGIC SELECT 'appointment_status' AS column_checked, appointment_status, COUNT(*) AS cnt
# MAGIC FROM wavepoint_workshop.project_3_silver.appointments
# MAGIC GROUP BY appointment_status
# MAGIC ORDER BY cnt DESC;
# MAGIC
# MAGIC -- Check is_no_show flag
# MAGIC SELECT 'is_no_show' AS column_checked, is_no_show, COUNT(*) AS cnt
# MAGIC FROM wavepoint_workshop.project_3_silver.appointments
# MAGIC GROUP BY is_no_show
# MAGIC ORDER BY cnt DESC;
# MAGIC
# MAGIC -- Check age_group distribution
# MAGIC SELECT 'age_group' AS column_checked, age_group, COUNT(*) AS cnt
# MAGIC FROM wavepoint_workshop.project_3_silver.patients
# MAGIC GROUP BY age_group
# MAGIC ORDER BY age_group;
# MAGIC
# MAGIC -- Check denial_reason_code no longer has nulls
# MAGIC SELECT 'denial_reason_code' AS column_checked, denial_reason_code, COUNT(*) AS cnt
# MAGIC FROM wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC GROUP BY denial_reason_code
# MAGIC ORDER BY cnt DESC;
# MAGIC
# MAGIC -- Check unpaid_amount calculation
# MAGIC SELECT 'unpaid_amount' AS column_checked,
# MAGIC   claim_status,
# MAGIC   COUNT(*) AS cnt,
# MAGIC   ROUND(AVG(unpaid_amount), 2) AS avg_unpaid
# MAGIC FROM wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC GROUP BY claim_status
# MAGIC ORDER BY cnt DESC;
# MAGIC
# MAGIC -- Check is_overdue flag on invoices
# MAGIC SELECT 'is_overdue' AS column_checked, is_overdue, COUNT(*) AS cnt
# MAGIC FROM wavepoint_workshop.project_3_silver.invoices
# MAGIC GROUP BY is_overdue
# MAGIC ORDER BY cnt DESC;
# MAGIC
# MAGIC -- Check benefit utilization in patient_benefit_years
# MAGIC SELECT 'benefit_used_pct' AS column_checked,
# MAGIC   CASE
# MAGIC     WHEN benefit_used_pct < 25 THEN '0-25%'
# MAGIC     WHEN benefit_used_pct < 50 THEN '25-50%'
# MAGIC     WHEN benefit_used_pct < 75 THEN '50-75%'
# MAGIC     WHEN benefit_used_pct < 100 THEN '75-100%'
# MAGIC     ELSE '100%+'
# MAGIC   END AS utilization_bucket,
# MAGIC   COUNT(*) AS cnt
# MAGIC FROM wavepoint_workshop.project_3_silver.patient_benefit_years
# MAGIC GROUP BY utilization_bucket
# MAGIC ORDER BY utilization_bucket;