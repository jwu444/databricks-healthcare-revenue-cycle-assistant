# Hands-On Project 0: Connect Claude Code to Databricks

Projects 1–4 all assume a working connection between **your own Databricks workspace** and **Claude Code**. This project builds it, and — more importantly — **proves it works** before anything depends on it.

Every later project fails confusingly if this is half-configured. A missing `~/.databrickscfg` surfaces as `cannot configure default credentials` three steps into a notebook, not here where it would be obvious.

> **Why this project has no notebook.** Projects 1–4 ship a `00_Instructions.py` that runs *inside* the Databricks workspace. That would be circular here: a notebook lives in the workspace, and this project is what gets you access to the workspace. The CLI install, the SDK install, and `databricks configure --token` all run on your own machine — and the auth step specifically **must not** run through Claude Code. So everything lives in this README, with the verification harness as a script you can run before you have workspace access at all.

## The Use Case We're Building Toward

Everything in this repo builds one thing: **an AI operations assistant for a multi-location dental practice.**

A dental office manager's day is **appointments, billing, and financials** — and the answers live in two very different places:

| They ask | Kind of question | Answered by |
|---|---|---|
| *"What's our denial rate by payer?"* | **Data** — counts, sums, trends | Project 3 · Genie agent |
| *"Which five offices have the most A/R over 90 days?"* | **Data** | Project 3 |
| *"How many claims in the 2024-25 benefit year?"* | **Data** | Project 3 |
| *"How do I post an EOB in Open Dental?"* | **Document** — procedure | Project 2 · vector index |
| *"What A/R aging buckets should we track?"* | **Document** — best practice | Project 2 |
| *"What does denial code *Frequency Limit Exceeded* mean?"* | **Document** | Project 2 |

**Structured operations data** — 20 tables of appointments, claims, invoices, payments, patients and benefit years — answers *what happened in our practice*. **Unstructured documents** — 31 dental billing and practice-management articles — answer *how the work is done and what good looks like*.

The business problems underneath are real: claim denials that eat margin, A/R that ages past collectible, contractual write-offs nobody tracks, no-shows that waste chair time, and **benefit years that reset on September 1** rather than January 1 — which quietly breaks every year-over-year number if you don't know it.

This project is the plumbing that makes all of it reachable from Claude Code.

---

## Prerequisites

- A Databricks workspace URL, e.g. `https://dbc-XXXXXXXX-XXXX.cloud.databricks.com`
- A personal access token (PAT) for that workspace
- Homebrew (macOS). The CLI also ships as a direct binary for other platforms

The workspace **URL and ID are not secret** and are fine to share in conversation. **The PAT is** — see Step 3.

---

## Step 1 — Install the Databricks CLI

In your own terminal:

```bash
brew tap databricks/tap
brew install databricks
```

### 🪤 Trap: untrusted tap

Recent Homebrew refuses to load a formula from a newly-tapped third-party repo the first time:

```
Error: Refusing to load formula databricks/tap/databricks from untrusted tap
```

Fix:

```bash
brew trust databricks/tap
brew install databricks
```

