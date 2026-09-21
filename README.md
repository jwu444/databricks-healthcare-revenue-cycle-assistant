# Healthcare Revenue Cycle Assistant — Databricks

An end-to-end AI assistant for a **multi-location dental practice**, built on Databricks in six hands-on projects.

A dental office manager's day is **appointments, billing, and financials**. The answers they need live in two very different places, and the whole architecture follows from that split.

| They ask | Kind of question | Answered by |
|---|---|---|
| *"What's our denial rate by payer?"* | **Data** — counts, sums, trends | Genie agent (project 3) |
| *"Which five offices have the most A/R over 90 days?"* | **Data** | Genie agent |
| *"How many claims in the 2024-25 benefit year?"* | **Data** | Genie agent |
| *"How do I post an EOB in Open Dental?"* | **Document** — procedure | Vector index (project 2) |
| *"What A/R aging buckets should we track?"* | **Document** — best practice | Vector index |
| *"What does denial code *Frequency Limit Exceeded* mean?"* | **Document** | Vector index |

**Structured operations data** — 20 tables of appointments, claims, invoices, payments, patients and benefit years — answers *what happened in our practice*. **Unstructured documents** — 31 dental billing and practice-management articles — answer *how the work is done and what good looks like*. Neither can answer the other's questions.

```
                    Dental Office Operations Assistant
                                   │
                  ┌────────────────┴────────────────┐
                  │  chat UI  (project 5)           │
                  │  A: Databricks App              │
                  │  B: React + FastAPI + Postgres  │
                  └────────────────┬────────────────┘
                                   ▼
                        supervisor routes it
                             (project 4)
               ┌───────────────────┴───────────────────┐
               ▼                                       ▼
      "what do our numbers say?"            "how is this done?"
      Genie agent over Delta tables          RAG over 31 PDFs
      appointments · claims · invoices        billing guides · A/R
      payments · benefit years                EOB posting · coding
         (projects 1 + 3)                        (project 2)
```

### The business problems underneath

Real ones, not toy ones: claim denials that eat margin, A/R that ages past collectible, contractual write-offs nobody tracks, no-shows that waste chair time, and **benefit years that reset on September 1 rather than January 1** — which quietly breaks every year-over-year number if you don't know it.

---

## The Six Projects

