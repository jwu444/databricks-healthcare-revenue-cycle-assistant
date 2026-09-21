# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A six-part Databricks workshop building **an AI operations assistant for a multi-location dental practice** (appointments, billing, financials). Each project is a top-level folder named `<N>_<Topic>` — `0_Setup`, `1_Medallion`, `2_RAG`, `3_Genie`, `4_Supervisor`, `5_Chat_app` — and corresponds to an issue in the separate `wavepoint-build/ai-engineering-workshop` repo (private) (`#15`=1, `#16`=2, `#17`=3, `#18`=4, `#19`=5). Read the issue before starting a project — it is the spec.

The whole architecture follows from one split: **structured data** (20 Delta tables) answers *"what happened in our practice?"*, **unstructured documents** (31 PDFs) answer *"how is this work done?"*. Neither answers the other's questions, and project 4's supervisor routes between them. The root `README.md` covers this in full.

| Folder | Builds | State |
|---|---|---|
| `0_Setup` | Claude Code ↔ Databricks connection | Done — **README-only, no notebook** (see below) |
| `1_Medallion` | Medallion bronze→silver→gold, dashboard, CI/CD | Done |
| `2_RAG` | Vector index over the 31 PDFs (RAG) | Done — index **torn down**, rebuildable |
| `3_Genie` | Genie agent over the silver tables | Done — agent live, `01f1a99230b81b2eb2a86a65b7d1d3a9` |
| `4_Supervisor` | Multi-agent supervisor | To do — folder holds a placeholder README only |
| `5_Chat_app` | Chat app (Databricks App; React/FastAPI/Postgres) | To do — folder holds a placeholder README only |

## Commands

There is **no package manager, no test framework, and no build step.** Notebooks run in Databricks; the CLI drives everything else.

```bash
# Data consistency check — the closest thing to a test suite. Exit 0 = consistent, 1 = drift.
# Run after any change to doc/generate_dental_data.py. Takes ~1s.
cd doc && python3 validate_dental_data.py

# Regenerate the synthetic CSVs (deterministic, seed 42)
cd doc && python3 generate_dental_data.py

# Verify the workspace connection — 7 capability checks + a live embedding call
python 0_Setup/verify_connection.py --profile DEFAULT
python 0_Setup/verify_connection.py --skip-end-to-end   # no model call

# Bundle
databricks bundle validate --strict --target dev --profile DEFAULT
databricks bundle deploy -t dev --profile DEFAULT
databricks bundle run <resource> -t dev --profile DEFAULT

# Ad-hoc SQL / schema exploration (preferred over hand-navigating catalogs)
databricks experimental aitools tools query "SELECT 1" --profile DEFAULT
databricks experimental aitools tools discover-schema <catalog.schema.table> --profile DEFAULT
```

CI (`.github/workflows/deploy.yml`) runs `bundle validate` → `bundle deploy` → `bundle run bronze_loader` against `--target prod` on push to `main`.

## Databricks conventions

**Never auto-select a profile.** Pass `--profile <name>` explicitly and let the user choose, even when only one exists. Only `DEFAULT` is configured here.

**Route Databricks work through the skills** — load `databricks-core` first, then the matching product skill (`databricks-vector-search`, `databricks-genie-agents`, `databricks-dabs`, …). They carry current API shapes, but see the SDK gotcha below: verify against the installed version rather than trusting an example.

**Unity Catalog layout:**

```
wavepoint_workshop
├── project_3_bronze    20 raw tables + raw_data volume (31 PDFs under articles/)
├── project_3_silver    24 cleaned tables + article_parsed / article_chunks
└── project_3_gold      8 business aggregates
```

**Naming:** underscores in catalog/schema/table names — hyphens cause SQL parse errors and need backtick escaping. The one exception is the Vector Search endpoint name (`wavepoint-vs`), which is not a SQL identifier.

**Free-tier daily compute limit.** When it is exhausted, *every* query fails with `you have hit your free daily limit`, including `SELECT 1`. That is not a config problem — it resets.

## Every project must land in a bundle

**Projects 1–5 each add or update Databricks Asset Bundle resources so the work is deployment-ready.** A project is not finished when the notebook runs interactively — it is finished when its resources are declared in `resources/*.yml` and `databricks bundle validate --strict` passes on both targets.

Add resources under `resources/<name>.yml` (included by `databricks.yml` via `include: resources/*.yml`), then:

```bash
databricks bundle validate --strict --target dev  --profile DEFAULT
databricks bundle validate --strict --target prod --profile DEFAULT
```

Current coverage — **project 3 onward is a gap to close**:

| Project | Bundle resources | File |
|---|---|---|
| 1 | dashboard + 3 jobs (bronze/silver/gold) | `resources/dashboard_and_job.yml` |
| 2 | RAG ingest job; endpoint + index written but commented | `resources/rag_pipeline.yml` |
| 3 | **none yet** — Genie agent is not declared | — |
| 4, 5 | not started | — |

