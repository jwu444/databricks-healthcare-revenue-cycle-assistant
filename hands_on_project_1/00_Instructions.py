# Databricks notebook source
# DBTITLE 1,Title & Overview
# MAGIC %md
# MAGIC # Hands-On Project 1: Create Raw Tables, Load Data and Build Dashboard in Databricks
# MAGIC
# MAGIC ## Overview
# MAGIC This hands-on project guides you through setting up a data lakehouse following the **Medallion Architecture** and creating raw tables from CSV files in Unity Catalog.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC - Understand and implement the Medallion Architecture (Bronze, Silver, Gold layers)
# MAGIC - Create Unity Catalog schemas and volumes
# MAGIC - Load CSV data into Delta tables using multiple approaches
# MAGIC - Connect GitHub repositories to Databricks workspace
# MAGIC - Follow SQL naming best practices
# MAGIC - Build AI/BI dashboards with cross-entity charts
# MAGIC - Set up CI/CD with Declarative Automation Bundles
# MAGIC
# MAGIC ## Important: Naming Convention
# MAGIC
# MAGIC ⚠️ **Always use underscores (`_`) in catalog, schema, and table names to avoid SQL syntax confusion.**
# MAGIC
# MAGIC ✅ **Good:** `project_3_bronze`, `cdt_medicaid_allowed_amounts`
# MAGIC ❌ **Bad:** `project-3-bronze`, `cdt-medicaid-allowed-amounts`
# MAGIC
# MAGIC Hyphens (`-`) can cause SQL parsing errors and require backtick escaping.
# MAGIC
# MAGIC ## Table of Contents
# MAGIC
# MAGIC 1. Understand the Medallion Architecture
# MAGIC 2. Set Up Your Project Structure
# MAGIC 3. Copy Raw Data to Volume
# MAGIC 4. Connect Your GitHub Repository
# MAGIC 5. Create Raw Tables (Bronze Layer)
# MAGIC 6. Verify Your Setup
# MAGIC 7. Execute the Project
# MAGIC 8. Create Silver Layer (Data Cleaning & Enrichment)
# MAGIC 9. Create Gold Layer (Business Analytics & Aggregations)
# MAGIC 10. Create Dashboard
# MAGIC 11. CI/CD with Declarative Automation Bundles

# COMMAND ----------

# DBTITLE 1,Step 1: Medallion Architecture
# MAGIC %md
# MAGIC ## Step 1: Understand the Medallion Architecture
# MAGIC
# MAGIC 📖 **[Medallion Architecture Documentation](https://docs.databricks.com/aws/en/lakehouse/medallion)**
# MAGIC
# MAGIC ### Why Three Schemas?
# MAGIC
# MAGIC The Medallion Architecture organizes data into three progressive layers:
# MAGIC
# MAGIC 1. **Bronze Layer (`project_3_bronze`)**
# MAGIC    - **Purpose:** Raw data ingestion layer
# MAGIC    - **Characteristics:**
# MAGIC      - Stores data in its original format (no transformations)
# MAGIC      - Preserves data lineage and history
# MAGIC      - Acts as the "single source of truth"
# MAGIC    - **Example:** Raw CSV files loaded as-is into Delta tables
# MAGIC
# MAGIC 2. **Silver Layer (`project_3_silver`)**
# MAGIC    - **Purpose:** Cleaned and enriched data layer
# MAGIC    - **Characteristics:**
# MAGIC      - Data is validated, deduplicated, and standardized
# MAGIC      - Business logic applied (e.g., type conversions, null handling)
# MAGIC      - Optimized for downstream consumption
# MAGIC    - **Example:** Cleaned tables with proper data types and business rules
# MAGIC
# MAGIC 3. **Gold Layer (`project_3_gold`)**
# MAGIC    - **Purpose:** Business-level aggregates and analytics-ready datasets
# MAGIC    - **Characteristics:**
# MAGIC      - Aggregated metrics and KPIs
# MAGIC      - Denormalized for performance
# MAGIC      - Ready for BI dashboards and reporting
# MAGIC    - **Example:** Summary tables, aggregated metrics, dashboards
# MAGIC
# MAGIC ### Key Benefits:
# MAGIC - **Incremental complexity:** Each layer adds value without modifying upstream data
# MAGIC - **Data quality:** Progressive refinement catches issues early
# MAGIC - **Flexibility:** Different teams can work at different layers
# MAGIC - **Audit trail:** Full lineage from raw to refined data

# COMMAND ----------

# DBTITLE 1,Step 2: Set Up Project Structure
# MAGIC %md
# MAGIC ## Step 2: Set Up Your Project Structure
# MAGIC
# MAGIC ### 2.1 Create Three Schemas
# MAGIC
# MAGIC Replace `<project_name>` with your actual project name. For this workshop we use `wavepoint_workshop` as the catalog and `project_3` as the project name.
# MAGIC
# MAGIC Run the SQL cell below to create the bronze, silver, and gold schemas.
# MAGIC
# MAGIC ### 2.2 Create a Volume in the Bronze Schema
# MAGIC
# MAGIC Volumes store unstructured data (files) in Unity Catalog. Run the SQL cell below to create the `raw_data` volume.
# MAGIC
# MAGIC ### 2.3 Create Sub-Directories in the Volume
# MAGIC
# MAGIC Run the Python cell below to create `data/` and `articles/` sub-directories inside the volume.

# COMMAND ----------

# DBTITLE 1,Create Schemas
# MAGIC %sql
# MAGIC -- Create Bronze schema (raw data)
# MAGIC CREATE SCHEMA IF NOT EXISTS wavepoint_workshop.project_3_bronze
# MAGIC COMMENT 'Bronze layer: Raw data ingestion';
# MAGIC
# MAGIC -- Create Silver schema (cleaned data)
# MAGIC CREATE SCHEMA IF NOT EXISTS wavepoint_workshop.project_3_silver
# MAGIC COMMENT 'Silver layer: Cleaned and validated data';
# MAGIC
# MAGIC -- Create Gold schema (business aggregates)
# MAGIC CREATE SCHEMA IF NOT EXISTS wavepoint_workshop.project_3_gold
# MAGIC COMMENT 'Gold layer: Business-level aggregates and analytics';

# COMMAND ----------

# DBTITLE 1,Create Volume
# MAGIC %sql
# MAGIC -- Create volume for raw data files
# MAGIC CREATE VOLUME IF NOT EXISTS wavepoint_workshop.project_3_bronze.raw_data
# MAGIC COMMENT 'Volume for storing raw CSV and document files';