| # | Project | Builds | Status |
|---|---|---|---|
| **0** | [Setup](./0_Setup/) | Claude Code ↔ Databricks connection, verified 7 ways | ✅ Complete |
| **1** | [Medallion](./1_Medallion/) | Bronze → silver → gold, AI/BI dashboard, CI/CD | ✅ Complete |
| **2** | [RAG](./2_RAG/) | Vector index over 31 dental PDFs | ✅ Complete |
| **3** | [Genie](./3_Genie/) | Natural-language → SQL agent over the Delta tables | ✅ Complete |
| **4** | [Supervisor](./4_Supervisor/) | Multi-agent routing between 2 and 3 | 📋 **To do** — [#18](https://github.com/wavepoint-build/ai-engineering-workshop/issues/18) |
| **5** | [Chat app](./5_Chat_app/) | Chat UI over the supervisor — in-platform, then full-stack | 📋 **To do** — [#19](https://github.com/wavepoint-build/ai-engineering-workshop/issues/19) |

Each project is a numbered folder. Projects 1–3 hold a `00_Instructions.py` notebook and a `README.md`. **Project 0 is README-only** — its steps configure your laptop, and a notebook that lives in the workspace can't tell you how to get access to the workspace. Its verification harness ships as a runnable script instead. **Projects 4 and 5 are scaffolded but not started** — their folders hold a placeholder `README.md` and the link to the issue that specs them.

### 0 · Setup — connect Claude Code to Databricks

Installs the CLI and Python SDK, authenticates, installs Databricks' own Claude Code skills, then **proves the connection works**:

```bash
python 0_Setup/verify_connection.py
```

Seven independent capability checks — authentication, Unity Catalog, warehouse, SQL execution, serving endpoints, an embedding model, the Vector Search API — each labelled with the project that needs it, plus a real 1024-dim embedding call. Exits non-zero on failure, so it works in CI.

The one rule: **the token never passes through a Claude Code session.** `databricks configure --token` runs in your own terminal, because a session's output is written to a transcript on disk. Running it through Claude Code fails with `host must be set in non-interactive mode` — that failure is the safety net working, not a bug to route around.

### 1 · Medallion — the structured data

20 CSV tables → **bronze** (raw Delta) → **silver** (cleaned, typed, commented) → **gold** (8 aggregates), then an AI/BI dashboard with 36 datasets and CI/CD through Declarative Automation Bundles. Data is synthetic (seed 42), 50,760 rows, no PHI.

### 2 · RAG — the unstructured documents

31 dental practice-management PDFs → `ai_parse_document` → **`ai_prep_search` semantic chunking** → 104 chunks → Delta Sync vector index with managed embeddings.

Two things worth carrying forward:

- **Embed `chunk_to_embed`, return `content`.** `ai_prep_search` produces two versions of each chunk: one enriched with title/headers/page (measured ~30% longer) for embedding, one clean for the LLM to read. Swapping them silently degrades retrieval.
- **Change Data Feed is mandatory.** A Delta Sync index will not build without `delta.enableChangeDataFeed = true` on the source table, and the failure surfaces far from the cause.

Retrieval was verified: all four answerable test questions returned the correct source document (scores 0.70–0.76), and the deliberately unanswerable *"what is our largest outstanding invoice?"* scored **0.54** — a visible cliff that says *this is a data question, not a document question*.

### 3 · Genie — natural language over the tables

A `Dental Billing Analyst` agent over 10 silver tables, answering in plain English **with the SQL shown**.

**8 of 8 test questions passed on the first run**, including both traps. The lesson the project is built around: **Genie accuracy is a metadata problem, not a model problem.** A better model writes better SQL *given the same understanding of the schema* — it cannot guess that a benefit year starts in September, or that `denial_reason_code` stores the literal string `'N/A'` rather than NULL.

Silver/gold rather than bronze, on evidence: **0 of 20 bronze tables carry a comment**, versus 22 of 24 silver and 8 of 8 gold.

### 4 · [Supervisor](./4_Supervisor/) — *to do* ([#18](https://github.com/wavepoint-build/ai-engineering-workshop/issues/18))

Put a supervisor in front of both agents so one assistant handles the office manager's whole day. The routing problem is already characterised by projects 2 and 3: each declined the other's question correctly and independently. Project 3's Genie agent id — `01f1a99230b81b2eb2a86a65b7d1d3a9` — is recorded for attachment.

### 5 · [Chat app](./5_Chat_app/) — *to do* ([#19](https://github.com/wavepoint-build/ai-engineering-workshop/issues/19))

A chat UI in front of the supervisor, so the office manager talks to **one** assistant rather than choosing between a Genie agent and a vector index. Built twice, on both sides of the platform boundary:

- **Part A — Databricks App**, in-platform. AppKit (Node/TypeScript/React) or Python (FastAPI/Streamlit); auth and hosting handled by the platform
- **Part B — full-stack web app**, outside Databricks: **React** front end, **FastAPI** back end, **Postgres for application state**, reaching the supervisor through [`databricks-ai-bridge`](https://github.com/databricks/databricks-ai-bridge)

**The supervisor's serving endpoint is the seam.** Both apps call that endpoint and nothing else — no direct Genie or vector-index calls from app code. Done right, Part B is a change of transport and auth, not a rewrite.

Two things the split is designed to teach. **Postgres holds *application* state** — conversations, messages, users, which agent answered and what it cited — while the dental data stays in Unity Catalog; conflating the two is the mistake to avoid. And **provenance has to survive the UI**: SQL shown for data answers, source document for document answers, and *"which patients will no-show next month?"* declined rather than answered, exactly as projects 2 and 3 already decline it on their own.

---

## Repository Layout

```
0_Setup/               Claude Code <-> Databricks connection (README + verify script)
1_Medallion/           Medallion: bronze -> silver -> gold, dashboard, CI/CD
2_RAG/                 RAG: PDFs -> semantic chunks -> vector index
3_Genie/               Genie: natural language -> SQL agent
4_Supervisor/          Multi-agent supervisor routing 2 and 3   (placeholder)
5_Chat_app/            Chat UI over the supervisor              (placeholder)
dashboards/            AI/BI dashboard (dental_billing.lvdash.json)
resources/             DABs resource definitions
doc/
  articles/            31 de-branded dental PDFs (project 2 source)
  data/                20 CSV tables + data dictionary
  dental_data_model_design.md
databricks.yml         Bundle config (dev / prod targets)
```

## Two Ways to Work

There are two viable development workflows for this repo. They are not equivalent, and the trade-off is essentially **where the context lives**.

### Option A — local coding agent + AI bridge

Run a coding agent on your machine (**Claude Code, GitHub Copilot, Codex**), connect it to the Databricks workspace through the CLI/SDK and [`databricks-ai-bridge`](https://github.com/databricks/databricks-ai-bridge), and keep a local git repo synced with the remote.

**Pros**
- Use the agent you already know, with your existing editor and shell
- Larger token limits you may already be paying for
- Full local tooling — run scripts, diff, test, and commit in one place

**Cons**
- You must **feed the agent its Databricks context** via `AGENTS.md` / `CLAUDE.md`; it does not know your catalog, your conventions, or your gotchas by default
- The agent often has to **probe the workspace** to extract context before it can act

> This repo was built with Option A, and both cons are visible in it. [`CLAUDE.md`](./CLAUDE.md) exists precisely because the agent needed the catalog layout, the naming rules and the hard-won gotchas written down. And a great deal of session time went into probing — `SELECT DISTINCT` over 15 categorical columns, `schema_of_variant()` on the parser output, reading the CLI's own bundle schema — because the documentation and the installed reality did not always agree.

### Option B — Databricks Genie coding agent, in-workspace

Link this GitHub repo in **Databricks Repos** and develop directly in the workspace using the Databricks Genie coding agent web UI.

**Pros**
- **Direct access to workspace context** — it can see what you are working on, which removes most of Option A's probing
- **Current Databricks knowledge loaded and ready**, rather than reconstructed from docs of uncertain vintage
- Databricks continues to train and tune this harness, so it should keep getting better and more efficient

**Cons**
- The web UI has **token limits**, and **fewer tools and features** than a full local agent — even though popular coding LLMs power it underneath

### Which to pick

**Databricks-specific work leans toward B; repo-wide work leans toward A.** The context Option B gets for free is exactly what Option A spends time reconstructing. But anything spanning many files, local scripts, or git history is still easier with a full local agent.

They are not exclusive — the repo is the shared surface. Committing from either side keeps both in sync.


## Conventions

**Naming** — underscores in catalog, schema, and table names. Hyphens cause SQL parse errors and need backtick escaping. The one exception is the Vector Search endpoint (`wavepoint-vs`), which is not a SQL identifier.

**Data** — fully synthetic, deterministic (seed 42). No PHI, no real patients, no real practices. The 31 PDFs are de-branded: images, logos, company name and copyright removed.

**Notebooks** — Databricks source format (`# Databricks notebook source`), one `DBTITLE` per cell, markdown instruction cells interleaved with runnable SQL/Python.

## Future Enhancements

- **[Genie semantic caching](https://github.com/databricks-industry-solutions/semantic-caching)** — cache answers to semantically equivalent questions so repeated asks skip the warehouse round trip. An office manager's day is full of near-duplicate questions, and today every one of them re-runs SQL.
- **[Business context layer with a knowledge graph](https://docs.databricks.com/aws/en/genie/genie-ontology)** — a Genie ontology over the tables. This is the natural next step from project 3's central lesson: accuracy is a metadata problem, not a model problem. Comments and value inventories got the agent to 8 of 8; an explicit ontology encodes the relationships that comments can only imply.

## Useful Databricks Repositories

- **[databricks-solutions](https://github.com/databricks-solutions)** — solution accelerators and reference implementations
- **[databricks-industry-solutions](https://github.com/databricks-industry-solutions)** — industry-specific accelerators, including the semantic-caching project above
