# Databricks notebook source
# DBTITLE 1,Option 2: PySpark Schema Inference
# MAGIC %md
# MAGIC # Option 2: PySpark Schema Inference
# MAGIC
# MAGIC Create bronze tables from the 20 dental billing CSV files using the PySpark DataFrame API with schema inference.
# MAGIC
# MAGIC ## What This Notebook Does:
# MAGIC 1. Sets the catalog and schema configuration
# MAGIC 2. Reads CSV files with `spark.read.csv(inferSchema=True)`
# MAGIC 3. Writes them as Delta tables in the Bronze schema
# MAGIC
# MAGIC ## When to Use:
# MAGIC - Data exploration and transformations before saving
# MAGIC - You need fine-grained control over schema
# MAGIC - You want to inspect the DataFrame before writing

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

print(f"Will create {len(csv_to_table_mapping)} tables:")
for table_name in csv_to_table_mapping.keys():
    print(f"  - {BRONZE_SCHEMA}.{table_name}")

# COMMAND ----------

# DBTITLE 1,Explore Sample Table Schema
# Explore a sample table before creating all tables
df = spark.read.csv(
    f"{VOLUME_PATH}/patients.csv",
    header=True,
    inferSchema=True
)

print(f"Schema for patients:")
df.printSchema()
print(f"\nRow count: {df.count():,}")
print("\nFirst 5 rows:")
display(df.limit(5))

# COMMAND ----------

# DBTITLE 1,Create All Bronze Tables
# Create all bronze tables using PySpark with schema inference
print(f"\nCreating tables in {BRONZE_SCHEMA}:\n")

created_tables = []
failed_tables = []

for table_name, csv_file in csv_to_table_mapping.items():
    try:
        file_path = f"{VOLUME_PATH}/{csv_file}"
        full_table_name = f"{BRONZE_SCHEMA}.{table_name}"
        
        print(f"Processing: {csv_file} -> {full_table_name}")
        
        df = spark.read.csv(file_path, header=True, inferSchema=True)
        row_count = df.count()
        df.write.mode("overwrite").saveAsTable(full_table_name)
        
        print(f"  Created table with {row_count:,} rows\n")
        created_tables.append(table_name)
        
    except Exception as e:
        print(f"  Failed: {str(e)}\n")
        failed_tables.append((table_name, str(e)))

print("="*60)
print(f"Summary: {len(created_tables)} succeeded, {len(failed_tables)} failed")
print("="*60)