Not on macOS/Homebrew? See the [CLI installation docs](https://docs.databricks.com/aws/en/dev-tools/cli/install).

**Verify:**

```bash
databricks --version    # need v0.292.0+; v1.14.1 was used to write this
which databricks        # confirms it is on PATH
```

---

## Step 2 — Install the Python SDK

The CLI and the SDK are **separate installs**. You need both: the CLI for exploration and bundle deploys, the SDK for anything programmatic — projects 2 and 3 both use it to create a vector index and query Genie.

```bash
poetry add databricks-sdk          # project dependency
# or
pip install --user databricks-sdk  # pure exploration
```

Inside a Databricks notebook the SDK is already present — no install needed there.

---

## Step 3 — Authenticate

# 🔐 Run this in your own terminal. Never through Claude Code.

```bash
databricks configure --token
```

It prompts for your workspace host, then the token (**masked**). This writes `~/.databrickscfg`, which lives outside any git repo.

### Why this one step is off-limits to the assistant

**Do not run this via Claude Code's `!` prefix, and do not ask the assistant to run it for you.** Both execute inside the session whose output is written to the conversation transcript **on disk**. A secret that reaches a transcript is a secret you have to rotate.

A masked interactive prompt in your own terminal is the only path where the token never passes through Claude Code at all.

### 🪤 The failure that is actually a safety net

Run it through Claude Code anyway and it fails:

```
Error: host must be set in non-interactive mode
```

There's no TTY for the masked prompt, so `configure --token` falls back to reading the host from `--host`/`DATABRICKS_HOST` and the token from stdin — neither is set.

**That error is the safety net working, not a bug to work around.** If you're tempted to "fix" it by passing `--host` and piping the token in, stop: that's exactly the path that puts the secret in the transcript.

### For application code

An app reads `DATABRICKS_HOST` / `DATABRICKS_TOKEN` from its own **gitignored** `.env`, the same way an `ANTHROPIC_API_KEY` would be. Verify through the application's code path too — a bare `WorkspaceClient()` and an app's `Settings` object can silently diverge if only one is configured.

---

## Step 4 — Install Databricks' Claude Code Skills

```bash
databricks aitools install --agents claude-code
databricks aitools list      # full set; most are opt-in
```

This installs the official `databricks-agent-skills` plugin — the skills Claude Code loads when a task touches Databricks. They're what let the assistant reach for `databricks-vector-search` in project 2 and `databricks-genie-agents` in project 3 instead of guessing at APIs.

### 🪤 Restart your Claude Code session

**Newly installed skills are not picked up mid-session.** Install, then start a fresh session. Skipping this is the most common reason someone follows the runbook correctly and still sees no Databricks skills.

### Why this matters later

These skills carry current API shapes, but they aren't infallible. Project 2 hit a real case: the documented `create_index` example passes `delta_sync_index_spec` as a plain dict, but `databricks-sdk 0.135.0` calls `.as_dict()` on it and raises `AttributeError: 'dict' object has no attribute 'as_dict'`. Typed objects (`DeltaSyncVectorIndexSpecRequest`) are required. Skills narrow that gap; they don't close it — **always verify against your installed version.**

---

## Step 5 — Verify Both Ways

Two **independent** checks, because later projects use both paths and they can be configured differently.

**CLI:**

```bash
databricks auth profiles     # lists profiles and whether each is valid
databricks current-user me   # who the CLI thinks you are
```

**SDK:**

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
print(w.current_user.me().user_name)
print(w.config.host)
```

Both must report the **same user**. If they disagree, you have two credential sources and one is stale.

> **On profiles:** if you have more than one, always pass `--profile <name>` explicitly rather than relying on the default. Silently operating against the wrong workspace is a bad afternoon.

---

## Step 6 — Run the Verification Harness

`current-user me` proves your credentials are valid. It does **not** prove you can run a query, reach a model, or read Unity Catalog — and those are what projects 1–4 actually need.

```bash
python 0_Setup/verify_connection.py
python 0_Setup/verify_connection.py --profile DEFAULT     # explicit profile
python 0_Setup/verify_connection.py --skip-end-to-end     # no model call
```

Seven independent checks, each labelled with the project that needs it, so a failure names the **broken capability** rather than just "something is wrong". Exit code is 0 on success, 1 otherwise, so it works in CI.

| Check | Proves | Needed by |
|---|---|---|
| Authentication | Credentials resolve | everything |
| Unity Catalog read | You can list catalogs | 1, 2, 3 |
| SQL warehouse | Compute exists and is reachable | 1, 2, 3 |
| SQL execution | A query actually runs | 1, 2, 3 |
| Serving endpoints | Foundation models available | 2, 4 |
| Embedding model | Vector Search can embed | 2 |
| Vector Search API | The service is enabled in your region | 2 |

Then an **end-to-end test**: a real call to `databricks-gte-large-en` returning a real 1024-dimension vector — the same path project 2's index depends on. Cheap: one short embedding call.

### Expected output

Captured from a live run while writing this:

```
     CHECK               NEEDED BY  DETAIL
--------------------------------------------------------------------------------------------
PASS  Authentication      all        binwu247@gmail.com
PASS  Unity Catalog read  1,2,3      4 catalog(s): workspace, system, samples, wavepoint_workshop
PASS  SQL warehouse       1,2,3      Serverless Starter Warehouse [State.STOPPING]
PASS  SQL execution       1,2,3      query returned 1 on Serverless Starter Warehouse
PASS  Serving endpoints   2,4        11 endpoint(s)
PASS  Embedding model     2          databricks-gte-large-en, databricks-bge-large-en, databricks-qwen3-embedding-0-6b
PASS  Vector Search API   2          API reachable, 0 endpoint(s) -- none is normal and costs nothing

All capability checks passed.

End-to-end test via databricks-gte-large-en ...
  dimensions : 1024
  first 5    : [-0.3882, -0.6694, 0.0571, 0.8057, 0.3406]

Connection is ready for projects 1-4.
```

**Vector Search reporting 0 endpoints is a PASS** — the API answering is what's being tested. An endpoint would bill continuously; see the [root README](../README.md).

A failure here is **useful**. It's far cheaper to find now than three steps into project 2.

---

## Step 7 — Inventory Your Workspace

**Free-tier capability varies by workspace and region.** Check early — it shapes what's actually buildable.

```bash
databricks warehouses list -o json
databricks serving-endpoints list -o json
databricks clusters list-node-types
```

### What this workspace had — a snapshot, not a promise

| Resource | Found |
|---|---|
| SQL warehouses | 1 — Serverless Starter, PRO, 2X-Small, auto-stops when idle |
| Serving endpoints | **11** pay-per-token Foundation Model APIs |
| Embedding models | `databricks-gte-large-en`, `databricks-bge-large-en`, `databricks-qwen3-embedding-0-6b` — all 1024-dim |
| Chat models | Llama 4 Maverick, Llama 3.3 70B, Qwen3, GPT-OSS 120B/20B, Gemma 3 |
| Interactive clusters | 0 — everything runs serverless |

Three consequences worth knowing before project 1:

1. **`databricks-gte-large-en` exists**, which is what project 2's vector index embeds with. No provisioning needed.
2. **No interactive clusters**, so everything runs serverless. This matters: `ai_parse_document` needs DBR 17.3+ and `ai_prep_search` needs 18.2+, and serverless is current enough while an old pinned cluster is not.
3. **The free tier has a daily compute limit.** Exhaust it and *every* query fails with `you have hit your free daily limit` until it resets. Project 2's PDF parsing is 31 LLM inferences in one go.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Refusing to load formula ... from untrusted tap` | New Homebrew security check | `brew trust databricks/tap` |
| `host must be set in non-interactive mode` | Ran `configure --token` **through Claude Code** | Run it in your own terminal — this error is the safety net working |
| `cannot configure default credentials` | No `~/.databrickscfg`, or wrong profile | Re-run Step 3; pass `--profile <name>` |
| CLI and SDK report **different users** | Two credential sources, one stale | Check `~/.databrickscfg` **and** `DATABRICKS_HOST`/`DATABRICKS_TOKEN` in the environment |
| No Databricks skills in Claude Code | Installed mid-session | **Restart the session** — Step 4 |
| `you have hit your free daily limit` | Free-tier compute exhausted | Wait for reset, or raise the limit. Not a config problem |
| `PERMISSION_DENIED` on a catalog | Token lacks Unity Catalog grants | Check workspace/UC permissions for your user |
| SQL execution times out | Serverless warehouse cold-starting | Re-run — first query after idle takes ~1 min |
| `'dict' object has no attribute 'as_dict'` | SDK wants typed objects, not dicts | Use the typed request classes; see project 2 Step 8 |

Hit something not listed here? That's worth reporting on the setup issue — a genuine gap gets the runbook fixed rather than letting the next person hit the same wall.

---

## Project Contents

| File | Description |
|------|-------------|
| `README.md` | This guide — every setup step and the verification procedure |
| `verify_connection.py` | Runnable 7-check harness plus the end-to-end embedding call |

## What You Built

```
Databricks CLI  ─┐
Python SDK      ─┼─→ ~/.databrickscfg ─→ your workspace
Claude Code     ─┘   (token never in a transcript)
    + databricks-agent-skills
```

Verified: authentication, Unity Catalog, SQL execution, serving endpoints, an embedding model, the Vector Search API, and one real end-to-end model call.

## On to the Projects

| Project | Builds | Needs from here |
|---|---|---|
| **[1](../1_Medallion/)** | Medallion architecture, dashboard, CI/CD | SQL warehouse, Unity Catalog |
| **[2](../2_RAG/)** | RAG vector index over 31 PDFs | Embedding model, Vector Search API |
| **[3](../3_Genie/)** | Genie agent over the Delta tables | SQL warehouse, Unity Catalog |
| **4** | Supervisor routing between 2 and 3 | Serving endpoints |

## Additional Resources

- [CLI installation](https://docs.databricks.com/aws/en/dev-tools/cli/install)
- [CLI authentication](https://docs.databricks.com/aws/en/dev-tools/cli/authentication)
- [Python SDK](https://databricks-sdk-py.readthedocs.io/)
- [Foundation Model APIs](https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/)
- [Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/)
