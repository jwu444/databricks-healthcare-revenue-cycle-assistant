# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Gold Layer: Business Analytics
# MAGIC %md
# MAGIC # Gold Layer: Business Analytics and Aggregations
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC This notebook creates 8 gold tables from the silver layer, pre-computing joins and aggregations for dashboard consumption.
# MAGIC
# MAGIC ### Gold Tables
# MAGIC
# MAGIC 1. **gold_kpi_summary** — Single-row overview: total patients, appointments, claims, revenue, denial rate, no-show rate
# MAGIC 2. **gold_monthly_revenue** — Monthly financial trends: revenue, writeoffs, patient balances
# MAGIC 3. **gold_revenue_by_procedure** — Monthly revenue by procedure category (preventive/basic/major)
# MAGIC 4. **gold_patient_summary** — Per-patient: visits, spending, no-shows, claims, balances
# MAGIC 5. **gold_office_performance** — Per-office: appointments, revenue, no-show rate, denial rate
# MAGIC 6. **gold_payer_performance** — Per-insurance company: denial rate, adjudication time, total claims
# MAGIC 7. **gold_appointment_analytics** — By month and visit type: no-show rate, completion rate
# MAGIC 8. **gold_recall_effectiveness** — Recall campaign: conversion rates by channel and response
# MAGIC
# MAGIC ### Design Principles
# MAGIC
# MAGIC - Pre-compute JOINs between silver tables to avoid expensive runtime joins
# MAGIC - Aggregate at business-relevant granularity (monthly, per-patient, per-office)
# MAGIC - Use silver enrichment columns (is_no_show, is_denied, is_overdue, age_group, etc.)
# MAGIC - Add _gold_loaded_at audit timestamp to every table
# MAGIC - All tables use CREATE OR REPLACE TABLE for idempotent re-runs

# COMMAND ----------

# DBTITLE 1,Create Gold Schema
# MAGIC %sql
# MAGIC -- Create Gold schema if not already created in Step 2
# MAGIC CREATE SCHEMA IF NOT EXISTS wavepoint_workshop.project_3_gold
# MAGIC COMMENT 'Gold layer: Business-level aggregates and analytics';

# COMMAND ----------

# DBTITLE 1,KPI Summary
# MAGIC %md
# MAGIC ## 1. KPI Summary Table
# MAGIC
# MAGIC A single-row table with high-level KPIs for the dashboard overview page.

# COMMAND ----------

# DBTITLE 1,gold_kpi_summary
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_kpi_summary: Single-row overview KPIs
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_kpi_summary
# MAGIC COMMENT 'Gold: Overview KPIs for the dental billing dashboard'
# MAGIC AS SELECT
# MAGIC   (SELECT COUNT(*) FROM wavepoint_workshop.project_3_silver.patients) AS total_patients,
# MAGIC   (SELECT COUNT(*) FROM wavepoint_workshop.project_3_silver.appointments) AS total_appointments,
# MAGIC   (SELECT COUNT(*) FROM wavepoint_workshop.project_3_silver.claims_and_payments) AS total_claims,
# MAGIC   (SELECT COUNT(*) FROM wavepoint_workshop.project_3_silver.invoices) AS total_invoices,
# MAGIC   (SELECT ROUND(SUM(total_allowed_amount), 2) FROM wavepoint_workshop.project_3_silver.invoices) AS total_revenue,
# MAGIC   (SELECT ROUND(SUM(patient_balance), 2) FROM wavepoint_workshop.project_3_silver.invoices) AS total_patient_balance,
# MAGIC   (SELECT ROUND(AVG(CASE WHEN is_denied THEN 1.0 ELSE 0.0 END) * 100, 2) FROM wavepoint_workshop.project_3_silver.claims_and_payments) AS denial_rate_pct,
# MAGIC   (SELECT ROUND(AVG(CASE WHEN is_no_show THEN 1.0 ELSE 0.0 END) * 100, 2) FROM wavepoint_workshop.project_3_silver.appointments) AS no_show_rate_pct,
# MAGIC   (SELECT ROUND(AVG(CASE WHEN is_overdue THEN 1.0 ELSE 0.0 END) * 100, 2) FROM wavepoint_workshop.project_3_silver.invoices) AS overdue_rate_pct,
# MAGIC   (SELECT COUNT(*) FROM wavepoint_workshop.project_3_silver.claim_disputes) AS total_disputes,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at;