# COMMAND ----------

# DBTITLE 1,Create Sub-Directories
# Create sub-directories
dbutils.fs.mkdirs("/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data")
dbutils.fs.mkdirs("/Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles")

print("✓ Created sub-directories: data/ and articles/")

# COMMAND ----------

# DBTITLE 1,Step 3: Copy Raw Data
# MAGIC %md
# MAGIC ## Step 3: Copy Raw Data to Volume
# MAGIC
# MAGIC ### 3.1 Data Sources
# MAGIC
# MAGIC The project data lives in your `project-3` repository under `doc/data/` (20 CSV files) and `doc/articles/` (31 PDF documents). If you haven't already, pull the latest changes from your Git remote to get the new dental billing data model.
# MAGIC
# MAGIC **Data model design:** `doc/dental_data_model_design.md` - full ER diagram, relationships, money mechanics, and behavioural rules.
# MAGIC
# MAGIC **Data dictionary:** `doc/data/README.md` - column-level documentation for all 20 tables (50,760 rows total).
# MAGIC
# MAGIC All data is synthetic (seed = 42, deterministic). No PHI, no real patients, no real practices.
# MAGIC
# MAGIC **From `doc/data/` folder (20 CSV files):**
# MAGIC
# MAGIC Reference and structure:
# MAGIC - `dental_offices.csv` (20 rows)
# MAGIC - `insurance_networks.csv` (3 rows)
# MAGIC - `insurance_companies.csv` (9 rows)
# MAGIC - `insurance_company_networks.csv` (19 rows)
# MAGIC - `office_network_participation.csv` (39 rows)
# MAGIC - `office_insurance_network.csv` (180 rows)
# MAGIC - `insurance_policies.csv` (35 rows)
# MAGIC - `billing_codes.csv` (22 rows)
# MAGIC - `coverage_rules.csv` (770 rows)
# MAGIC
# MAGIC People:
# MAGIC - `patients.csv` (796 rows)
# MAGIC - `primary_policy_holders.csv` (200 rows)
# MAGIC - `policy_dependents.csv` (596 rows)
# MAGIC - `patient_benefit_years.csv` (2,388 rows)
# MAGIC
# MAGIC Activity:
# MAGIC - `recall_reminders.csv` (4,776 rows)
# MAGIC - `appointments.csv` (6,044 rows)
# MAGIC - `appointment_reminders.csv` (11,789 rows)
# MAGIC
# MAGIC Money:
# MAGIC - `invoices.csv` (5,232 rows)
# MAGIC - `invoice_lines.csv` (12,478 rows)
# MAGIC - `claims_and_payments.csv` (5,232 rows)
# MAGIC - `claim_disputes.csv` (132 rows)
# MAGIC
# MAGIC **From `doc/articles/` folder:**
# MAGIC - 31 PDF documents (dental RCM, billing, and practice management articles)
# MAGIC
# MAGIC ### 3.2 Copy Files from Repo to Volume
# MAGIC
# MAGIC The CSV files are already in your Git folder workspace. Copy them to the volume so Databricks SQL and Auto Loader can read them. Run the Python cell below to copy all CSV and PDF files.

# COMMAND ----------

# DBTITLE 1,Copy Files to Volume
import os

# Source: Git folder workspace path (adjust YOUR_EMAIL)
YOUR_EMAIL = "binwu247@gmail.com"
CATALOG = "wavepoint_workshop"
PROJECT = "project_3"

REPO_DATA_DIR = f"/Workspace/Users/{YOUR_EMAIL}/project-3/doc/data"
REPO_ARTICLES_DIR = f"/Workspace/Users/{YOUR_EMAIL}/project-3/doc/articles"

# Destination: UC volume
VOLUME_DATA_DIR = f"/Volumes/{CATALOG}/{PROJECT}_bronze/raw_data/data"
VOLUME_ARTICLES_DIR = f"/Volumes/{CATALOG}/{PROJECT}_bronze/raw_data/articles"

# Copy all CSV files
csv_files = [f for f in os.listdir(REPO_DATA_DIR) if f.endswith('.csv')]
for csv_file in csv_files:
    dbutils.fs.cp(f"{REPO_DATA_DIR}/{csv_file}", f"{VOLUME_DATA_DIR}/{csv_file}")
print(f"Copied {len(csv_files)} CSV files to volume")

# Copy all PDF files
pdf_files = [f for f in os.listdir(REPO_ARTICLES_DIR) if f.endswith('.pdf')]
for pdf_file in pdf_files:
    dbutils.fs.cp(f"{REPO_ARTICLES_DIR}/{pdf_file}", f"{VOLUME_ARTICLES_DIR}/{pdf_file}")
print(f"Copied {len(pdf_files)} PDF files to volume")

# COMMAND ----------

# DBTITLE 1,Verify Upload
# List files in data directory
print("Files in /data:")
display(dbutils.fs.ls("/Volumes/wavepoint_workshop/project_3_bronze/raw_data/data/"))

print("\nFiles in /articles:")
display(dbutils.fs.ls("/Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles/"))

# COMMAND ----------

