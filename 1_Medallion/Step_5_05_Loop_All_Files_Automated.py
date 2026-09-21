# Databricks notebook source
# DBTITLE 1,Option 5: Loop All Files - Automated Table Creation
# MAGIC %md
# MAGIC # Option 5: Loop All Files - Automated Table Creation
# MAGIC
# MAGIC This notebook demonstrates how to create all 20 bronze tables automatically by looping through CSV files from the dental billing data model.
# MAGIC
# MAGIC ## Benefits:
# MAGIC - ✓ Create all tables at once
# MAGIC - ✓ Consistent naming and structure
# MAGIC - ✓ Minimal code duplication
# MAGIC - ✓ Easy to maintain and extend
# MAGIC
# MAGIC ## What This Notebook Does:
# MAGIC 1. Maps CSV filenames to table names
# MAGIC 2. Loops through all files
# MAGIC 3. Reads each CSV with schema inference
# MAGIC 4. Saves as Delta tables in the Bronze schema

# COMMAND ----------

# DBTITLE 1,Configuration - Update These Values
# CONFIGURATION - Update these values to match your setup

# Your catalog and schema names
CATALOG_NAME = "wavepoint_workshop"  # Update to your catalog
PROJECT_NAME = "project_3"          # Update to your project name

# Derived schema and volume paths
BRONZE_SCHEMA = f"{CATALOG_NAME}.{PROJECT_NAME}_bronze"
VOLUME_PATH = f"/Volumes/{CATALOG_NAME}/{PROJECT_NAME}_bronze/raw_data/data"

print(f"Bronze Schema: {BRONZE_SCHEMA}")
print(f"Volume Path: {VOLUME_PATH}")

# COMMAND ----------

# DBTITLE 1,Define CSV to Table Mapping
# Map CSV filenames to table names (all files use underscores, so table name = filename without .csv)
csv_to_table_mapping = {
    # Reference and structure
    "dental_offices": "dental_offices.csv",
    "insurance_networks": "insurance_networks.csv",
    "insurance_companies": "insurance_companies.csv",
    "insurance_company_networks": "insurance_company_networks.csv",
    "office_network_participation": "office_network_participation.csv",
    "office_insurance_network": "office_insurance_network.csv",
    "insurance_policies": "insurance_policies.csv",
    "billing_codes": "billing_codes.csv",
    "coverage_rules": "coverage_rules.csv",
    # People
    "patients": "patients.csv",
    "primary_policy_holders": "primary_policy_holders.csv",
    "policy_dependents": "policy_dependents.csv",
    "patient_benefit_years": "patient_benefit_years.csv",
    # Activity
    "recall_reminders": "recall_reminders.csv",
    "appointments": "appointments.csv",
    "appointment_reminders": "appointment_reminders.csv",
    # Money
    "invoices": "invoices.csv",
    "invoice_lines": "invoice_lines.csv",
    "claims_and_payments": "claims_and_payments.csv",
    "claim_disputes": "claim_disputes.csv"
}

print(f"Will create {len(csv_to_table_mapping)} tables:")
for table_name in csv_to_table_mapping.keys():
    print(f"  - {BRONZE_SCHEMA}.{table_name}")

# COMMAND ----------

# DBTITLE 1,Verify CSV Files Exist
# Verify all CSV files exist in the volume
print(f"\nVerifying files in {VOLUME_PATH}:\n")

missing_files = []
for table_name, csv_file in csv_to_table_mapping.items():
    file_path = f"{VOLUME_PATH}/{csv_file}"
    try:
        file_info = dbutils.fs.ls(file_path)
        print(f"✓ Found: {csv_file}")
    except:
        print(f"✗ Missing: {csv_file}")
        missing_files.append(csv_file)

if missing_files:
    raise Exception(f"Missing {len(missing_files)} file(s). Please upload them to the volume first.")
else:
    print(f"\n✓ All {len(csv_to_table_mapping)} CSV files found!")

# COMMAND ----------

# DBTITLE 1,Create All Bronze Tables
# Loop through all CSV files and create Delta tables
print(f"\nCreating tables in {BRONZE_SCHEMA}:\n")

created_tables = []
failed_tables = []

for table_name, csv_file in csv_to_table_mapping.items():
    try:
        # Full paths
        file_path = f"{VOLUME_PATH}/{csv_file}"
        full_table_name = f"{BRONZE_SCHEMA}.{table_name}"
        
        print(f"Processing: {csv_file} -> {full_table_name}")
        
        # Read CSV with schema inference
        df = spark.read.csv(
            file_path,
            header=True,
            inferSchema=True
        )
        
        # Get row count
        row_count = df.count()
        
        # Write as Delta table (overwrite if exists)
        df.write.mode("overwrite").saveAsTable(full_table_name)
        
        print(f"  ✓ Created table with {row_count:,} rows\n")
        created_tables.append(table_name)
        
    except Exception as e:
        print(f"  ✗ Failed: {str(e)}\n")
        failed_tables.append((table_name, str(e)))

# Summary
print("="*60)
print(f"Summary: {len(created_tables)} succeeded, {len(failed_tables)} failed")
print("="*60)

if created_tables:
    print(f"\n✓ Successfully created tables:")
    for table in created_tables:
        print(f"  - {BRONZE_SCHEMA}.{table}")

if failed_tables:
    print(f"\n✗ Failed tables:")
    for table, error in failed_tables:
        print(f"  - {table}: {error}")

# COMMAND ----------

# DBTITLE 1,Verify Tables in Bronze Schema
# MAGIC %sql
# MAGIC -- View all tables in the Bronze schema
# MAGIC SHOW TABLES IN wavepoint_workshop.project_3_bronze;

# COMMAND ----------

# DBTITLE 1,Sample Data from Each Table
# Preview first 3 rows from each table
for table_name in csv_to_table_mapping.keys():
    full_table_name = f"{BRONZE_SCHEMA}.{table_name}"
    print(f"\n{'='*60}")
    print(f"Table: {full_table_name}")
    print(f"{'='*60}")
    
    try:
        df = spark.table(full_table_name)
        row_count = df.count()
        col_count = len(df.columns)
        
        print(f"Rows: {row_count:,} | Columns: {col_count}")
        print(f"\nFirst 3 rows:")
        display(df.limit(3))
    except Exception as e:
        print(f"Error reading table: {e}")