# COMMAND ----------

# DBTITLE 1,Financial Analytics
# MAGIC %md
# MAGIC ## 2. Financial Analytics Tables
# MAGIC
# MAGIC Two tables that aggregate financial data at monthly granularity.

# COMMAND ----------

# DBTITLE 1,gold_monthly_revenue
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_monthly_revenue: Monthly financial trends
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_monthly_revenue
# MAGIC COMMENT 'Gold: Monthly financial trends'
# MAGIC AS SELECT
# MAGIC   DATE_TRUNC('month', service_date) AS month,
# MAGIC   COUNT(*) AS invoice_count,
# MAGIC   ROUND(SUM(total_gross_amount), 2) AS gross_revenue,
# MAGIC   ROUND(SUM(total_allowed_amount), 2) AS net_revenue,
# MAGIC   ROUND(SUM(total_contractual_writeoff), 2) AS total_writeoffs,
# MAGIC   ROUND(SUM(estimated_insurance_responsibility), 2) AS insurance_portion,
# MAGIC   ROUND(SUM(patient_balance), 2) AS outstanding_patient_balance,
# MAGIC   SUM(CASE WHEN is_overdue THEN 1 ELSE 0 END) AS overdue_invoices,
# MAGIC   ROUND(SUM(CASE WHEN is_overdue THEN patient_balance ELSE 0 END), 2) AS overdue_balance,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_silver.invoices
# MAGIC GROUP BY DATE_TRUNC('month', service_date)
# MAGIC ORDER BY month;

# COMMAND ----------

# DBTITLE 1,gold_revenue_by_procedure
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_revenue_by_procedure: Monthly revenue by procedure category
# MAGIC -- JOINs invoice_lines + invoices to get service_date
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_revenue_by_procedure
# MAGIC COMMENT 'Gold: Monthly revenue by procedure category'
# MAGIC AS SELECT
# MAGIC   DATE_TRUNC('month', i.service_date) AS month,
# MAGIC   il.procedure_category,
# MAGIC   COUNT(*) AS line_count,
# MAGIC   SUM(il.quantity) AS total_units,
# MAGIC   ROUND(SUM(il.allowed_amount), 2) AS total_allowed,
# MAGIC   ROUND(SUM(il.contractual_writeoff), 2) AS total_writeoffs,
# MAGIC   ROUND(SUM(il.estimated_insurance_amount), 2) AS insurance_portion,
# MAGIC   ROUND(SUM(il.estimated_patient_amount), 2) AS patient_portion,
# MAGIC   ROUND(SUM(il.discount_applied), 2) AS total_discounts,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_silver.invoice_lines il
# MAGIC JOIN wavepoint_workshop.project_3_silver.invoices i ON il.invoice_id = i.invoice_id
# MAGIC GROUP BY DATE_TRUNC('month', i.service_date), il.procedure_category
# MAGIC ORDER BY month, procedure_category;

# COMMAND ----------

# DBTITLE 1,Entity Analytics
# MAGIC %md
# MAGIC ## 3. Entity Analytics Tables
# MAGIC
# MAGIC Three tables that aggregate per-entity metrics by joining multiple silver tables.
# MAGIC
# MAGIC - **gold_patient_summary**: Joins patients + appointments + invoices + claims
# MAGIC - **gold_office_performance**: Joins dental_offices + appointments + invoices + claims
# MAGIC - **gold_payer_performance**: Joins insurance_companies + claims