# DBTITLE 1,Step 4: Connect GitHub
# MAGIC %md
# MAGIC ## Step 4: Connect Your GitHub Repository
# MAGIC
# MAGIC ### 4.1 Create a GitHub Repository
# MAGIC
# MAGIC Create a new repository for your project, e.g. `https://github.com/<your-username>/project-3.git`
# MAGIC
# MAGIC ### 4.2 Connect Repository to Databricks Workspace
# MAGIC
# MAGIC **Using Databricks Assistant (Genie Code):**
# MAGIC
# MAGIC Ask the assistant: "Connect my GitHub repository https://github.com/<your-username>/project-3.git to this Databricks workspace"
# MAGIC
# MAGIC The assistant will:
# MAGIC 1. Clone the repository into your workspace
# MAGIC 2. Set up the Git folder at `/Workspace/Users/<your-email>/project-3`
# MAGIC 3. Enable you to commit, push, and pull changes
# MAGIC
# MAGIC **Manual Method:**
# MAGIC
# MAGIC 1. Go to **Workspace** → **Repos**
# MAGIC 2. Click **Add Repo**
# MAGIC 3. Enter your GitHub repository URL
# MAGIC 4. Select **Git provider: GitHub**
# MAGIC 5. Click **Create Repo**
# MAGIC
# MAGIC ### 4.3 Configure GitHub Repository Access in Databricks
# MAGIC
# MAGIC ⚠️ **Important:** Before you can push commits to GitHub, you need to configure authentication between Databricks and GitHub.
# MAGIC
# MAGIC #### Option A: Using Databricks GitHub App (Recommended)
# MAGIC
# MAGIC **Step 1: Link Your GitHub Account**
# MAGIC 1. Click your **user profile icon** (top right corner)
# MAGIC 2. Select **Settings** → **Linked accounts**
# MAGIC 3. Click **Link account** next to **GitHub**
# MAGIC 4. Authenticate with your GitHub credentials
# MAGIC 5. Authorize Databricks to access your repositories
# MAGIC
# MAGIC **Step 2: Install the Databricks GitHub App**
# MAGIC 1. Go to: https://github.com/apps/databricks/installations/new
# MAGIC 2. Select your GitHub account or organization
# MAGIC 3. Choose repository access: Select **"Only select repositories"** and choose your `project-3` repository
# MAGIC 4. Click **Install** or **Save**
# MAGIC 5. GitHub will redirect you back to Databricks
# MAGIC
# MAGIC **Step 3: Verify the Connection**
# MAGIC 1. Make a small change to any file in your Git folder
# MAGIC 2. Ask Databricks Assistant: "Show me the Git status and commit this change"
# MAGIC 3. If successful, you'll see the commit pushed to your GitHub repository
# MAGIC
# MAGIC #### Option B: Using Personal Access Token
# MAGIC
# MAGIC 1. Go to GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
# MAGIC 2. Click **Generate new token (classic)**
# MAGIC 3. Select scope: ✅ **`repo`** (Full control of private repositories)
# MAGIC 4. Go to Databricks **Settings** → **Linked accounts** → GitHub → **Add token**
# MAGIC 5. Paste your token and click **Save**

# COMMAND ----------

# DBTITLE 1,Step 5: Create Raw Tables
# MAGIC %md
# MAGIC ## Step 5: Create Raw Tables (Bronze Layer)
# MAGIC
# MAGIC Now you're ready to create tables from the CSV files using the five notebooks in this folder:
# MAGIC
# MAGIC ### Notebook Overview
# MAGIC
# MAGIC 1. **Step_5_01_SQL_CREATE_TABLE** — Simplest approach using SQL CREATE TABLE. Best for quick one-time loads.
# MAGIC 2. **Step_5_02_PySpark_Schema_Inference** — PySpark DataFrame API with schema inference. Best for data exploration.
# MAGIC 3. **Step_5_03_COPY_INTO_Incremental** — COPY INTO for incremental loading. Best for idempotent, repeatable loads.
# MAGIC 4. **Step_5_04_Auto_Loader_Streaming** — Auto Loader for streaming/batch ingestion. Best for production pipelines.
# MAGIC 5. **Step_5_05_Loop_All_Files_Automated** — Automated loop to create all 20 tables at once. Best for bulk table creation.
# MAGIC
# MAGIC ### Expected Tables in Bronze Schema (`wavepoint_workshop.project_3_bronze`)
# MAGIC
# MAGIC **Reference and structure:**
# MAGIC - `dental_offices`, `insurance_networks`, `insurance_companies`, `insurance_company_networks`
# MAGIC - `office_network_participation`, `office_insurance_network`, `insurance_policies`, `billing_codes`, `coverage_rules`
# MAGIC
# MAGIC **People:**
# MAGIC - `patients`, `primary_policy_holders`, `policy_dependents`, `patient_benefit_years`
# MAGIC
# MAGIC **Activity:**
# MAGIC - `recall_reminders`, `appointments`, `appointment_reminders`
# MAGIC
# MAGIC **Money:**
# MAGIC - `invoices`, `invoice_lines`, `claims_and_payments`, `claim_disputes`

# COMMAND ----------

# DBTITLE 1,Step 6: Verify Your Setup
# MAGIC %md
# MAGIC ## Step 6: Verify Your Setup
# MAGIC
# MAGIC Run the SQL cells below to verify that your schemas, volume, tables, and sample data are all set up correctly.

# COMMAND ----------

# DBTITLE 1,Check Schemas
# MAGIC %sql
# MAGIC SHOW SCHEMAS IN wavepoint_workshop LIKE '%project_3%';

# COMMAND ----------

# DBTITLE 1,Check Volume
# MAGIC %sql
# MAGIC SHOW VOLUMES IN wavepoint_workshop.project_3_bronze;

# COMMAND ----------

# DBTITLE 1,Check Tables
# MAGIC %sql
# MAGIC SHOW TABLES IN wavepoint_workshop.project_3_bronze;

# COMMAND ----------

# DBTITLE 1,Sample Data
# MAGIC %sql
# MAGIC SELECT * FROM wavepoint_workshop.project_3_bronze.patients LIMIT 5;

# COMMAND ----------

# DBTITLE 1,Step 7: Execute the Project
# MAGIC %md
# MAGIC ## Step 7: Execute the Project
# MAGIC
# MAGIC ### 7.1 Create All Bronze Tables Using Option 5
# MAGIC
# MAGIC For this hands-on project, we'll use **Option 5: Loop All Files Automated** to create all 20 tables at once.
# MAGIC
# MAGIC **Instructions:**
# MAGIC
# MAGIC 1. Open the notebook: **Step_5_05_Loop_All_Files_Automated**
# MAGIC 2. Review the code that loops through all CSV files
# MAGIC 3. Update the catalog and schema names to match your setup
# MAGIC 4. Run all cells to create the 20 bronze tables
# MAGIC 5. Verify the tables were created successfully
# MAGIC
# MAGIC ### 7.2 Commit Your Work to GitHub
# MAGIC
# MAGIC Once you've created the tables, commit your work to version control.
# MAGIC
# MAGIC 1. Create a new branch: Ask Databricks Assistant "Create a new Git branch called 'hands_on_project_1' and switch to it"
# MAGIC 2. Check Git status: Ask Databricks Assistant "Show me the Git status of the project-3 repository"
# MAGIC 3. Commit and push: Ask Databricks Assistant "Commit all changes with message 'Add hands-on project 1: Bronze layer setup' and push to GitHub"
# MAGIC
# MAGIC **What to commit:**
# MAGIC - `hands_on_project_1/` folder with all 5 notebook files and README.md
# MAGIC - Any additional files you created
# MAGIC
# MAGIC **Why use version control?**
# MAGIC - Track changes to your project over time
# MAGIC - Collaborate with team members
# MAGIC - Revert to previous versions if needed
# MAGIC - Document your learning progress

