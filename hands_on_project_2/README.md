# Hands-On Project 2: Vector Search Index (RAG) over the Dental Business Documents

## Overview

This hands-on project builds a **retrieval index** over 31 dental practice-management PDFs, so an LLM can answer questions like *"How do you post an EOB in Open Dental?"* or *"What A/R aging buckets should a practice track?"* — **with citations back to the source document**.

Project 1 built the Medallion Architecture over **structured** CSV data. This project covers the other half of a real lakehouse: **unstructured documents**. The same medallion thinking applies — the PDFs are bronze, the parsed and chunked text is silver.

## RAG Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  BRONZE — UC Volume (raw, unchanged)                            │
│  /Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles │
│  31 dental practice-management PDFs (7.5 MB)                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼  ai_parse_document()  — one LLM inference per document
┌─────────────────────────────────────────────────────────────────┐
│  SILVER — project_3_silver.article_parsed                       │
│  Raw parser VARIANT, one row per document                       │
│  Materialised once so chunking never re-parses (and re-pays)    │
└─────────────────────────────────────────────────────────────────┘
    │
    ├──▶ article_pages — flattened text + page number per element
    │
    ▼  ai_prep_search()  — semantic chunking on section boundaries
┌─────────────────────────────────────────────────────────────────┐
│  SILVER — project_3_silver.article_chunks                       │
│  chunk_id (PK) · doc_uri · page · chunk_position                │
│  content (shown to the LLM) · chunk_to_embed (embedded)         │
│  ⚠ delta.enableChangeDataFeed = true  ← index requires this     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼  Delta Sync index, managed embeddings (databricks-gte-large-en)
┌─────────────────────────────────────────────────────────────────┐
│  VECTOR SEARCH — project_3_silver.article_chunks_index          │
│  Endpoint: wavepoint-vs (STANDARD)                              │
│  Each chunk becomes a 1024-dimension vector                     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼  similarity search → top-k chunks
┌─────────────────────────────────────────────────────────────────┐
│  AI PLAYGROUND — chat model with the index attached as a tool   │
│  Answers grounded in retrieved text, traceable to a document    │
└─────────────────────────────────────────────────────────────────┘
```

**Key design principle:** parse once, chunk many times. Parsing is an LLM inference per document — slow and billed — so it is materialised into `article_parsed` and every chunking experiment reads from there. Tuning the chunk strategy re-runs only the cheap part.

## Embed One Column, Return Another

The subtlety that decides whether this index works. `ai_prep_search` returns **two** versions of every chunk:

| Column | Use | Why |
|---|---|---|
| `chunk_to_embed` | **The index embeds this** | Enriched with document title, section headers and page — so a chunk saying *"this takes 30 to 60 days"* still carries the context of *what* takes 30–60 days |
| `content` (`chunk_to_retrieve`) | **The LLM reads this** | The clean original text, without the injected context scaffolding |

Measured on these documents, `chunk_to_embed` runs about **30% longer** than `chunk_to_retrieve`. That difference is the context you embed but never show. Getting the two backwards is the classic mistake: embedding the bare text loses the context that makes retrieval work.

## Getting Started

Open the interactive guide: **[00_Instructions.py](./00_Instructions.py)** — a Databricks notebook with 37 cells (16 markdown, 9 SQL, 12 Python) that you execute inline as you read through each step.

## Project Contents

| File | Description |
|------|-------------|
| `00_Instructions.py` | Interactive step-by-step notebook guide (run cells inline) |
| `README.md` | This overview file |

## Steps Covered

1. **Understand RAG and Vector Search** — the parse → chunk → embed → index → retrieve pipeline
2. **Confirm the Source Files** — verify the 31 PDFs are in the UC volume
3. **Inspect the Parser Output** — look at the `VARIANT` shape before writing extraction against it
4. **Parse the PDFs to Text** — `ai_parse_document` into `article_parsed`, flattened to `article_pages`
5. **Chunk the Text into a Silver Table** — semantic chunking with `ai_prep_search`, with a fixed-window fallback
6. **Enable Change Data Feed** — required for a Delta Sync index; the most common failure point
7. **Create the Vector Search Endpoint** — one `wavepoint-vs` endpoint, STANDARD type
8. **Create the Delta Sync Index** — managed embeddings, PK `chunk_id`, embedding source `chunk_to_embed`
9. **Wait for ONLINE and Verify** — confirm the indexed row count matches the chunk table
10. **Query the Index** — three test questions, top-5 hits with scores and `doc_uri`
11. **Test in the AI Playground** — attach the index as a tool, including one question the documents *cannot* answer
12. **Record Findings, Commit, and Tear Down** — capture a retrieval failure, then delete the endpoint

## Chunking Strategy

Step 5 probes the workspace and picks a path automatically:

| | **Semantic** — `ai_prep_search` | **Fixed window** — fallback |
|---|---|---|
| Splits at | Section and topic boundaries | Wherever the character count runs out |
| Result | One coherent idea per chunk | Ideas cut mid-sentence, patched with overlap |
| Context enrichment | Yes — title, headers, page | None |
| Typical size | ~2,600–4,400 characters | 1,000 characters, 150 overlap |
| Requires | DBR 18.2+ / serverless env v3+ | Any runtime |

Both paths write an identical schema, so Steps 6–12 are unchanged either way. `ai_prep_search` is **verified available** on this workspace (DBSQL `2026.20`).

## Data Sources

31 de-branded dental practice-management PDFs in [`doc/articles/`](../doc/articles/), covering four themes:

| Theme | Examples |
|---|---|
| **A/R and collections** | `AR Aging Analysis for Dental Practices`, `Dental AR Reconciliation Tools` |
| **Payment / EOB posting** | `Dental EOB Posting Guide`, `Dental Payment Posting in Open Dental`, `Post EOBs in Eaglesoft` |
| **Claims, coding, coverage** | `Complete CDT Codes Guide`, `ADA Dental Claim Form Guide`, `HMO vs. PPO Insurance` |
| **Practice management / vendors** | `Top Dental Practice Management Software 2026`, `6 Best Dental Billing Software` |

> **Read the sources critically.** These are vendor and agency **marketing articles**, not standards documents. They are genuinely useful on workflow and benchmarks, but several are selling something. When you evaluate an answer, note whether the retrieved chunk describes **industry practice** or **pitches a product** — that distinction decides what you would trust this index to answer in production.

> Filenames contain spaces, parentheses, and underscores standing in for colons. **Do not rename them** — `doc_uri` is what your citations show.

## 💰 Cost

**A Vector Search endpoint bills for as long as it exists, not just while you query it.**

- Create exactly one endpoint (`wavepoint-vs`) — the notebook reuses an existing one rather than making a second
- Pausing for more than a day? Ask before leaving it up
- Step 12 has the teardown. Deleting the index and endpoint does **not** touch `article_chunks`, so you can rebuild at any time

Parsing also costs one LLM inference per document. `article_parsed` exists so you pay that once.

## Naming Convention

⚠️ Always use underscores (`_`) in catalog, schema, and table names. Avoid hyphens (`-`) which cause SQL parsing errors.

✅ Good: `project_3_silver`, `article_chunks`
❌ Bad: `project-3-silver`, `article-chunks`

The one exception is the **Vector Search endpoint name** (`wavepoint-vs`). An endpoint is not a SQL identifier, so a hyphen is safe there.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ai_parse_document` not found | Needs **DBR 17.3+** — switch to serverless or a newer cluster |
| `ai_prep_search` not found | Needs **DBR 18.2+ / serverless env v3+**. Step 5's probe falls back automatically |
| Index creation fails mentioning change data feed | Step 6 — CDF is not enabled on `article_chunks` |
| `explode()` fails on a VARIANT | Cast first: `explode(variant_get(x, '$.path', 'ARRAY<VARIANT>'))` |
| `page` is always NULL | A chunk can span pages — use `$.pages[0].page_id`, not `$.page` |
| Index ONLINE but row counts differ | Trigger a sync, wait, re-check before trusting results |
| Retrieval worse after switching to semantic | Check you embedded `chunk_to_embed`, not `content` |
| Vector Search unavailable in region | **Stop and flag it** — it changes the plan for the next project |

## Additional Resources

- [Create a Vector Search index](https://docs.databricks.com/aws/en/ai-search/create-ai-search/)
- [Vector Search overview](https://docs.databricks.com/aws/en/generative-ai/vector-search)
- [`ai_parse_document`](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)
- [`ai_prep_search`](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_prep_search)
- [Delta Change Data Feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)
- [AI Playground](https://docs.databricks.com/aws/en/large-language-models/ai-playground)
- [Unity Catalog Volumes](https://docs.databricks.com/aws/en/catalog/volumes.html)

## Questions?

Ask **Databricks Assistant (Genie Code)** for help at any step!