# COMMAND ----------

# DBTITLE 1,gold_patient_summary
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_patient_summary: Per-patient aggregated metrics
# MAGIC -- JOINs patients + appointments + invoices + claims
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_patient_summary
# MAGIC COMMENT 'Gold: Per-patient aggregated metrics'
# MAGIC AS SELECT
# MAGIC   p.patient_id,
# MAGIC   p.first_name,
# MAGIC   p.last_name,
# MAGIC   p.age,
# MAGIC   p.age_group,
# MAGIC   p.gender,
# MAGIC   p.state,
# MAGIC   COALESCE(a.total_appointments, 0) AS total_appointments,
# MAGIC   COALESCE(a.no_show_count, 0) AS no_show_count,
# MAGIC   COALESCE(a.cancelled_count, 0) AS cancelled_count,
# MAGIC   COALESCE(a.completed_visits, 0) AS completed_visits,
# MAGIC   COALESCE(a.no_show_rate_pct, 0) AS no_show_rate_pct,
# MAGIC   COALESCE(i.total_invoices, 0) AS total_invoices,
# MAGIC   COALESCE(i.total_spent, 0) AS total_spent,
# MAGIC   COALESCE(i.outstanding_balance, 0) AS outstanding_balance,
# MAGIC   COALESCE(c.total_claims, 0) AS total_claims,
# MAGIC   COALESCE(c.denied_claims, 0) AS denied_claims,
# MAGIC   COALESCE(c.denial_rate_pct, 0) AS denial_rate_pct,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_silver.patients p
# MAGIC LEFT JOIN (
# MAGIC   SELECT
# MAGIC     patient_id,
# MAGIC     COUNT(*) AS total_appointments,
# MAGIC     SUM(CASE WHEN is_no_show THEN 1 ELSE 0 END) AS no_show_count,
# MAGIC     SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS cancelled_count,
# MAGIC     SUM(CASE WHEN appointment_status = 'completed' THEN 1 ELSE 0 END) AS completed_visits,
# MAGIC     ROUND(AVG(CASE WHEN is_no_show THEN 1.0 ELSE 0.0 END) * 100, 2) AS no_show_rate_pct
# MAGIC   FROM wavepoint_workshop.project_3_silver.appointments
# MAGIC   GROUP BY patient_id
# MAGIC ) a ON p.patient_id = a.patient_id
# MAGIC LEFT JOIN (
# MAGIC   SELECT
# MAGIC     patient_id,
# MAGIC     COUNT(*) AS total_invoices,
# MAGIC     ROUND(SUM(total_allowed_amount), 2) AS total_spent,
# MAGIC     ROUND(SUM(patient_balance), 2) AS outstanding_balance
# MAGIC   FROM wavepoint_workshop.project_3_silver.invoices
# MAGIC   GROUP BY patient_id
# MAGIC ) i ON p.patient_id = i.patient_id
# MAGIC LEFT JOIN (
# MAGIC   SELECT
# MAGIC     patient_id,
# MAGIC     COUNT(*) AS total_claims,
# MAGIC     SUM(CASE WHEN is_denied THEN 1 ELSE 0 END) AS denied_claims,
# MAGIC     ROUND(AVG(CASE WHEN is_denied THEN 1.0 ELSE 0.0 END) * 100, 2) AS denial_rate_pct
# MAGIC   FROM wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC   GROUP BY patient_id
# MAGIC ) c ON p.patient_id = c.patient_id;

# COMMAND ----------

