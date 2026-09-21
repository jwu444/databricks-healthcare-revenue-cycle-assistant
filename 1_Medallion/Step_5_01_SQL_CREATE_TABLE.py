# Databricks notebook source
# DBTITLE 1,Option 1: SQL CREATE TABLE
# MAGIC %md
# MAGIC # Option 1: SQL CREATE TABLE
# MAGIC
# MAGIC Create bronze tables from the 20 dental billing CSV files using SQL `CREATE TABLE ... AS SELECT` with `read_files`.
# MAGIC
# MAGIC ## What This Notebook Does:
# MAGIC 1. Sets the catalog and schema configuration
# MAGIC 2. Creates representative tables using SQL CTAS with `read_files`
# MAGIC 3. Verifies the tables
# MAGIC
# MAGIC ## When to Use:
# MAGIC - Quick one-time loads
# MAGIC - You know the exact file paths
# MAGIC - You want SQL-only syntax (no PySpark)

# COMMAND ----------

# DBTITLE 1,Configuration - Update These Values
# CONFIGURATION - Update these values to match your setup
CATALOG_NAME = "wavepoint_workshop"  # Update to your catalog
PROJECT_NAME = "project_3"          # Update to your project name

BRONZE_SCHEMA = f"{CATALOG_NAME}.{PROJECT_NAME}_bronze"
VOLUME_PATH = f"/Volumes/{CATALOG_NAME}/{PROJECT_NAME}_bronze/raw_data/data"

print(f"Bronze Schema: {BRONZE_SCHEMA}")
print(f"Volume Path: {VOLUME_PATH}")

# COMMAND ----------

# DBTITLE 1,Create Representative Tables with SQL CTAS
# MAGIC %sql
# MAGIC -- Create representative tables using CTAS with read_files
# MAGIC -- This creates a few tables; use notebook 05 to create all 20 at once
# MAGIC
# MAGIC -- Patients table (796 rows)
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.patients
# MAGIC USING delta
# MAGIC AS SELECT * FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/patients.csv',
# MAGIC   format => 'csv',
# MAGIC   header => true,
# MAGIC   inferSchema => true
# MAGIC );
# MAGIC
# MAGIC -- Dental offices table (20 rows)
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.dental_offices
# MAGIC USING delta
# MAGIC AS SELECT * FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/dental_offices.csv',
# MAGIC   format => 'csv',
# MAGIC   header => true,
# MAGIC   inferSchema => true
# MAGIC );
# MAGIC
# MAGIC -- Insurance companies table (9 rows)
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.insurance_companies
# MAGIC USING delta
# MAGIC AS SELECT * FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/insurance_companies.csv',
# MAGIC   format => 'csv',
# MAGIC   header => true,
# MAGIC   inferSchema => true
# MAGIC );
# MAGIC
# MAGIC -- Invoices table (5,232 rows)
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.invoices
# MAGIC USING delta
# MAGIC AS SELECT * FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/invoices.csv',
# MAGIC   format => 'csv',
# MAGIC   header => true,
# MAGIC   inferSchema => true
# MAGIC );
# MAGIC
# MAGIC -- Claims and payments table (5,232 rows)
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.claims_and_payments
# MAGIC USING delta
# MAGIC AS SELECT * FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/claims_and_payments.csv',
# MAGIC   format => 'csv',
# MAGIC   header => true,
# MAGIC   inferSchema => true
# MAGIC );

# COMMAND ----------

# DBTITLE 1,Verify Tables in Bronze Schema
# MAGIC %sql
# MAGIC -- Verify the created tables
# MAGIC SHOW TABLES IN wavepoint_workshop.project_3_bronze;

# COMMAND ----------

# DBTITLE 1,Row Counts Summary
# MAGIC %sql
# MAGIC -- Preview data from each created table
# MAGIC SELECT 'patients' AS table_name, COUNT(*) AS row_count FROM wavepoint_workshop.project_3_bronze.patients
# MAGIC UNION ALL
# MAGIC SELECT 'dental_offices', COUNT(*) FROM wavepoint_workshop.project_3_bronze.dental_offices
# MAGIC UNION ALL
# MAGIC SELECT 'insurance_companies', COUNT(*) FROM wavepoint_workshop.project_3_bronze.insurance_companies
# MAGIC UNION ALL
# MAGIC SELECT 'invoices', COUNT(*) FROM wavepoint_workshop.project_3_bronze.invoices
# MAGIC UNION ALL
# MAGIC SELECT 'claims_and_payments', COUNT(*) FROM wavepoint_workshop.project_3_bronze.claims_and_payments
# MAGIC ORDER BY row_count DESC;