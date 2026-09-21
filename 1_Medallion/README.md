# Hands-On Project 1: Creating Raw Tables, Load Data and Build Dashboard in Databricks

## Overview

This hands-on project guides students through building a complete dental billing analytics platform on Databricks following the **Medallion Architecture**. Students will set up Unity Catalog schemas and volumes, load CSV data into Delta tables, clean and enrich the data in a silver layer, create business aggregates in a gold layer, build an AI/BI dashboard with cross-entity charts, and configure CI/CD with Declarative Automation Bundles.

## Medallion Architecture

The project follows the Databricks Medallion Architecture with three layers of increasing data quality and business value:

 ```
CSV Files (20 tables, 50K+ rows)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  BRONZE LAYER (wavepoint_workshop.project_3_bronze)             │
│  20 raw Delta tables loaded from CSV via Auto Loader            │
│  Notebooks: 01-05 (SQL CREATE, PySpark, COPY INTO, streaming)   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  SILVER LAYER (wavepoint_workshop.project_3_silver)             │
│  20 cleaned & enriched tables with:                             │
│  • Lowercase text standardization (e.g. "No-Show" → "no-show")  │
│  • Null handling (fill defaults, replace missing values)        │
│  • Derived columns(age_group, is_no_show, is_denied, is_overdue)│
│  • Audit timestamps (_silver_loaded_at)                         │
│  Notebook: 06_Silver_Layer_Cleaning.py                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  GOLD LAYER (wavepoint_workshop.project_3_gold)                 │
│  8 business-level aggregate tables:                             │
│  • gold_kpi_summary — Single-row overview KPIs                  │
│  • gold_monthly_revenue — Monthly financial trends              │
│  • gold_revenue_by_procedure — Revenue by procedure category    │
│  • gold_patient_summary — Per-patient aggregated metrics        │
│  • gold_office_performance — Per-office performance metrics     │
│  • gold_payer_performance — Per-insurance company metrics       │
│  • gold_appointment_analytics — Appointment metrics by month    │
│  • gold_recall_effectiveness — Recall campaign effectiveness    │
│  Notebook: 07_Gold_Layer_Analytics.py                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  DASHBOARD (AI/BI Lakeview)                                     │
│  4 pages, 30+ widgets, 6 cross-entity charts                    │
│  36 datasets querying gold (9) and silver (27) tables           │
│  No bronze tables — fully migrated to silver/gold layers        │
│  Cross-entity analysis via local metric views with JOINs        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  CI/CD (Declarative Automation Bundles)                         │
│  GitHub Actions pipeline for automated deployment               │
│  databricks.yml bundle configuration                            │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principle:** Each layer adds value without losing lineage. Bronze preserves raw data; silver standardizes and enriches; gold pre-computes business aggregates for fast dashboard queries. The dashboard queries gold tables for pre-computed analytics and silver tables for detailed distributions.

## Getting Started

Open the interactive guide: **[00_Instructions.py](./00_Instructions.py)** — a Databricks notebook with 22 cells (14 markdown, 4 SQL, 3 Python) that students can execute inline as they read through each step.

## Project Contents

| File | Description |
|------|-------------|
| `00_Instructions.py` | Interactive step-by-step notebook guide (run cells inline) |
| `README.md` | This overview file |
| `Step_5_01_SQL_CREATE_TABLE.ipynb` | Create tables using SQL CREATE TABLE |
| `Step_5_02_PySpark_Schema_Inference.ipynb` | Create tables using PySpark DataFrame API |
| `Step_5_03_COPY_INTO_Incremental.ipynb` | Create tables using COPY INTO for incremental loading |
| `Step_5_04_Auto_Loader_Streaming.ipynb` | Create tables using Auto Loader for streaming ingestion |
| `Step_5_05_Loop_All_Files_Automated.ipynb` | Automated loop to create all 20 tables at once |
| `Step_8_Silver_Layer_Cleaning.py` | Silver layer: Clean and enrich all 20 bronze tables |
| `Step_9_Gold_Layer_Analytics.py` | Gold layer: 8 aggregated analytics tables from silver data |

## Steps Covered

1. **Understand the Medallion Architecture** — Bronze, Silver, Gold layers
2. **Set Up Your Project Structure** — Create schemas and volumes in Unity Catalog
3. **Copy Raw Data to Volume** — Copy 20 CSV files and 31 PDFs from Git repo to UC volume
4. **Connect Your GitHub Repository** — Link GitHub to Databricks workspace
5. **Create Raw Tables (Bronze Layer)** — Load CSV data into 20 Delta tables
6. **Verify Your Setup** — Run SQL checks on schemas, volumes, and tables
7. **Execute the Project** — Run the automated notebook and commit to Git
8. **Create Silver Layer** — Clean and enrich bronze data (standardize text, handle nulls, add derived columns)
9. **Create Gold Layer** — Build 8 aggregated analytics tables (KPIs, monthly revenue, patient/office/payer summaries)
10. **Create Dashboard** — Build AI/BI dashboard on gold/silver layers with 4 pages, 30+ widgets, 6 cross-entity charts
11. **CI/CD** — Deploy with Declarative Automation Bundles and GitHub Actions

## Data Sources

All data is synthetic (seed = 42, deterministic). No PHI, no real patients, no real practices.

- **Data model design:** [`doc/dental_data_model_design.md`](../doc/dental_data_model_design.md)
- **Data dictionary:** [`doc/data/README.md`](../doc/data/README.md)
- **CSV files:** 20 tables, 50,760 rows total in `doc/data/`
- **PDF articles:** 31 documents in `doc/articles/`

## Naming Convention

⚠️ Always use underscores (`_`) in catalog, schema, and table names. Avoid hyphens (`-`) which cause SQL parsing errors.

✅ Good: `project_3_bronze`
❌ Bad: `project-3-bronze`

## Additional Resources

- [Databricks Medallion Architecture](https://docs.databricks.com/aws/en/lakehouse/medallion)
- [Unity Catalog Volumes](https://docs.databricks.com/aws/en/catalog/volumes.html)
- [AI/BI Dashboards](https://docs.databricks.com/aws/en/dashboards/)
- [Metric Views](https://docs.databricks.com/aws/en/dashboards/metric-views)
- [Relationship Graphs](https://docs.databricks.com/aws/en/dashboards/relationship-graphs)
- [Git Integration with Databricks](https://docs.databricks.com/aws/en/repos/index.html)
- [Declarative Automation Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/index/)

## Questions?

Ask **Databricks Assistant (Genie Code)** for help at any step!