# COMMAND ----------

# DBTITLE 1,Step 8: Silver Layer
# MAGIC %md
# MAGIC ## Step 8: Create Silver Layer (Data Cleaning & Enrichment)
# MAGIC
# MAGIC The silver layer transforms raw bronze data into clean, standardized, and enriched tables ready for analytics. This step uses the **Step_8_Silver_Layer_Cleaning** notebook to create all 20 silver tables.
# MAGIC
# MAGIC 📖 **[Delta Lake Best Practices](https://docs.databricks.com/aws/en/delta/index.html)**
# MAGIC
# MAGIC ### 8.1 What the Silver Layer Does
# MAGIC
# MAGIC | Category | What We Do |
# MAGIC |----------|------------|
# MAGIC | **Text Standardization** | Normalize all categorical text columns to lowercase (e.g., `"No-Show"` → `"no-show"`) |
# MAGIC | **Null Handling** | Replace nulls with sensible defaults (e.g., `source_recall_id` nulls → `0`, `denial_reason_code` nulls → `'N/A'`) |
# MAGIC | **Derived Columns** | Add business-relevant computed columns (e.g., `age_group`, `is_no_show`, `is_denied`, `unpaid_amount`, `is_overdue`) |
# MAGIC | **Audit Columns** | Add `_silver_loaded_at` timestamp to every table for lineage tracking |
# MAGIC
# MAGIC ### 8.2 Enrichment Highlights
# MAGIC
# MAGIC **Patients table:**
# MAGIC - `age_group`: child, young_adult, adult, middle_aged, senior
# MAGIC - `gender`: Expanded from M/F/O to male/female/other
# MAGIC - `state`: Standardized to UPPERCASE
# MAGIC
# MAGIC **Appointments table:**
# MAGIC - `is_no_show`: Boolean flag for no-show appointments
# MAGIC - `is_cancelled`: Boolean flag for cancelled appointments
# MAGIC - `appointment_date`: Date-only extraction from timestamp
# MAGIC - `day_of_week`: Day name (Monday, Tuesday, etc.)
# MAGIC - `source_recall_id`: Nulls filled with 0
# MAGIC
# MAGIC **Claims and Payments table:**
# MAGIC - `is_denied`: Boolean flag for denied claims
# MAGIC - `unpaid_amount`: Calculated as `amount_claimed - amount_paid`
# MAGIC - `denial_reason_code`: Nulls replaced with `'N/A'` (non-denied) or `'UNKNOWN'` (denied without code)
# MAGIC
# MAGIC **Invoices table:**
# MAGIC - `is_overdue`: Boolean flag for invoices past due date with remaining balance
# MAGIC - `has_patient_balance`: Boolean flag for invoices with outstanding patient balance
# MAGIC - `days_overdue`: Number of days past due date
# MAGIC
# MAGIC **Patient Benefit Years table:**
# MAGIC - `deductible_met_pct`: Percentage of deductible met
# MAGIC - `benefit_used_pct`: Percentage of annual benefit used
# MAGIC - `is_benefit_exhausted`: Boolean flag when benefit remaining <= 0
# MAGIC
# MAGIC ### 8.3 Execute the Silver Layer
# MAGIC
# MAGIC 1. Open the notebook: **Step_8_Silver_Layer_Cleaning** (in this folder)
# MAGIC 2. Review the 4 SQL cells that create 20 silver tables grouped by category:
# MAGIC    - **Reference & Structure** (9 tables): offices, insurance, policies, billing codes, coverage rules
# MAGIC    - **People** (4 tables): patients, policy holders, dependents, benefit years
# MAGIC    - **Activity** (3 tables): recalls, appointments, appointment reminders
# MAGIC    - **Money** (4 tables): invoices, invoice lines, claims, disputes
# MAGIC 3. Run all SQL cells to create the silver tables
# MAGIC 4. Run the verification queries to confirm:
# MAGIC    - All 20 silver tables exist
# MAGIC    - Row counts match between bronze and silver
# MAGIC    - Data quality fixes were applied correctly
# MAGIC    - Enrichment columns have valid values
# MAGIC
# MAGIC ### 8.4 Verification Results
# MAGIC
# MAGIC All 20 silver tables were created and verified:
# MAGIC - All row counts match bronze (50,760 total rows)
# MAGIC - `appointment_status` standardized to lowercase: `completed`, `no-show`, `cancelled`
# MAGIC - `is_no_show` flag: 543 true / 5,501 false (matches exact no-show count)
# MAGIC - `age_group` distribution: child (319), young_adult (165), adult (183), middle_aged (108), senior (21)
# MAGIC - `denial_reason_code` nulls eliminated: `N/A` for 4,454 non-denied claims
# MAGIC - `unpaid_amount`: $0 avg for clean-paid claims, $216.94 avg for denied claims
# MAGIC - `is_overdue`: 970 overdue invoices
# MAGIC - `gender` expanded: male (408), female (372), other (16)
# MAGIC - `day_of_week`: Monday busiest (2,689), no weekend appointments
# MAGIC
# MAGIC ### 8.5 Key Lesson: Bronze vs Silver
# MAGIC
# MAGIC The bronze layer preserves data **exactly as received** — no transformations, no standardization. This is critical for:
# MAGIC - **Auditability**: You can always trace back to the raw data
# MAGIC - **Reprocessing**: If cleaning rules change, you can re-run silver from bronze without re-ingesting
# MAGIC - **Data quality**: The silver layer is where you enforce standards and catch issues
# MAGIC
# MAGIC The silver layer is the **clean, trusted data** that downstream consumers (dashboards, ML models, reports) should query instead of bronze.

# COMMAND ----------