# DBTITLE 1,gold_office_performance
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_office_performance: Per-office performance metrics
# MAGIC -- JOINs dental_offices + appointments + invoices + claims
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_office_performance
# MAGIC COMMENT 'Gold: Per-office performance metrics'
# MAGIC AS SELECT
# MAGIC   o.office_id,
# MAGIC   o.office_name,
# MAGIC   o.city,
# MAGIC   o.state,
# MAGIC   o.specialty_type,
# MAGIC   o.provider_count,
# MAGIC   COALESCE(a.total_appointments, 0) AS total_appointments,
# MAGIC   COALESCE(a.no_show_count, 0) AS no_show_count,
# MAGIC   COALESCE(a.cancelled_count, 0) AS cancelled_count,
# MAGIC   COALESCE(a.no_show_rate_pct, 0) AS no_show_rate_pct,
# MAGIC   COALESCE(i.total_invoices, 0) AS total_invoices,
# MAGIC   COALESCE(i.total_revenue, 0) AS total_revenue,
# MAGIC   COALESCE(i.outstanding_patient_balance, 0) AS outstanding_patient_balance,
# MAGIC   COALESCE(c.total_claims, 0) AS total_claims,
# MAGIC   COALESCE(c.denied_claims, 0) AS denied_claims,
# MAGIC   COALESCE(c.denial_rate_pct, 0) AS denial_rate_pct,
# MAGIC   COALESCE(c.avg_days_to_adjudicate, 0) AS avg_days_to_adjudicate,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_silver.dental_offices o
# MAGIC LEFT JOIN (
# MAGIC   SELECT
# MAGIC     office_id,
# MAGIC     COUNT(*) AS total_appointments,
# MAGIC     SUM(CASE WHEN is_no_show THEN 1 ELSE 0 END) AS no_show_count,
# MAGIC     SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS cancelled_count,
# MAGIC     ROUND(AVG(CASE WHEN is_no_show THEN 1.0 ELSE 0.0 END) * 100, 2) AS no_show_rate_pct
# MAGIC   FROM wavepoint_workshop.project_3_silver.appointments
# MAGIC   GROUP BY office_id
# MAGIC ) a ON o.office_id = a.office_id
# MAGIC LEFT JOIN (
# MAGIC   SELECT
# MAGIC     office_id,
# MAGIC     COUNT(*) AS total_invoices,
# MAGIC     ROUND(SUM(total_allowed_amount), 2) AS total_revenue,
# MAGIC     ROUND(SUM(patient_balance), 2) AS outstanding_patient_balance
# MAGIC   FROM wavepoint_workshop.project_3_silver.invoices
# MAGIC   GROUP BY office_id
# MAGIC ) i ON o.office_id = i.office_id
# MAGIC LEFT JOIN (
# MAGIC   SELECT
# MAGIC     office_id,
# MAGIC     COUNT(*) AS total_claims,
# MAGIC     SUM(CASE WHEN is_denied THEN 1 ELSE 0 END) AS denied_claims,
# MAGIC     ROUND(AVG(CASE WHEN is_denied THEN 1.0 ELSE 0.0 END) * 100, 2) AS denial_rate_pct,
# MAGIC     ROUND(AVG(days_to_adjudicate), 1) AS avg_days_to_adjudicate
# MAGIC   FROM wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC   GROUP BY office_id
# MAGIC ) c ON o.office_id = c.office_id;

# COMMAND ----------

