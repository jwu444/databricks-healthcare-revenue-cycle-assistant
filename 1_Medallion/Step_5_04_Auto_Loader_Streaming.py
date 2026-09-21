# Databricks notebook source
# DBTITLE 1,Option 4: Auto Loader Streaming
# MAGIC %md
# MAGIC # Option 4: Auto Loader Streaming
# MAGIC
# MAGIC Create bronze tables from the 20 dental billing CSV files using Auto Loader for streaming/batch ingestion.
# MAGIC
# MAGIC ## What This Notebook Does:
# MAGIC 1. Sets the catalog and schema configuration
# MAGIC 2. Uses `cloudFiles` Auto Loader to ingest CSV files from a volume directory
# MAGIC 3. Writes to Delta tables in the Bronze schema
# MAGIC
# MAGIC ## When to Use:
# MAGIC - Production pipelines with new files arriving over time
# MAGIC - You want schema inference and evolution handling
# MAGIC - Streaming or batch ingestion from a directory

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

# DBTITLE 1,Define CSV to Table Mapping
# Map table names to CSV filenames
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

print(f"Will create {len(csv_to_table_mapping)} tables with Auto Loader")

# COMMAND ----------

# DBTITLE 1,Create All Bronze Tables with Auto Loader
# Create all bronze tables using Auto Loader
# Auto Loader uses cloudFiles format to incrementally load files from a directory
print(f"\nCreating tables in {BRONZE_SCHEMA} with Auto Loader:\n")

created_tables = []
failed_tables = []

for table_name, csv_file in csv_to_table_mapping.items():
    try:
        full_table_name = f"{BRONZE_SCHEMA}.{table_name}"
        file_path = f"{VOLUME_PATH}/{csv_file}"
        
        print(f"Processing: {csv_file} -> {full_table_name}")
        
        # Use Auto Loader (cloudFiles) to read the CSV file
        df = (spark.readStream
              .format("cloudFiles")
              .option("cloudFiles.format", "csv")
              .option("cloudFiles.schemaLocation", f"{VOLUME_PATH}/_schemas/{table_name}")
              .option("header", "true")
              .option("inferSchema", "true")
              .load(VOLUME_PATH)
              .filter(input_file_name().endswith(csv_file)))
        
        # Write to Delta table
        (df.writeStream
         .format("delta")
         .outputMode("append")
         .option("checkpointLocation", f"{VOLUME_PATH}/_checkpoints/{table_name}")
         .toTable(full_table_name))
        
        print(f"  Started stream for {table_name}\n")
        created_tables.append(table_name)
        
    except Exception as e:
        print(f"  Failed: {str(e)}\n")
        failed_tables.append((table_name, str(e)))

print("="*60)
print(f"Summary: {len(created_tables)} streams started, {len(failed_tables)} failed")
print("="*60)

# COMMAND ----------

# DBTITLE 1,Verify Tables in Bronze Schema
# MAGIC %sql
# MAGIC -- Verify the created tables
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