# DBTITLE 1,Step 9: Gold Layer
# MAGIC %md
# MAGIC ## Step 9: Create Gold Layer (Business Analytics & Aggregations)
# MAGIC
# MAGIC The gold layer creates business-level aggregates and analytics-ready datasets from the silver tables. This step uses the **Step_9_Gold_Layer_Analytics** notebook to create 8 gold tables that pre-compute joins and aggregations for dashboard consumption.
# MAGIC
# MAGIC 📖 **[Delta Lake Best Practices](https://docs.databricks.com/aws/en/delta/index.html)**
# MAGIC
# MAGIC ### 9.1 Gold Tables Created
# MAGIC
# MAGIC | Table | Granularity | Source Silver Tables | Purpose |
# MAGIC |-------|-------------|---------------------|---------|
# MAGIC | `gold_kpi_summary` | Single row | All key tables | Overview KPIs: patients, appointments, claims, revenue, denial rate, no-show rate |
# MAGIC | `gold_monthly_revenue` | Monthly | invoices | Monthly financial trends: gross/net revenue, writeoffs, patient balances, overdue |
# MAGIC | `gold_revenue_by_procedure` | Monthly x procedure | invoice_lines + invoices | Revenue by procedure category (preventive/basic/major) with insurance vs patient portions |
# MAGIC | `gold_patient_summary` | Per patient | patients + appointments + invoices + claims | Per-patient: visits, spending, no-shows, claims, balances, denial rate |
# MAGIC | `gold_office_performance` | Per office | dental_offices + appointments + invoices + claims | Per-office: revenue, no-show rate, denial rate, adjudication time |
# MAGIC | `gold_payer_performance` | Per insurance company | insurance_companies + claims | Per-payer: denial rate, adjudication time, total claimed/paid/unpaid, network split |
# MAGIC | `gold_appointment_analytics` | Monthly x visit type | appointments | Appointment metrics: no-show rate, cancellation rate, completion rate |
# MAGIC | `gold_recall_effectiveness` | Per channel x response | recall_reminders | Recall campaign conversion rates by channel, delivery status, and patient response |
# MAGIC
# MAGIC ### 9.2 Design Principles
# MAGIC
# MAGIC - **Pre-compute JOINs**: All cross-table joins are materialized in gold tables, so dashboard queries don't need runtime joins
# MAGIC - **Business granularity**: Aggregations at monthly, per-patient, per-office, and per-payer levels
# MAGIC - **Use silver enrichment**: Leverage `is_no_show`, `is_denied`, `is_overdue`, `age_group`, `unpaid_amount` from silver layer
# MAGIC - **Audit trail**: `_gold_loaded_at` timestamp on every table for lineage tracking
# MAGIC
# MAGIC ### 9.3 Execute the Gold Layer
# MAGIC
# MAGIC 1. Open the notebook: **Step_9_Gold_Layer_Analytics** (in this folder)
# MAGIC 2. Review the 8 SQL cells grouped by category:
# MAGIC    - **KPI Summary** (1 table): Overview metrics for the dashboard
# MAGIC    - **Financial Analytics** (2 tables): Monthly revenue trends and revenue by procedure category
# MAGIC    - **Entity Analytics** (3 tables): Per-patient, per-office, and per-payer performance summaries
# MAGIC    - **Activity Analytics** (2 tables): Appointment analytics and recall effectiveness
# MAGIC 3. Run all SQL cells to create the 8 gold tables
# MAGIC 4. Run the verification queries to confirm:
# MAGIC    - All 8 gold tables exist
# MAGIC    - Row counts are correct (796 patients, 20 offices, 9 payers, 36 months, etc.)
# MAGIC    - Aggregations match silver layer totals
# MAGIC
# MAGIC ### 9.4 Verification Results
# MAGIC
# MAGIC All 8 gold tables created and verified:
# MAGIC
# MAGIC | Table | Rows | Key Metric |
# MAGIC |-------|------|------------|
# MAGIC | gold_kpi_summary | 1 | $1.45M total revenue, 14.87% denial rate, 8.98% no-show rate |
# MAGIC | gold_monthly_revenue | 36 | 36 months of financial data (Sep 2023 - Aug 2026) |
# MAGIC | gold_revenue_by_procedure | 108 | 36 months x 3 procedure categories |
# MAGIC | gold_patient_summary | 796 | One row per patient with full activity history |
# MAGIC | gold_office_performance | 20 | One row per dental office with performance metrics |
# MAGIC | gold_payer_performance | 9 | One row per insurance company with claim metrics |
# MAGIC | gold_appointment_analytics | 144 | 36 months x 4 visit types |
# MAGIC | gold_recall_effectiveness | 21 | Channel x delivery x response combinations |
# MAGIC
# MAGIC ### 9.5 Key Lesson: Silver vs Gold
# MAGIC
# MAGIC The silver layer contains **clean, standardized, row-level data** — one row per entity (one row per patient, one row per appointment, one row per claim).
# MAGIC
# MAGIC The gold layer contains **aggregated, business-ready data** — one row per business entity with computed metrics (one row per patient with their lifetime stats, one row per office with their performance metrics, one row per month with revenue totals).
# MAGIC
# MAGIC This separation means:
# MAGIC - **Dashboards query gold tables** for fast, pre-computed results
# MAGIC - **Analysts query silver tables** when they need row-level detail or custom aggregations
# MAGIC - **Data engineers query bronze tables** only for debugging or reprocessing
# MAGIC - **All three layers can be refreshed independently** — re-run silver from bronze, re-run gold from silver

# COMMAND ----------

