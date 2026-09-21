# Project 4 · Supervisor — Multi-Agent Routing over Genie and RAG

> 📋 **Status: not started.** This README is a placeholder. The spec lives in
> [wavepoint-build/ai-engineering-workshop#18](https://github.com/wavepoint-build/ai-engineering-workshop/issues/18) —
> read the issue before starting.

## Overview

Put a **supervisor agent** in front of the two agents built so far, so the office manager talks to one assistant instead of choosing a tool.

Project 3's Genie agent answers *"what is our denial rate by payer?"* Project 2's vector index answers *"what does denial reason code X mean?"* Neither can answer the other's question — and both already decline correctly and independently, which is exactly the signal a supervisor routes on.

```
                        office manager's question
                                   │
                                   ▼
                        supervisor  (this project)
                                   │
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
     "what do our numbers say?"            "how is this done?"
     Genie agent  (project 3)              Vector index  (project 2)
     01f1a99230b81b2eb2a86a65b7d1d3a9      article_chunks_index
```

## What this project will build

- A **Multi-Agent Supervisor** (Agent Bricks) that routes between the Genie agent and a Knowledge Assistant over the project-2 index
- A **serving endpoint** for the supervisor — this is the seam project 5's chat apps call, and the only thing they call
- **Bundle resources** under `resources/`, per the repo rule that every project lands in a bundle
- An **evaluation pass** over routing: data questions, document questions, ambiguous ones, and questions neither agent should answer

## Prerequisites

| Need | From | Note |
|---|---|---|
| Genie agent `01f1a99230b81b2eb2a86a65b7d1d3a9` | [Project 3](../3_Genie/) | Live |
| Vector index `article_chunks_index` | [Project 2](../2_RAG/) | **Torn down** — rebuild via project 2 Steps 7–9 (~30 min) |
| Silver tables | [Project 1](../1_Medallion/) | Live |

⚠️ Rebuilding the project-2 index stands up a **Vector Search endpoint, which bills continuously until deleted.** See the cost section in the [root README](../README.md).

## Design questions to settle first

- **Routing on decline vs. routing up front** — does the supervisor classify the question, or try one agent and fall back?
- **What provenance survives the hop?** A data answer should carry its SQL, a document answer its source document. The supervisor must not flatten either.
- **What does it do with a question neither agent can answer?** Projects 2 and 3 both decline honestly; the supervisor has to preserve that rather than synthesize an answer.

## Additional Resources

- [Multi-agent supervisor](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/multi-agent-supervisor)
- [Knowledge Assistant](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/knowledge-assistant)
- [Mosaic AI Agent Framework](https://docs.databricks.com/aws/en/generative-ai/agent-framework/build-genai-apps)

## Questions?

Ask **Databricks Assistant (Genie Code)** for help at any step!
