# Project 5 · Chat App — UI over the Supervisor

> 📋 **Status: not started.** This README is a placeholder. The spec lives in
> [wavepoint-build/ai-engineering-workshop#19](https://github.com/wavepoint-build/ai-engineering-workshop/issues/19) —
> read the issue before starting.

## Overview

A chat UI in front of project 4's supervisor, so the office manager talks to **one** assistant rather than choosing between a Genie agent and a vector index.

Built twice, on both sides of the platform boundary — the point is the comparison, not the second app.

```
        Part A                              Part B
   Databricks App                   React + FastAPI + Postgres
   (in-platform)                        (outside Databricks)
        │                                       │
        └───────────────────┬───────────────────┘
                            ▼
              supervisor serving endpoint   ← the seam
                       (project 4)
```

## What this project will build

**Part A — Databricks App**, in-platform. AppKit (Node/TypeScript/React) or Python (FastAPI/Streamlit); auth and hosting handled by the platform.

**Part B — full-stack web app**, outside Databricks: React front end, FastAPI back end, **Postgres for application state**, reaching the supervisor through [`databricks-ai-bridge`](https://github.com/databricks/databricks-ai-bridge).

Plus **bundle resources** under `resources/`, per the repo rule that every project lands in a bundle.

## The two things this split is designed to teach

**The serving endpoint is the seam.** Both apps call the supervisor endpoint and nothing else — no direct Genie or vector-index calls from app code. Done right, Part B is a change of transport and auth, not a rewrite.

**Postgres holds *application* state** — conversations, messages, users, which agent answered and what it cited — while the dental data stays in Unity Catalog. Conflating the two is the mistake to avoid.

And one requirement that carries through both: **provenance has to survive the UI.** SQL shown for data answers, source document for document answers, and *"which patients will no-show next month?"* declined rather than answered — exactly as projects 2 and 3 already decline it on their own.

## Prerequisites

| Need | From | Note |
|---|---|---|
| Supervisor serving endpoint | [Project 4](../4_Supervisor/) | **Not built yet — blocks this project** |
| Genie agent + vector index | Projects [3](../3_Genie/) and [2](../2_RAG/) | Reached only through the supervisor |

## Additional Resources

- [Databricks Apps](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
- [Lakebase (Postgres on Databricks)](https://docs.databricks.com/aws/en/oltp/)
- [`databricks-ai-bridge`](https://github.com/databricks/databricks-ai-bridge)

## Questions?

Ask **Databricks Assistant (Genie Code)** for help at any step!