# DBTITLE 1,Step 10: Create Dashboard
# MAGIC %md
# MAGIC ## Step 10: Create Dashboard
# MAGIC
# MAGIC This step builds the **Dental Billing Analytics** AI/BI Dashboard on top of the **gold and silver layers**. The dashboard has 4 pages, 30+ widgets, and 6 cross-entity charts that join multiple tables.
# MAGIC
# MAGIC 📖 **[AI/BI Dashboards Documentation](https://docs.databricks.com/aws/en/dashboards/)**
# MAGIC
# MAGIC ### 10.1 Add Datasets
# MAGIC
# MAGIC The dashboard is backed by 36 datasets that query the gold and silver layers (no bronze tables):
# MAGIC
# MAGIC | Dataset | Source | Purpose |
# MAGIC |---------|--------|--------|
# MAGIC | Overview_KPIs | Gold: `gold_kpi_summary` | 6 counter KPIs (patients, appointments, claims, revenue, denial rate, no-show rate) |
# MAGIC | Appointment_Status | Silver: `appointments` | Pie chart of appointment status distribution |
# MAGIC | Claims_Status | Silver: `claims_and_payments` | Pie chart of claim status distribution |
# MAGIC | Monthly_Financials | Gold: `gold_monthly_revenue` | Monthly revenue trend and patient balance trend |
# MAGIC | Denial_Analysis_by_Payer | Gold: `gold_payer_performance` | Denial rate and days-to-adjudicate by payer |
# MAGIC | Denial_Reasons | Silver: `claims_and_payments` | Denial reason code counts |
# MAGIC | Dispute_Outcomes | Silver: `claim_disputes` | Dispute outcome distribution |
# MAGIC | Appointments_by_Office | Gold: `gold_office_performance` | Appointments per office |
# MAGIC | NoShow_by_Age_Group | Gold: `gold_patient_summary` | No-show rate by age group |
# MAGIC | Visit_Type_Distribution | Gold: `gold_appointment_analytics` | Visit type pie chart |
# MAGIC | Recall_Reminder_Effectiveness | Gold: `gold_recall_effectiveness` | Conversion rate by recall type |
# MAGIC | Patient_Balance_by_Office | Gold: `gold_office_performance` | Patient balance per office |
# MAGIC | Revenue_by_Procedure_Category | Gold: `gold_revenue_by_procedure` | Revenue by procedure category |
# MAGIC | Network_Status_Comparison | Silver: `claims_and_payments` | In-network vs out-of-network claims |
# MAGIC | Cross-Entity Claims | Silver: claims + insurance + offices | 4 cross-entity bar charts |
# MAGIC | Cross-Entity Revenue | Silver: invoices + patients | Revenue by patient demographics |
# MAGIC
# MAGIC The remaining 20 datasets are metric views on individual silver tables, used by the semantic model entities.
# MAGIC
# MAGIC ### 10.2 Build the Semantic Model and Relationship Graph
# MAGIC
# MAGIC The semantic model connects datasets through join relationships, enabling cross-entity queries without writing explicit JOINs.
# MAGIC
# MAGIC **What was built:**
# MAGIC
# MAGIC 1. **Registered 36 entities** — one per silver table and per SQL aggregation dataset
# MAGIC 2. **Added 32 foreign-key relationships** — matching the ER diagram, all using `CARDINALITY_MANY_TO_ONE`
# MAGIC 3. **Added 4 cross-entity measures:**
# MAGIC    - `revenue_per_patient` = `MEASURE(Invoices.total_allowed_amount) / COUNT(Patients.patient_id)`
# MAGIC    - `claims_per_appointment` = `MEASURE(Claims_and_Payments.claim_count) / COUNT(Appointments.appointment_id)`
# MAGIC    - `avg_revenue_per_office` = `MEASURE(Invoices.total_allowed_amount) / COUNT(Dental_Offices.office_id)`
# MAGIC    - `unpaid_claim_amount` = `MEASURE(Claims_and_Payments.amount_claimed) - MEASURE(Claims_and_Payments.amount_paid)`
# MAGIC
# MAGIC **Key lesson — "not singly connected" error:**
# MAGIC
# MAGIC With 32 relationships across 20 connected entities, multiple paths existed between many entity pairs (e.g., Dental_Offices to Claims_and_Payments had 3+ paths). The relationship graph engine requires a **singly connected** graph (exactly one path between any two entities). Cycles caused every cross-entity query to fail with `INVALID_PARAMETER_VALUE: Semantic model graph is not singly connected`.
# MAGIC
# MAGIC **Resolution:** Cleared all 32 relationships and 4 measures, then replaced cross-entity queries with **joined local metric views** (see below). This embeds JOINs directly in the metric view's `source` and `joins` YAML, avoiding the graph traversal issue entirely.
# MAGIC
# MAGIC 📖 **[Relationship Graphs Documentation](https://docs.databricks.com/aws/en/dashboards/relationship-graphs)**
# MAGIC
# MAGIC ### 10.3 Build Dashboard Pages
# MAGIC
# MAGIC **Overview Page:**
# MAGIC - 6 counter KPIs: Total Patients, Appointments, Claims, Revenue, Denial Rate, No-Show Rate
# MAGIC - 3 charts: Appointment Status (pie), Claims Status (pie), Monthly Revenue Trend (line)
# MAGIC
# MAGIC **Claims & Denials Page:**
# MAGIC - Denial Rate by Insurance Company (bar)
# MAGIC - Denial Reasons (bar)
# MAGIC - Dispute Outcomes (bar)
# MAGIC - Avg Days to Adjudicate by Payer (bar)
# MAGIC - Denial Analysis Detail (table)
# MAGIC - Unpaid Claims by Insurance Company (cross-entity bar)
# MAGIC - Claim Amount by Office (cross-entity bar)
# MAGIC - Claim Count by Office State (cross-entity bar)
# MAGIC - Total Paid by Payer Type (cross-entity bar)
# MAGIC
# MAGIC **Patients & Appointments Page:**
# MAGIC - Appointments by Office (bar)
# MAGIC - No-Show Rate by Age Group (bar)
# MAGIC - Visit Type Distribution (pie)
# MAGIC - Recall Reminder Effectiveness (bar)
# MAGIC - Revenue by Patient Gender (cross-entity bar)
# MAGIC
# MAGIC **Financial Page:**
# MAGIC - Patient Balance by Office (bar)
# MAGIC - Revenue by Procedure Category (bar)
# MAGIC - In-Network vs Out-of-Network Claims (bar)
# MAGIC - Monthly Patient Balance Trend (line)
# MAGIC - Unpaid Claims by Office (cross-entity bar)
# MAGIC
# MAGIC ### 10.4 Create Cross-Entity Charts
# MAGIC
# MAGIC Cross-entity charts join data from multiple tables using **local metric views** that embed JOINs in their YAML configuration.
# MAGIC
# MAGIC **Cross-Entity Claims Analysis** (`datasets/cross_entity_claims`):
# MAGIC
# MAGIC Joins `claims_and_payments` with `insurance_companies` and `dental_offices`:
# MAGIC
# MAGIC ```yaml
# MAGIC version: 1.1
# MAGIC source: wavepoint_workshop.project_3_silver.claims_and_payments
# MAGIC joins:
# MAGIC   - name: insurance_companies
# MAGIC     source: wavepoint_workshop.project_3_silver.insurance_companies
# MAGIC     on: source.insurance_company_id = insurance_companies.insurance_company_id
# MAGIC   - name: dental_offices
# MAGIC     source: wavepoint_workshop.project_3_silver.dental_offices
# MAGIC     on: source.office_id = dental_offices.office_id
# MAGIC dimensions:
# MAGIC   - name: company_name
# MAGIC     expr: insurance_companies.company_name
# MAGIC   - name: office_name
# MAGIC     expr: dental_offices.office_name
# MAGIC   - name: office_state
# MAGIC     expr: dental_offices.state
# MAGIC   - name: payer_type
# MAGIC     expr: insurance_companies.payer_type
# MAGIC   - name: claim_status
# MAGIC     expr: source.claim_status
# MAGIC measures:
# MAGIC   - name: unpaid_amount
# MAGIC     expr: SUM(source.amount_claimed - source.amount_paid)
# MAGIC   - name: total_claimed
# MAGIC     expr: SUM(source.amount_claimed)
# MAGIC   - name: total_paid
# MAGIC     expr: SUM(source.amount_paid)
# MAGIC   - name: claim_count
# MAGIC     expr: COUNT(1)
# MAGIC ```
# MAGIC
# MAGIC **Cross-Entity Revenue Analysis** (`datasets/cross_entity_revenue`):
# MAGIC
# MAGIC Joins `invoices` with `patients`:
# MAGIC
# MAGIC ```yaml
# MAGIC version: 1.1
# MAGIC source: wavepoint_workshop.project_3_silver.invoices
# MAGIC joins:
# MAGIC   - name: patients
# MAGIC     source: wavepoint_workshop.project_3_silver.patients
# MAGIC     on: source.patient_id = patients.patient_id
# MAGIC dimensions:
# MAGIC   - name: gender
# MAGIC     expr: patients.gender
# MAGIC   - name: patient_state
# MAGIC     expr: patients.state
# MAGIC   - name: age
# MAGIC     expr: patients.age
# MAGIC measures:
# MAGIC   - name: total_revenue
# MAGIC     expr: SUM(source.total_allowed_amount)
# MAGIC   - name: invoice_count
# MAGIC     expr: COUNT(1)
# MAGIC ```
# MAGIC
# MAGIC **6 cross-entity bar charts** were created from these two datasets:
# MAGIC
# MAGIC | Chart | Page | Dataset | X-Axis | Y-Axis |
# MAGIC |-------|------|---------|--------|--------|
# MAGIC | Unpaid Claims by Insurance Company | Claims & Denials | cross_entity_claims | company_name | unpaid_amount |
# MAGIC | Claim Amount by Office | Claims & Denials | cross_entity_claims | office_name | total_claimed |
# MAGIC | Claim Count by Office State | Claims & Denials | cross_entity_claims | office_state | claim_count |
# MAGIC | Total Paid by Payer Type | Claims & Denials | cross_entity_claims | payer_type | total_paid |
# MAGIC | Revenue by Patient Gender | Patients & Appointments | cross_entity_revenue | gender | total_revenue |
# MAGIC | Unpaid Claims by Office | Financial | cross_entity_claims | office_name | unpaid_amount |
# MAGIC
# MAGIC 📖 **[Metric Views Documentation](https://docs.databricks.com/aws/en/dashboards/metric-views)**
# MAGIC
# MAGIC ### 10.5 Data Quality Fixes
# MAGIC
# MAGIC **No-Show Rate by Age Group showing all zeros:**
# MAGIC
# MAGIC - **Root cause:** The original bronze SQL dataset checked `appointment_status = 'no-show'` (lowercase), but the bronze data value was `'No-Show'` (capitalized). Spark SQL is case-sensitive, so the condition never matched.
# MAGIC - **Fix in silver layer:** The silver layer normalizes all categorical text to lowercase, so `appointment_status = 'no-show'` now matches correctly.
# MAGIC - **Fix in gold layer:** The `gold_patient_summary` table pre-computes `no_show_count` and `no_show_rate_pct` per patient using the silver `is_no_show` boolean column.
# MAGIC - **Result:** No-show rates now display correctly from the gold table (e.g., child 10.1%, young_adult 8.9%, adult 8.3%, senior 7.6%, middle_aged 7.4%).
# MAGIC
# MAGIC **Gold table fan-out JOIN bug:**
# MAGIC
# MAGIC - **Root cause:** `gold_patient_summary` and `gold_office_performance` originally used a single multi-table JOIN (patients + appointments + invoices + claims). This caused a fan-out effect where each appointment row was multiplied by the number of invoices and claims, inflating `SUM(CASE WHEN ...)` columns (e.g., `no_show_count` was 14,029 instead of 543).
# MAGIC - **Fix:** Replaced multi-table JOINs with pre-aggregated subqueries — each entity (appointments, invoices, claims) is aggregated separately in a subquery, then LEFT JOINed to the main entity.
# MAGIC - **Lesson:** When joining multiple one-to-many relationships to a single parent, always pre-aggregate each child table in a subquery to avoid fan-out multiplication.

