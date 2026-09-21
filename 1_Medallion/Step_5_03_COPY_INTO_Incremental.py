# Databricks notebook source
# DBTITLE 1,Option 3: COPY INTO Incremental Loading
# MAGIC %md
# MAGIC # Option 3: COPY INTO Incremental Loading
# MAGIC
# MAGIC Create bronze tables from the 20 dental billing CSV files using `COPY INTO` for idempotent, repeatable loads.
# MAGIC
# MAGIC ## What This Notebook Does:
# MAGIC 1. Sets the catalog and schema configuration
# MAGIC 2. Creates empty Delta tables and loads data with `COPY INTO`
# MAGIC 3. Verifies the tables
# MAGIC
# MAGIC ## When to Use:
# MAGIC - Idempotent, repeatable loads (safe to re-run without duplicates)
# MAGIC - Incremental file arrivals
# MAGIC - You want a simple SQL-based approach

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

# DBTITLE 1,Create Tables and Load with COPY INTO
# MAGIC %sql
# MAGIC -- Create empty tables and load data with COPY INTO
# MAGIC -- COPY INTO is idempotent: re-running will not duplicate data
# MAGIC
# MAGIC -- Patients table
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.patients
# MAGIC USING delta;
# MAGIC COPY INTO wavepoint_workshop.project_3_bronze.patients
# MAGIC FROM '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/patients.csv'
# MAGIC FILEFORMAT = CSV
# MAGIC FORMAT_OPTIONS ('header' = 'true', 'inferSchema' = 'true');
# MAGIC
# MAGIC -- Dental offices table
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.dental_offices
# MAGIC USING delta;
# MAGIC COPY INTO wavepoint_workshop.project_3_bronze.dental_offices
# MAGIC FROM '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/dental_offices.csv'
# MAGIC FILEFORMAT = CSV
# MAGIC FORMAT_OPTIONS ('header' = 'true', 'inferSchema' = 'true');
# MAGIC
# MAGIC -- Insurance companies table
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.insurance_companies
# MAGIC USING delta;
# MAGIC COPY INTO wavepoint_workshop.project_3_bronze.insurance_companies
# MAGIC FROM '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/insurance_companies.csv'
# MAGIC FILEFORMAT = CSV
# MAGIC FORMAT_OPTIONS ('header' = 'true', 'inferSchema' = 'true');
# MAGIC
# MAGIC -- Appointments table
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.appointments
# MAGIC USING delta;
# MAGIC COPY INTO wavepoint_workshop.project_3_bronze.appointments
# MAGIC FROM '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/appointments.csv'
# MAGIC FILEFORMAT = CSV
# MAGIC FORMAT_OPTIONS ('header' = 'true', 'inferSchema' = 'true');
# MAGIC
# MAGIC -- Invoices table
# MAGIC CREATE TABLE IF NOT EXISTS wavepoint_workshop.project_3_bronze.invoices
# MAGIC USING delta;
# MAGIC COPY INTO wavepoint_workshop.project_3_bronze.invoices
# MAGIC FROM '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/invoices.csv'
# MAGIC FILEFORMAT = CSV
# MAGIC FORMAT_OPTIONS ('header' = 'true', 'inferSchema' = 'true');

# COMMAND ----------

# DBTITLE 1,Verify Tables in Bronze Schema
# MAGIC %sql
# MAGIC -- Verify the created tables
# MAGIC SHOW TABLES IN wavepoint_workshop.project_3_bronze;

# COMMAND ----------

# DBTITLE 1,Row Counts Summary
# MAGIC %sql
# MAGIC -- Preview data from loaded tables
# MAGIC SELECT 'patients' AS table_name, COUNT(*) AS row_count FROM wavepoint_workshop.project_3_bronze.patients
# MAGIC UNION ALL
# MAGIC SELECT 'dental_offices', COUNT(*) FROM wavepoint_workshop.project_3_bronze.dental_offices
# MAGIC UNION ALL
# MAGIC SELECT 'insurance_companies', COUNT(*) FROM wavepoint_workshop.project_3_bronze.insurance_companies
# MAGIC UNION ALL
# MAGIC SELECT 'appointments', COUNT(*) FROM wavepoint_workshop.project_3_bronze.appointments
# MAGIC UNION ALL
# MAGIC SELECT 'invoices', COUNT(*) FROM wavepoint_workshop.project_3_bronze.invoices
# MAGIC ORDER BY row_count DESC;