# DBTITLE 1,gold_payer_performance
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_payer_performance: Per-insurance company performance
# MAGIC -- JOINs insurance_companies + claims_and_payments
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_payer_performance
# MAGIC COMMENT 'Gold: Per-insurance company performance metrics'
# MAGIC AS SELECT
# MAGIC   ic.insurance_company_id,
# MAGIC   ic.company_name,
# MAGIC   ic.payer_type,
# MAGIC   ic.average_reimbursement_turnaround_days,
# MAGIC   ic.denial_rate_baseline,
# MAGIC   COUNT(c.claim_id) AS total_claims,
# MAGIC   SUM(CASE WHEN c.is_denied THEN 1 ELSE 0 END) AS denied_claims,
# MAGIC   ROUND(AVG(CASE WHEN c.is_denied THEN 1.0 ELSE 0.0 END) * 100, 2) AS actual_denial_rate_pct,
# MAGIC   ROUND(AVG(c.days_to_adjudicate), 1) AS avg_days_to_adjudicate,
# MAGIC   ROUND(SUM(c.amount_claimed), 2) AS total_claimed,
# MAGIC   ROUND(SUM(c.amount_paid), 2) AS total_paid,
# MAGIC   ROUND(SUM(c.unpaid_amount), 2) AS total_unpaid,
# MAGIC   SUM(CASE WHEN c.network_status = 'in-network' THEN 1 ELSE 0 END) AS in_network_claims,
# MAGIC   SUM(CASE WHEN c.network_status = 'out-of-network' THEN 1 ELSE 0 END) AS out_network_claims,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_silver.insurance_companies ic
# MAGIC LEFT JOIN wavepoint_workshop.project_3_silver.claims_and_payments c ON ic.insurance_company_id = c.insurance_company_id
# MAGIC GROUP BY ic.insurance_company_id, ic.company_name, ic.payer_type,
# MAGIC   ic.average_reimbursement_turnaround_days, ic.denial_rate_baseline;

# COMMAND ----------

# DBTITLE 1,Activity Analytics
# MAGIC %md
# MAGIC ## 4. Activity Analytics Tables
# MAGIC
# MAGIC Two tables that aggregate appointment and recall campaign data.

# COMMAND ----------

# DBTITLE 1,gold_appointment_analytics
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_appointment_analytics: By month and visit type
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_appointment_analytics
# MAGIC COMMENT 'Gold: Appointment analytics by month and visit type'
# MAGIC AS SELECT
# MAGIC   DATE_TRUNC('month', appointment_date) AS month,
# MAGIC   visit_type,
# MAGIC   COUNT(*) AS total_appointments,
# MAGIC   SUM(CASE WHEN is_no_show THEN 1 ELSE 0 END) AS no_show_count,
# MAGIC   SUM(CASE WHEN is_cancelled THEN 1 ELSE 0 END) AS cancelled_count,
# MAGIC   SUM(CASE WHEN appointment_status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
# MAGIC   ROUND(AVG(CASE WHEN is_no_show THEN 1.0 ELSE 0.0 END) * 100, 2) AS no_show_rate_pct,
# MAGIC   ROUND(AVG(CASE WHEN is_cancelled THEN 1.0 ELSE 0.0 END) * 100, 2) AS cancellation_rate_pct,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_silver.appointments
# MAGIC GROUP BY DATE_TRUNC('month', appointment_date), visit_type
# MAGIC ORDER BY month, visit_type;

# COMMAND ----------

# DBTITLE 1,gold_recall_effectiveness
# MAGIC %sql
# MAGIC -- ============================================
# MAGIC -- gold_recall_effectiveness: Recall campaign metrics
# MAGIC -- ============================================
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_gold.gold_recall_effectiveness
# MAGIC COMMENT 'Gold: Recall campaign effectiveness metrics'
# MAGIC AS SELECT
# MAGIC   recall_type,
# MAGIC   communication_channel,
# MAGIC   delivery_status,
# MAGIC   patient_response,
# MAGIC   COUNT(*) AS total_sent,
# MAGIC   SUM(CASE WHEN resulted_in_appointment THEN 1 ELSE 0 END) AS appointments_created,
# MAGIC   ROUND(AVG(CASE WHEN resulted_in_appointment THEN 1.0 ELSE 0.0 END) * 100, 2) AS conversion_rate_pct,
# MAGIC   CURRENT_TIMESTAMP() AS _gold_loaded_at
# MAGIC FROM wavepoint_workshop.project_3_silver.recall_reminders
# MAGIC GROUP BY recall_type, communication_channel, delivery_status, patient_response
# MAGIC ORDER BY total_sent DESC;

# COMMAND ----------

# DBTITLE 1,Verification
# MAGIC %md
# MAGIC ## 5. Verification
# MAGIC
# MAGIC Run the queries below to verify that all 8 gold tables were created with correct data.

