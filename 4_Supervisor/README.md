# Project 4 · Supervisor — Multi-Agent Routing over Genie and RAG

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
     Genie agent.                          Vector index  (project 2)
     
```

## What this project will build

- A **Multi-Agent Supervisor** (Agent Bricks) that routes between the Genie agent and a Knowledge Assistant over the project-2 index
- A **serving endpoint** for the supervisor — this is the seam project 5's chat apps call, and the only thing they call
- **Bundle resources** under `resources/`, per the repo rule that every project lands in a bundle
- An **evaluation pass** over routing: data questions, document questions, ambiguous ones, and questions neither agent should answer

## Prerequisites

| Need | From | Note |
|---|---|---|
| Genie agent | [3_Genie](../3_Genie/) | Live |
| Vector index | [2_RAG](../2_RAG/) | **Torn down** — rebuild via project 2 Steps 7–9 (~30 min) |
| Silver tables | [1_Medallion](../1_Medallion/) | Live |

## Additional Resources

- [Multi-agent supervisor](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/multi-agent-supervisor)
- [Knowledge Assistant](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/knowledge-assistant)
- [Mosaic AI Agent Framework](https://docs.databricks.com/aws/en/generative-ai/agent-framework/build-genai-apps)

## Questions?

Ask **Databricks Assistant (Genie Code)** for help at any step!