# COMMAND ----------

# DBTITLE 1,Step 11: CI/CD
# MAGIC %md
# MAGIC ## Step 11: CI/CD with Declarative Automation Bundles
# MAGIC
# MAGIC This project uses **Declarative Automation Bundles (DABs)** to automate deployment of the bronze tables, dashboard, and pipeline jobs across environments (dev, staging, prod).
# MAGIC
# MAGIC 📖 **[CI/CD Workflows on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/flows/)**
# MAGIC 📖 **[What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/index/)**
# MAGIC
# MAGIC ### 11.1 Project Structure
# MAGIC
# MAGIC ```
# MAGIC project-3/
# MAGIC   databricks.yml                 # Bundle configuration (root)
# MAGIC   .github/
# MAGIC     workflows/
# MAGIC       deploy.yml                  # GitHub Actions CI/CD pipeline
# MAGIC   dashboards/
# MAGIC     dental_billing.lvdash.json   # Exported dashboard JSON
# MAGIC   hands_on_project_1/
# MAGIC     README.md
# MAGIC     00_Instructions.py           # This notebook
# MAGIC     Step_5_01_SQL_CREATE_TABLE.ipynb
# MAGIC     Step_5_02_PySpark_Schema_Inference.ipynb
# MAGIC     Step_5_03_COPY_INTO_Incremental.ipynb
# MAGIC     Step_5_04_Auto_Loader_Streaming.ipynb
# MAGIC     Step_5_05_Loop_All_Files_Automated.ipynb
# MAGIC     Step_8_Silver_Layer_Cleaning.py  # Silver layer notebook
# MAGIC     Step_9_Gold_Layer_Analytics.py   # Gold layer notebook
# MAGIC   doc/
# MAGIC     data/                        # 20 CSV source files
# MAGIC     articles/                     # 31 PDF reference docs
# MAGIC     dental_data_model_design.md
# MAGIC ```
# MAGIC
# MAGIC ### 11.2 Install the Databricks CLI
# MAGIC
# MAGIC ```bash
# MAGIC # macOS
# MAGIC brew install databricks
# MAGIC
# MAGIC # Verify installation
# MAGIC databricks --version
# MAGIC
# MAGIC # Authenticate (opens browser)
# MAGIC databricks auth login --host https://<your-workspace-url>
# MAGIC ```
# MAGIC
# MAGIC ### 11.3 Bundle Configuration (`databricks.yml`)
# MAGIC
# MAGIC The `databricks.yml` file at the project root defines the bundle. Key sections:
# MAGIC
# MAGIC - **Variables:** Parameterize warehouse ID, catalog name, and schema for each environment
# MAGIC - **Targets:** Separate dev and prod environments with different workspaces and resources
# MAGIC - **Resources:** Define the dashboard and the bronze loader job as deployable resources
# MAGIC
# MAGIC ### 11.4 Export the Dashboard
# MAGIC
# MAGIC ```bash
# MAGIC # Export the Dental Billing Analytics dashboard
# MAGIC databricks bundle generate dashboard \
# MAGIC   --id 01f1a9408503107bba3222274c033e58 \
# MAGIC   --path ./dashboards/dental_billing.lvdash.json
# MAGIC
# MAGIC # Or use watch mode to sync UI edits back to the JSON file
# MAGIC databricks bundle generate dashboard \
# MAGIC   --id 01f1a9408503107bba3222274c033e58 \
# MAGIC   --path ./dashboards/dental_billing.lvdash.json \
# MAGIC   --watch
# MAGIC ```
# MAGIC
# MAGIC ### 11.5 Validate, Deploy, and Run
# MAGIC
# MAGIC ```bash
# MAGIC # Validate the bundle configuration
# MAGIC databricks bundle validate --target dev
# MAGIC
# MAGIC # Deploy to the dev environment
# MAGIC databricks bundle deploy --target dev
# MAGIC
# MAGIC # Deploy to production
# MAGIC databricks bundle deploy --target prod
# MAGIC
# MAGIC # Run the bronze loader job
# MAGIC databricks bundle run --target dev bronze_loader
# MAGIC ```
# MAGIC
# MAGIC ### 11.6 GitHub Actions CI/CD Pipeline
# MAGIC
# MAGIC The `.github/workflows/deploy.yml` file defines an automated pipeline that:
# MAGIC
# MAGIC 1. **Triggers** on push to `main` branch or manual dispatch
# MAGIC 2. **Validates** the bundle configuration
# MAGIC 3. **Deploys** to the target environment
# MAGIC 4. Uses **secrets** for authentication (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`)
# MAGIC
# MAGIC To set up GitHub secrets:
# MAGIC 1. Go to your GitHub repo **Settings** > **Secrets and variables** > **Actions**
# MAGIC 2. Add repository secrets: `DATABRICKS_HOST` and `DATABRICKS_TOKEN`
# MAGIC 3. The pipeline runs automatically on every push to `main`
# MAGIC
# MAGIC ### 11.7 CI/CD Best Practices
# MAGIC
# MAGIC - **Always validate before deploy:** Run `databricks bundle validate` in CI to catch config errors
# MAGIC - **Separate environments:** Use distinct catalogs, warehouses, and workspaces for dev vs prod
# MAGIC - **Parameterize with variables:** Use `${var.catalog}`, `${var.warehouse_id}` so the same bundle works across environments
# MAGIC - **Version-control everything:** The `.lvdash.json` file, notebooks, and `databricks.yml` are all in Git
# MAGIC - **Use `--watch` during development:** Sync UI dashboard edits back to the JSON file while iterating
# MAGIC - **Force flag for overrides:** Use `--force` during deployment to overwrite remote dashboards with local versions when needed
# MAGIC - **Test in dev first:** Deploy and validate in the dev target before promoting to prod