# COMMAND ----------

# DBTITLE 1,Verify Gold Tables
# MAGIC %sql
# MAGIC -- 5.1 List all gold tables
# MAGIC SHOW TABLES IN wavepoint_workshop.project_3_gold;

# COMMAND ----------

# DBTITLE 1,Verify Row Counts
# MAGIC %sql
# MAGIC -- 5.2 Check row counts for all gold tables
# MAGIC SELECT 'gold_kpi_summary' AS table_name, COUNT(*) AS row_count FROM wavepoint_workshop.project_3_gold.gold_kpi_summary
# MAGIC UNION ALL SELECT 'gold_monthly_revenue', COUNT(*) FROM wavepoint_workshop.project_3_gold.gold_monthly_revenue
# MAGIC UNION ALL SELECT 'gold_revenue_by_procedure', COUNT(*) FROM wavepoint_workshop.project_3_gold.gold_revenue_by_procedure
# MAGIC UNION ALL SELECT 'gold_patient_summary', COUNT(*) FROM wavepoint_workshop.project_3_gold.gold_patient_summary
# MAGIC UNION ALL SELECT 'gold_office_performance', COUNT(*) FROM wavepoint_workshop.project_3_gold.gold_office_performance
# MAGIC UNION ALL SELECT 'gold_payer_performance', COUNT(*) FROM wavepoint_workshop.project_3_gold.gold_payer_performance
# MAGIC UNION ALL SELECT 'gold_appointment_analytics', COUNT(*) FROM wavepoint_workshop.project_3_gold.gold_appointment_analytics
# MAGIC UNION ALL SELECT 'gold_recall_effectiveness', COUNT(*) FROM wavepoint_workshop.project_3_gold.gold_recall_effectiveness
# MAGIC ORDER BY table_name;

# COMMAND ----------

# DBTITLE 1,Verify Gold Data
# MAGIC %sql
# MAGIC -- 5.3 Verify data quality
# MAGIC
# MAGIC -- KPI summary
# MAGIC SELECT * FROM wavepoint_workshop.project_3_gold.gold_kpi_summary;
# MAGIC
# MAGIC -- Monthly revenue trend
# MAGIC SELECT month, invoice_count, net_revenue, outstanding_patient_balance, overdue_invoices
# MAGIC FROM wavepoint_workshop.project_3_gold.gold_monthly_revenue
# MAGIC ORDER BY month;
# MAGIC
# MAGIC -- Top 5 offices by revenue
# MAGIC SELECT office_name, specialty_type, total_revenue, no_show_rate_pct, denial_rate_pct
# MAGIC FROM wavepoint_workshop.project_3_gold.gold_office_performance
# MAGIC ORDER BY total_revenue DESC
# MAGIC LIMIT 5;
# MAGIC
# MAGIC -- Payer performance comparison
# MAGIC SELECT company_name, payer_type, total_claims, actual_denial_rate_pct,
# MAGIC   avg_days_to_adjudicate, total_unpaid
# MAGIC FROM wavepoint_workshop.project_3_gold.gold_payer_performance
# MAGIC ORDER BY total_claims DESC;
# MAGIC
# MAGIC -- Revenue by procedure category (most recent month)
# MAGIC SELECT month, procedure_category, total_allowed, insurance_portion, patient_portion
# MAGIC FROM wavepoint_workshop.project_3_gold.gold_revenue_by_procedure
# MAGIC ORDER BY month DESC, procedure_category
# MAGIC LIMIT 12;
# MAGIC
# MAGIC -- Appointment analytics by visit type
# MAGIC SELECT visit_type, total_appointments, no_show_rate_pct, cancellation_rate_pct
# MAGIC FROM wavepoint_workshop.project_3_gold.gold_appointment_analytics
# MAGIC GROUP BY visit_type, total_appointments, no_show_rate_pct, cancellation_rate_pct
# MAGIC ORDER BY total_appointments DESC;