Two things to get right when adding resources:

- **Match the compute to the code.** Project 1's jobs pin `spark_version: 15.4.x-scala2.12`, which cannot run project 2's notebook at all — `ai_parse_document` needs DBR 17.3+ and `ai_prep_search` needs 18.2+. A notebook task with no cluster spec gets serverless, which is current enough. Copying an existing `job_cluster` block produces a job that validates and then fails at runtime.
- **Do not silently declare billing resources.** See the cost section — a Vector Search endpoint in a bundle means CI stands one up on merge.

## Notebook format

Projects 1–3 ship `00_Instructions.py` in **Databricks source format**, not Jupyter:

```python
# Databricks notebook source
# DBTITLE 1,Step 1: Something
# MAGIC %md
# MAGIC ## Markdown content
# COMMAND ----------
```

Every cell gets a `DBTITLE`. Markdown cells use `# MAGIC %md`, SQL cells `# MAGIC %sql`, Python cells are plain. When editing, verify structure holds — split on `\n# COMMAND ----------\n`, confirm each cell has a `DBTITLE`, and `ast.parse` the Python cells.

**Projects 4 and 5 are folders with a placeholder `README.md` and nothing else** — each links the issue that specs it. Adding the notebook is part of doing the project.

**Project 0 is deliberately README-only.** Its steps configure the laptop, and a notebook that lives in the workspace cannot tell you how to get access to the workspace. Its verification harness is a runnable script instead. Do not "fix" this by adding a notebook.

## Gotchas discovered the hard way

These cost real time. They are documented in the project READMEs too, but worth having up front.

**SDK wants typed objects, not dicts.** `vector_search_indexes.create_index(delta_sync_index_spec={...})` raises `AttributeError: 'dict' object has no attribute 'as_dict'` on `databricks-sdk 0.135.0`. Use `DeltaSyncVectorIndexSpecRequest` / `EmbeddingSourceColumn` / `PipelineType`. The documented example is out of date.

**`apply_redactions` silently drops link annotations** but leaves the objects in the file (still reachable via `/StructParent`), so URLs survive `garbage=4`. Delete links *before* any redaction.

**Change Data Feed is mandatory for a Delta Sync index.** Without `delta.enableChangeDataFeed = true` on the source table, index creation fails with a message far from the cause.

**`ai_prep_search` chunk schema:** there is no `$.page` field — a chunk can span a page break, so it exposes `pages` as an ARRAY. Use `$.pages[0].page_id`. There is no `source_uri` either; carry `doc_uri` through from your own table. Verify shapes with `schema_of_variant(...)` before writing extraction.

**`SHOW FUNCTIONS` does not list every built-in.** `ai_prep_search` is absent from `SHOW FUNCTIONS LIKE 'ai_p*'` but works. To test availability, *call* it — a complaint about the argument means it exists; `UNRESOLVED_ROUTINE` means it does not.

**`git checkout <name>` is ambiguous here** because branch names match directory names (`2_RAG`). Use `git switch`.

**Benefit years run Sep 1 → Aug 31**, not calendar years, and `patient_benefit_years` has no date columns to join on — the rule must be written into SQL. Data spans exactly `2023-09-01` → `2026-08-31`.

## 💰 Cost — the one thing that bills while idle

**A Vector Search endpoint bills continuously until deleted. There is no pause** — the CLI surface is only `create`, `delete`, `get`, `list`, `patch`, and `patch-endpoint` takes just `--target-qps`.

Everything else here is free at rest: the SQL warehouse auto-stops, the Genie agent costs only the SQL it runs, Foundation Model endpoints are pay-per-token.

Teardown is cheap because the expensive work is durable in Delta — `article_parsed` (2m18s of LLM parsing) and `article_chunks` survive, only the embeddings are disposable. Rebuild is ~30 minutes via project 2's Steps 7–9, with no PDF re-parsing.

**Before creating a Vector Search endpoint, say so and confirm.** `resources/rag_pipeline.yml` declares the endpoint and index but leaves them **commented on purpose** — uncommenting means any `bundle deploy`, including CI on merge, silently stands up a billing resource.

## Git

Branch per project, named after the folder (`2_RAG`, `4_Supervisor`), merge to `main` with `--no-ff` so each project stays a visible unit. `main` is the default branch. Remote branch deletion is blocked by the permission classifier — hand the user the command rather than working around it.

## Verify, don't assume

The pattern that has paid off repeatedly in this repo: run the thing before writing it down. The `SELECT DISTINCT` value inventory, the benefit-year date boundaries, the `ai_prep_search` schema, and every SQL example in the Genie config were all executed against the workspace before being committed — and three of those turned up something different from what the docs implied.