# COMMAND ----------

# DBTITLE 1,Next Steps & Resources
# MAGIC %md
# MAGIC ## Next Steps
# MAGIC
# MAGIC Once your Bronze layer is set up and committed:
# MAGIC
# MAGIC 1. **Silver Layer:** Done! See Step 8 above for the Step_8_Silver_Layer_Cleaning notebook
# MAGIC 2. **Gold Layer:** Done! See Step 9 above for the Step_9_Gold_Layer_Analytics notebook
# MAGIC 3. **Visualization:** Build dashboards from Gold tables (see Step 10 above)
# MAGIC 4. **Automation:** Schedule pipelines to refresh data
# MAGIC 5. **CI/CD:** Use Declarative Automation Bundles to automate deployment (see Step 11 above)
# MAGIC
# MAGIC ## Additional Resources
# MAGIC
# MAGIC - 📖 [Databricks Medallion Architecture](https://docs.databricks.com/aws/en/lakehouse/medallion)
# MAGIC - 📖 [Unity Catalog Volumes](https://docs.databricks.com/aws/en/catalog/volumes.html)
# MAGIC - 📖 [Delta Lake Best Practices](https://docs.databricks.com/aws/en/delta/index.html)
# MAGIC - 📖 [Auto Loader](https://docs.databricks.com/aws/en/ingestion/auto-loader/index.html)
# MAGIC - 📖 [Git Integration with Databricks](https://docs.databricks.com/aws/en/repos/index.html)
# MAGIC - 📖 [AI/BI Dashboards](https://docs.databricks.com/aws/en/dashboards/)
# MAGIC - 📖 [Metric Views](https://docs.databricks.com/aws/en/dashboards/metric-views)
# MAGIC - 📖 [Relationship Graphs](https://docs.databricks.com/aws/en/dashboards/relationship-graphs)
# MAGIC
# MAGIC ## Questions?
# MAGIC
# MAGIC If you encounter issues:
# MAGIC 1. Ask **Databricks Assistant (Genie Code)** for help
# MAGIC 2. Review the error messages carefully
# MAGIC 3. Check the documentation links above
# MAGIC 4. Consult with your instructor or peers
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC > **Note:** This notebook is the executable companion to `README.md`. Markdown cells provide documentation context; SQL and Python cells can be run directly to set up your project.
# MAGIC
# MAGIC Happy learning! 🚀