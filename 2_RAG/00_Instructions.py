# Databricks notebook source
# DBTITLE 1,Title & Overview
# MAGIC %md
# MAGIC # Hands-On Project 2: Vector Search Index (RAG) over the Dental Business Documents
# MAGIC
# MAGIC ## Overview
# MAGIC This hands-on project builds a **retrieval index** over 31 dental practice-management PDFs so an LLM can answer
# MAGIC questions like *"How do you post an EOB in Open Dental?"* or *"What A/R aging buckets should a practice track?"*
# MAGIC — **with citations back to the source document**.
# MAGIC
# MAGIC In Project 1 you built the Medallion Architecture over **structured** CSV data. This project covers the other half
# MAGIC of a real lakehouse: **unstructured documents**. The same medallion thinking applies — the PDFs are bronze, the
# MAGIC parsed and chunked text is silver.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC - Understand the RAG pipeline: **parse → chunk → embed → index → retrieve**
# MAGIC - Parse PDFs to text with the built-in `ai_parse_document` SQL function
# MAGIC - Chunk semantically with `ai_prep_search`, and know why that beats fixed-size windows
# MAGIC - Understand the `chunk_to_embed` vs `chunk_to_retrieve` split
# MAGIC - Enable **Change Data Feed** on a Delta table (required for Delta Sync indexes)
# MAGIC - Create a Vector Search endpoint and a **Delta Sync index with managed embeddings**
# MAGIC - Query the index and read similarity scores critically
# MAGIC - Attach the index as a tool in the AI Playground and evaluate answer quality
# MAGIC - Recognise when retrieval **fails**, and when a retrieved chunk is vendor marketing rather than neutral practice
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC | Requirement | Detail |
# MAGIC |---|---|
# MAGIC | Project 1 complete | `wavepoint_workshop` catalog with `project_3_bronze` / `project_3_silver` schemas |
# MAGIC | Source documents | 31 PDFs already in `/Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles/` |
# MAGIC | Compute | **DBR 17.3+** (or serverless) — `ai_parse_document` requires it |
# MAGIC | Region | Vector Search must be available in your workspace region |
# MAGIC
# MAGIC ## ⚠️ Cost Warning — Read Before Step 6
# MAGIC
# MAGIC A Vector Search endpoint **bills while it exists, not just while you query it.**
# MAGIC
# MAGIC - Create **exactly one** endpoint (`wavepoint-vs`)
# MAGIC - If you are pausing for more than a day, **ask before leaving it up**
# MAGIC - Step 12 has the teardown commands — do not skip it when you are done
# MAGIC
# MAGIC ## Naming Convention (same rule as Project 1)
# MAGIC
# MAGIC ⚠️ **Use underscores (`_`) in catalog, schema, and table names.**
# MAGIC
# MAGIC ✅ **Good:** `project_3_silver`, `article_chunks`
# MAGIC ❌ **Bad:** `project-3-silver`, `article-chunks`
# MAGIC
# MAGIC The one exception is the **Vector Search endpoint name** (`wavepoint-vs`). An endpoint is not a SQL identifier,
# MAGIC so a hyphen is safe there.
# MAGIC
# MAGIC ## Table of Contents
# MAGIC
# MAGIC 1. Understand RAG and Vector Search
# MAGIC 2. Confirm the Source Files
# MAGIC 3. Inspect the Parser Output
# MAGIC 4. Parse the PDFs to Text
# MAGIC 5. Chunk the Text into a Silver Table — semantic (`ai_prep_search`) or fixed-window fallback
# MAGIC 6. Enable Change Data Feed ← **most common failure point**
# MAGIC 7. Create the Vector Search Endpoint
# MAGIC 8. Create the Delta Sync Index
# MAGIC 9. Wait for ONLINE and Verify
# MAGIC 10. Query the Index
# MAGIC 11. Test in the AI Playground
# MAGIC 12. Record Findings, Commit, and Tear Down

# COMMAND ----------

# DBTITLE 1,Step 1: Understand RAG and Vector Search
# MAGIC %md
# MAGIC ## Step 1: Understand RAG and Vector Search
# MAGIC
# MAGIC 📖 **[Create a Vector Search index](https://docs.databricks.com/aws/en/ai-search/create-ai-search/)**
# MAGIC
# MAGIC ### The Problem
# MAGIC
# MAGIC An LLM does not know anything about *your* documents. Asking a base model "how do I post an EOB in Open Dental?"
# MAGIC produces a plausible-sounding answer built from whatever it absorbed in training — with no way to check it.
# MAGIC
# MAGIC **RAG (Retrieval-Augmented Generation)** fixes this by retrieving the *actual relevant text* from your documents
# MAGIC first, then asking the LLM to answer **using only that text**. The answer becomes traceable to a source.
# MAGIC
# MAGIC ### The Pipeline
# MAGIC
# MAGIC ```
# MAGIC 31 PDFs in a UC Volume  (bronze — raw, unchanged)
# MAGIC     │
# MAGIC     ▼  ai_parse_document()
# MAGIC Text + page numbers per document
# MAGIC     │
# MAGIC     ▼  chunk: ai_prep_search (semantic) — or ~1000 chars / 150 overlap
# MAGIC article_chunks  (silver — parsed, cleaned, one row per chunk)
# MAGIC     │
# MAGIC     ▼  Change Data Feed enabled  ← the index cannot build without this
# MAGIC     ▼  Delta Sync index, managed embeddings (databricks-gte-large-en)
# MAGIC article_chunks_index  (each chunk becomes a 1024-dimension vector)
# MAGIC     │
# MAGIC     ▼  similarity search
# MAGIC Top-k relevant chunks  →  LLM  →  answer with citations
# MAGIC ```
# MAGIC
# MAGIC ### Why Chunking Matters
# MAGIC
# MAGIC A whole 12-page article is too big to embed usefully — one vector cannot represent twelve pages of distinct ideas,
# MAGIC and you would hand the LLM pages of irrelevant text. So documents are split into **chunks**, and each chunk gets
# MAGIC its own vector.
# MAGIC
# MAGIC **Where you split is the main quality knob.** There are two ways to decide:
# MAGIC
# MAGIC | | **Semantic** — `ai_prep_search` | **Fixed window** — every N characters |
# MAGIC |---|---|---|
# MAGIC | Splits at | Section and topic boundaries | Wherever the character count runs out |
# MAGIC | Result | One coherent idea per chunk | Ideas cut mid-sentence, patched with overlap |
# MAGIC | Bonus | Enriches chunks with title / headers / page | None |
# MAGIC | Needs | DBR 18.2+ / serverless env v3+ | Any runtime |
# MAGIC
# MAGIC **Semantic chunking is the better default** — a fixed window is really just a crude guess at "one idea per
# MAGIC chunk", and character overlap exists to soften the damage from cutting in the wrong place.
# MAGIC
# MAGIC Step 5 **probes your workspace** and takes the semantic path if it is available, falling back to 1000-character
# MAGIC windows with 150 characters of overlap if not. Either way the rest of the notebook is unchanged.
# MAGIC
# MAGIC ### Managed Embeddings
# MAGIC
# MAGIC An **embedding** turns text into a vector of numbers such that similar meanings land near each other. With a
# MAGIC **Delta Sync index using managed embeddings**, Databricks does all of this for you: it reads the source table,
# MAGIC calls the embedding model, stores the vectors, and keeps them in sync as the table changes. You never handle a
# MAGIC vector yourself — you write text to a Delta table and query with plain English.
# MAGIC
# MAGIC | Term | Meaning here |
# MAGIC |---|---|
# MAGIC | **Endpoint** | The compute that hosts indexes — `wavepoint-vs` |
# MAGIC | **Index** | The searchable vector structure — `article_chunks_index` |
# MAGIC | **Delta Sync** | Index auto-syncs from the source Delta table |
# MAGIC | **Managed embeddings** | Databricks computes the vectors with `databricks-gte-large-en` |
# MAGIC | **Primary key** | `chunk_id` — must be unique, this is what ties a hit back to its text |

# COMMAND ----------

# DBTITLE 1,Step 2: Confirm the Source Files
# MAGIC %md
# MAGIC ## Step 2: Confirm the Source Files
# MAGIC
# MAGIC The 31 PDFs were already copied into the volume by Project 1. **Do not re-upload them by hand.** If files are
# MAGIC missing, go back and finish the volume-loading step of Project 1.
# MAGIC
# MAGIC ### About the documents
# MAGIC
# MAGIC They cover four themes:
# MAGIC
# MAGIC | Theme | Examples |
# MAGIC |---|---|
# MAGIC | **A/R and collections** | `AR Aging Analysis for Dental Practices`, `Dental AR Reconciliation Tools` |
# MAGIC | **Payment / EOB posting** | `Dental EOB Posting Guide`, `Dental Payment Posting in Open Dental`, `Post EOBs in Eaglesoft` |
# MAGIC | **Claims, coding, coverage** | `Complete CDT Codes Guide`, `ADA Dental Claim Form Guide`, `HMO vs. PPO Insurance` |
# MAGIC | **Practice management / vendors** | `Top Dental Practice Management Software 2026`, `6 Best Dental Billing Software` |
# MAGIC
# MAGIC > 📌 **Read these sources critically.** They are vendor and agency **marketing articles**, not standards
# MAGIC > documents. They are genuinely useful on workflow and benchmarks, but several are selling something. When you
# MAGIC > evaluate an answer, note whether the retrieved chunk describes **industry practice** or **pitches a product**.
# MAGIC > That distinction decides what you would trust this index to answer in production.
# MAGIC
# MAGIC > ⚠️ **Filenames contain spaces, parentheses, and underscores standing in for colons.** Do not rename them.
# MAGIC > Handle the paths properly — `doc_uri` is what your citations will show the user.

# COMMAND ----------

# DBTITLE 1,List the Source PDFs
# MAGIC %sql
# MAGIC -- Expect 31 PDFs. If the count is short, finish Project 1's volume-loading step first.
# MAGIC LIST '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles/'

# COMMAND ----------

# DBTITLE 1,Count the Source PDFs
# MAGIC %sql
# MAGIC SELECT
# MAGIC   count(*)                                   AS pdf_count,
# MAGIC   round(sum(length) / 1024.0 / 1024.0, 1)    AS total_mb
# MAGIC FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles/',
# MAGIC   format => 'binaryFile'
# MAGIC )
# MAGIC WHERE lower(path) LIKE '%.pdf'

# COMMAND ----------

# DBTITLE 1,Step 3: Inspect the Parser Output
# MAGIC %md
# MAGIC ## Step 3: Inspect the Parser Output
# MAGIC
# MAGIC 📖 **[`ai_parse_document` reference](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)**
# MAGIC
# MAGIC Before parsing all 31 files, **parse one and look at what comes back.** `ai_parse_document` returns a `VARIANT`
# MAGIC (semi-structured JSON), and you need to see its actual shape before you can write extraction code against it.
# MAGIC
# MAGIC This habit matters beyond this project: never write extraction logic against a schema you have not looked at.
# MAGIC
# MAGIC Broadly the output looks like:
# MAGIC
# MAGIC ```
# MAGIC {
# MAGIC   "document": {
# MAGIC     "pages":    [ { "id": 0, ... }, ... ],
# MAGIC     "elements": [ { "id": 0, "page_id": 0, "type": "text", "content": "..." }, ... ]
# MAGIC   },
# MAGIC   "error_status": null
# MAGIC }
# MAGIC ```
# MAGIC
# MAGIC Run the cell below and confirm the field names **before** running Step 4. If they differ from the above, adjust
# MAGIC the `variant_get` paths in Step 4 to match what you actually see.
# MAGIC
# MAGIC > ⚠️ **`ai_parse_document` requires DBR 17.3+.** If you get `function not found`, your compute is too old.
# MAGIC > Switch to serverless or a DBR 17.3+ cluster.

# COMMAND ----------

# DBTITLE 1,Parse One File and Inspect the Structure
# MAGIC %sql
# MAGIC -- Parse a SINGLE document and look at the raw VARIANT before writing extraction logic.
# MAGIC SELECT
# MAGIC   path,
# MAGIC   ai_parse_document(content, map('version', '2.0')) AS parsed
# MAGIC FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles/',
# MAGIC   format => 'binaryFile'
# MAGIC )
# MAGIC WHERE lower(path) LIKE '%.pdf'
# MAGIC LIMIT 1

# COMMAND ----------

# DBTITLE 1,Step 4: Parse the PDFs to Text
# MAGIC %md
# MAGIC ## Step 4: Parse the PDFs to Text
# MAGIC
# MAGIC Now parse all 31 documents into one row **per page element**, keeping the page number so citations can point at
# MAGIC a page rather than a whole document.
# MAGIC
# MAGIC Two things worth noticing in the SQL below:
# MAGIC
# MAGIC 1. **`WHERE ... error_status IS NULL`** — a document that fails to parse should be dropped explicitly, not
# MAGIC    silently carried forward as a NULL row that breaks the chunking step.
# MAGIC 2. **`explode(variant_get(..., 'ARRAY<VARIANT>'))`** — `explode` needs a real ARRAY, so the VARIANT must be cast
# MAGIC    first. This is the single most common syntax error when working with `ai_parse_document` output.
# MAGIC
# MAGIC ### Parse once, chunk many times
# MAGIC
# MAGIC Parsing is an **LLM inference per document** — slow and billed. Step 5 offers two chunking strategies and
# MAGIC invites you to tune them, so we **materialise the parse once** into two tables and chunk from there:
# MAGIC
# MAGIC | Table | Contents | Used by |
# MAGIC |---|---|---|
# MAGIC | `article_parsed` | The raw `VARIANT` straight from the parser, one row per document | Semantic chunking (Step 5A) |
# MAGIC | `article_pages` | Flattened text + page number, one row per element | Fixed-window chunking (Step 5B) |
# MAGIC
# MAGIC Keeping the raw VARIANT matters: `ai_prep_search` takes the **parsed document object**, not flattened text, so
# MAGIC without `article_parsed` the semantic path would have to re-parse all 31 PDFs and pay for it again.

# COMMAND ----------

# DBTITLE 1,Parse All PDFs into article_parsed
# MAGIC %sql
# MAGIC -- The expensive step: one LLM inference per document. Run once, reuse everywhere.
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.article_parsed
# MAGIC COMMENT 'Raw ai_parse_document output for the dental article PDFs, one row per document'
# MAGIC AS
# MAGIC SELECT
# MAGIC   path                                              AS doc_uri,
# MAGIC   ai_parse_document(content, map('version', '2.0')) AS parsed
# MAGIC FROM read_files(
# MAGIC   '/Volumes/wavepoint_workshop/project_3_bronze/raw_data/articles/',
# MAGIC   format => 'binaryFile'
# MAGIC )
# MAGIC WHERE lower(path) LIKE '%.pdf'

# COMMAND ----------

# DBTITLE 1,Flatten to article_pages
# MAGIC %sql
# MAGIC -- Flattened view of the same parse: one row per page element. No re-parsing.
# MAGIC CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.article_pages
# MAGIC COMMENT 'Parsed text from the dental article PDFs, one row per page element'
# MAGIC AS
# MAGIC SELECT
# MAGIC   doc_uri,
# MAGIC   variant_get(el, '$.page_id', 'INT')    AS page,
# MAGIC   variant_get(el, '$.content', 'STRING') AS content
# MAGIC FROM wavepoint_workshop.project_3_silver.article_parsed
# MAGIC LATERAL VIEW explode(
# MAGIC   variant_get(parsed, '$.document.elements', 'ARRAY<VARIANT>')
# MAGIC ) e AS el
# MAGIC WHERE variant_get(parsed, '$.error_status', 'STRING') IS NULL
# MAGIC   AND variant_get(el, '$.content', 'STRING') IS NOT NULL

# COMMAND ----------

# DBTITLE 1,Verify the Parse
# MAGIC %sql
# MAGIC -- documents_parsed should be 31. A document with 0 rows failed to parse.
# MAGIC SELECT
# MAGIC   count(DISTINCT doc_uri)  AS documents_parsed,
# MAGIC   count(*)                 AS page_elements,
# MAGIC   sum(length(content))     AS total_characters
# MAGIC FROM wavepoint_workshop.project_3_silver.article_pages

# COMMAND ----------

# DBTITLE 1,Step 5: Chunk the Text into a Silver Table
# MAGIC %md
# MAGIC ## Step 5: Chunk the Text into a Silver Table
# MAGIC
# MAGIC Write `wavepoint_workshop.project_3_silver.article_chunks`. There are **two ways to chunk**, and the next cell
# MAGIC picks for you based on what your workspace supports.
# MAGIC
# MAGIC | | **5A — Semantic** (`ai_prep_search`) | **5B — Fixed window** (fallback) |
# MAGIC |---|---|---|
# MAGIC | Splits on | Meaning: sections, headings, topic shifts | Every 1000 characters |
# MAGIC | Boundaries | Respects where an idea ends | Cuts mid-sentence, patched with 150-char overlap |
# MAGIC | Context | Enriches each chunk with title/headers/page | None — a chunk is bare text |
# MAGIC | Requires | **DBR 18.2+ / serverless env v3+** | Any runtime |
# MAGIC
# MAGIC **Prefer 5A.** Fixed-size windows are a crude proxy for "one idea per chunk" — they cut wherever the character
# MAGIC count runs out, which is why overlap is needed to paper over the damage. Semantic chunking splits where the
# MAGIC *document* changes subject.
# MAGIC
# MAGIC ### The two-column trick in 5A
# MAGIC
# MAGIC `ai_prep_search` returns **two** versions of every chunk, and they are used differently:
# MAGIC
# MAGIC | Column | Use |
# MAGIC |---|---|
# MAGIC | `chunk_to_embed` | **Embed this.** Enriched with document title, section headers and page — so a chunk saying "this takes 30 to 60 days" still carries the context of *what* takes 30-60 days |
# MAGIC | `chunk_to_retrieve` | **Show this to the LLM.** The clean original text, without the injected context scaffolding |
# MAGIC
# MAGIC Getting these backwards is the classic mistake: embedding the bare text loses the context that makes retrieval
# MAGIC work, and handing the LLM the enriched version feeds it duplicated boilerplate.
# MAGIC
# MAGIC ### Target schema (identical from either path)
# MAGIC
# MAGIC | Column | Purpose |
# MAGIC |---|---|
# MAGIC | `chunk_id` | **Primary key — must be unique.** The index keys on this |
# MAGIC | `doc_uri` | Source file path — what your citations display |
# MAGIC | `page` | First page the chunk covers (`pages[0].page_id` in 5A) |
# MAGIC | `chunk_position` | Order of the chunk within its document |
# MAGIC | `content` | Text shown to the LLM (`chunk_to_retrieve` in 5A) |
# MAGIC | `chunk_to_embed` | Text that gets embedded (equals `content` in 5B) |
# MAGIC | `chunk_method` | `semantic` or `fixed_window` — record which path ran |
# MAGIC
# MAGIC Because both paths land the same schema, **Steps 6–12 are identical either way.**
# MAGIC
# MAGIC **Why silver?** Parsed, cleaned data derived from the bronze volume — the same rule you applied to the CSV
# MAGIC tables in Project 1.

# COMMAND ----------

# DBTITLE 1,Probe: Is ai_prep_search Available Here?
# ai_prep_search needs DBR 18.2+ / serverless env v3+. Rather than assume, ask the
# warehouse directly and let the answer choose the chunking path.
try:
    spark.sql("SELECT ai_prep_search(parse_json('{}')) AS probe").collect()
    HAS_AI_PREP_SEARCH = True
except Exception as e:
    msg = str(e)
    # "function not found" => genuinely unavailable. Any other error (e.g. a complaint
    # about our empty argument) means the function EXISTS and we can use it.
    unavailable = (
        "UNRESOLVED_ROUTINE" in msg
        or "not found" in msg.lower()
        or "cannot resolve" in msg.lower()
    )
    HAS_AI_PREP_SEARCH = not unavailable
    if unavailable:
        print(f"ai_prep_search is NOT available on this compute:\n  {msg.splitlines()[0]}")

print(f"\nHAS_AI_PREP_SEARCH = {HAS_AI_PREP_SEARCH}")
print(
    "→ Step 5A: semantic chunking" if HAS_AI_PREP_SEARCH
    else "→ Step 5B: fixed-window chunking (upgrade compute to DBR 18.2+ for semantic)"
)

# COMMAND ----------

# DBTITLE 1,Step 5A: Inspect the ai_prep_search Output
# MAGIC %md
# MAGIC ### Step 5A: Semantic chunking with `ai_prep_search`
# MAGIC
# MAGIC 📖 **[`ai_prep_search` reference](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_prep_search)**
# MAGIC
# MAGIC *Skip to 5B if the probe printed `False`.*
# MAGIC
# MAGIC Same discipline as Step 3: **look at the output before writing extraction against it.** The schema, confirmed
# MAGIC against this workspace with `schema_of_variant(...)`:
# MAGIC
# MAGIC ```
# MAGIC OBJECT<
# MAGIC   document: OBJECT<
# MAGIC     contents: ARRAY<OBJECT<
# MAGIC       chunk_id:          STRING,
# MAGIC       chunk_position:    BIGINT,
# MAGIC       chunk_to_embed:    STRING,
# MAGIC       chunk_to_retrieve: STRING,
# MAGIC       metadata:          OBJECT<>,
# MAGIC       pages:             ARRAY<OBJECT<image_uri: STRING, page_id: BIGINT>>
# MAGIC     >>
# MAGIC   >,
# MAGIC   pages:        ARRAY<OBJECT<id: BIGINT, image_uri: VOID>>,
# MAGIC   error_status: VOID
# MAGIC >
# MAGIC ```
# MAGIC
# MAGIC Two things to notice, both of which shape the write cell:
# MAGIC
# MAGIC - **`pages` on a chunk is an ARRAY, not a scalar** — a semantic chunk can span a page break. There is no
# MAGIC   `$.page` field; the citation page is `$.pages[0].page_id`
# MAGIC - **There is no `source_uri`** — the file path is not in the output, which is why we carry `doc_uri` through
# MAGIC   from `article_parsed` rather than reading it back out of the chunk
# MAGIC
# MAGIC ### Expect bigger chunks than the fixed-window path
# MAGIC
# MAGIC Measured on one of these documents, `chunk_to_retrieve` runs **~2,600–4,400 characters** — several times the
# MAGIC 1000-character fallback window. That is the point: the split lands where the *section* ends, not where a
# MAGIC character counter runs out. And `chunk_to_embed` came back **~30% longer** than `chunk_to_retrieve` on every
# MAGIC chunk — that difference is the injected title/header context you are embedding but not showing the LLM.

# COMMAND ----------

# DBTITLE 1,Inspect One Prepped Document
if HAS_AI_PREP_SEARCH:
    display(
        spark.sql("""
            SELECT ai_prep_search(parsed) AS prep
            FROM wavepoint_workshop.project_3_silver.article_parsed
            LIMIT 1
        """)
    )
else:
    print("Skipped — ai_prep_search is not available. Use Step 5B.")

# COMMAND ----------

# DBTITLE 1,Step 5A: Write article_chunks (Semantic)
if HAS_AI_PREP_SEARCH:
    spark.sql("""
        CREATE OR REPLACE TABLE wavepoint_workshop.project_3_silver.article_chunks
        COMMENT 'Semantically chunked dental article text, ready for vector indexing'
        AS
        WITH prepped AS (
          SELECT doc_uri, ai_prep_search(parsed) AS prep
          FROM wavepoint_workshop.project_3_silver.article_parsed
        )
        SELECT
          variant_get(chunk, '$.chunk_id',           'STRING') AS chunk_id,
          doc_uri,
          -- A chunk can span pages, so `pages` is an ARRAY. Cite the first one.
          variant_get(chunk, '$.pages[0].page_id',   'INT')    AS page,
          variant_get(chunk, '$.chunk_position',     'INT')    AS chunk_position,
          variant_get(chunk, '$.chunk_to_retrieve',  'STRING') AS content,
          variant_get(chunk, '$.chunk_to_embed',     'STRING') AS chunk_to_embed,
          'semantic'                                           AS chunk_method
        FROM prepped
        LATERAL VIEW explode(
          variant_get(prep, '$.document.contents', 'ARRAY<VARIANT>')
        ) c AS chunk
        WHERE variant_get(prep, '$.error_status', 'STRING') IS NULL
          AND variant_get(chunk, '$.chunk_to_embed', 'STRING') IS NOT NULL
    """)
    n = spark.table("wavepoint_workshop.project_3_silver.article_chunks").count()
    print(f"✅ Wrote {n:,} semantic chunks via ai_prep_search.")
else:
    print("Skipped — run Step 5B instead.")

# COMMAND ----------

# DBTITLE 1,Step 5B: Write article_chunks (Fixed Window Fallback)
# MAGIC %md
# MAGIC ### Step 5B: Fixed-window chunking — the fallback
# MAGIC
# MAGIC *Runs only if the probe printed `False`.* Splits every ~1000 characters with 150 characters of overlap.
# MAGIC
# MAGIC **Chunk size is the main quality knob here:**
# MAGIC
# MAGIC | Symptom | Cause | Fix |
# MAGIC |---|---|---|
# MAGIC | Answers vague and unfocused | Chunks too **big** — one vector averages too many ideas | Lower `CHUNK_SIZE` |
# MAGIC | Answers fragmentary, cut mid-thought | Chunks too **small** — context severed | Raise `CHUNK_SIZE` |
# MAGIC | Misses info spanning a boundary | Not enough **overlap** | Raise `OVERLAP` |
# MAGIC
# MAGIC `chunk_id` is a SHA-256 of `doc_uri` + page + chunk index, so it is **deterministic** — re-running produces
# MAGIC identical ids rather than a fresh random set, and the index syncs a stable set of keys.

# COMMAND ----------

# DBTITLE 1,Chunk and Write article_chunks (Fixed Window)
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType

# Tune these, re-run this cell, then re-sync the index (Step 10). No re-parsing needed.
CHUNK_SIZE = 1000
OVERLAP = 150


@F.udf(ArrayType(StringType()))
def split_into_chunks(text):
    """Split text into ~CHUNK_SIZE character windows overlapping by OVERLAP."""
    if not text:
        return []
    step = CHUNK_SIZE - OVERLAP
    out = []
    for start in range(0, len(text), step):
        piece = text[start:start + CHUNK_SIZE].strip()
        if piece:
            out.append(piece)
        if start + CHUNK_SIZE >= len(text):
            break
    return out


if HAS_AI_PREP_SEARCH:
    print("Skipped — semantic chunks already written in Step 5A.")
else:
    pages = spark.table("wavepoint_workshop.project_3_silver.article_pages")

    chunks = (
        pages
        .select(
            "doc_uri",
            "page",
            F.posexplode(split_into_chunks(F.col("content"))).alias("chunk_index", "content"),
        )
        .withColumn(
            "chunk_id",
            F.sha2(
                F.concat_ws("::", F.col("doc_uri"), F.col("page").cast("string"),
                            F.col("chunk_index").cast("string")),
                256,
            ),
        )
        # No context enrichment available, so the embedded and retrieved text are the same.
        .withColumnRenamed("chunk_index", "chunk_position")
        .withColumn("chunk_to_embed", F.col("content"))
        .withColumn("chunk_method", F.lit("fixed_window"))
        .select("chunk_id", "doc_uri", "page", "chunk_position",
                "content", "chunk_to_embed", "chunk_method")
    )

    (
        chunks.write
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable("wavepoint_workshop.project_3_silver.article_chunks")
    )
    print(f"✅ Wrote {chunks.count():,} fixed-window chunks (size={CHUNK_SIZE}, overlap={OVERLAP}).")

# COMMAND ----------

# DBTITLE 1,Verify Chunk Uniqueness
# MAGIC %sql
# MAGIC -- duplicate_ids MUST be 0. A Delta Sync index silently misbehaves on a non-unique primary key.
# MAGIC -- documents should be 31. chunk_method records which Step 5 path actually ran.
# MAGIC SELECT
# MAGIC   chunk_method,
# MAGIC   count(*)                                  AS total_chunks,
# MAGIC   count(DISTINCT chunk_id)                  AS distinct_ids,
# MAGIC   count(*) - count(DISTINCT chunk_id)       AS duplicate_ids,
# MAGIC   count(DISTINCT doc_uri)                   AS documents,
# MAGIC   round(avg(length(content)))               AS avg_retrieved_chars,
# MAGIC   round(avg(length(chunk_to_embed)))        AS avg_embedded_chars
# MAGIC FROM wavepoint_workshop.project_3_silver.article_chunks
# MAGIC GROUP BY chunk_method

# COMMAND ----------

# DBTITLE 1,Step 6: Enable Change Data Feed
# MAGIC %md
# MAGIC ## Step 6: Enable Change Data Feed
# MAGIC
# MAGIC # ⚠️ This is the single most common thing that breaks this project.
# MAGIC
# MAGIC **A Delta Sync vector index will not build without Change Data Feed enabled on the source table.**
# MAGIC
# MAGIC Change Data Feed (CDF) makes Delta record which rows changed in each version. The index uses that record to sync
# MAGIC incrementally — updating only what changed instead of re-embedding all chunks on every write. Without it, the
# MAGIC index has no way to track changes and index creation fails.
# MAGIC
# MAGIC If you skip this step, the failure surfaces later at index creation with a message about the source table not
# MAGIC supporting change data feed — a long way from the actual cause. **Enable it now.**

# COMMAND ----------

# DBTITLE 1,Enable Change Data Feed
# MAGIC %sql
# MAGIC ALTER TABLE wavepoint_workshop.project_3_silver.article_chunks
# MAGIC SET TBLPROPERTIES (delta.enableChangeDataFeed = true)

# COMMAND ----------

# DBTITLE 1,Confirm CDF Is On
# MAGIC %sql
# MAGIC -- delta.enableChangeDataFeed must show 'true' before you continue to Step 7.
# MAGIC SHOW TBLPROPERTIES wavepoint_workshop.project_3_silver.article_chunks

# COMMAND ----------

# DBTITLE 1,Step 7: Create the Vector Search Endpoint
# MAGIC %md
# MAGIC ## Step 7: Create the Vector Search Endpoint
# MAGIC
# MAGIC 📖 **[Vector Search endpoints](https://docs.databricks.com/aws/en/ai-search/create-ai-search/)**
# MAGIC
# MAGIC The endpoint is the compute that hosts your index.
# MAGIC
# MAGIC ### 💰 Cost — the important part
# MAGIC
# MAGIC **An endpoint bills for as long as it exists, whether or not you query it.** It is not serverless-per-query.
# MAGIC
# MAGIC - Create **exactly one**: `wavepoint-vs`
# MAGIC - Re-run the cell freely — it is written to reuse an existing endpoint, not create a second one
# MAGIC - Pausing for more than a day? **Ask before leaving it up**, and see the teardown in Step 12
# MAGIC
# MAGIC ### Endpoint type
# MAGIC
# MAGIC | Type | Latency | Cost | Use when |
# MAGIC |---|---|---|---|
# MAGIC | **STANDARD** | 20–50 ms | Higher | Interactive querying — **what we want here** |
# MAGIC | STORAGE_OPTIMIZED | 300–500 ms | ~7x lower | Hundreds of millions of vectors |
# MAGIC
# MAGIC A few thousand chunks is tiny, and we want snappy Playground responses, so **STANDARD**.
# MAGIC
# MAGIC > 🛑 **If endpoint creation fails because Vector Search is unavailable in your workspace region, stop here and
# MAGIC > flag it in Slack.** That changes the plan for Project 4 — do not try to work around it.

# COMMAND ----------

# DBTITLE 1,Create or Reuse the Endpoint
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceAlreadyExists

ENDPOINT_NAME = "wavepoint-vs"

w = WorkspaceClient()

existing = [e.name for e in w.vector_search_endpoints.list_endpoints()]
if ENDPOINT_NAME in existing:
    print(f"Endpoint '{ENDPOINT_NAME}' already exists — reusing it (no second endpoint, no extra cost).")
else:
    try:
        w.vector_search_endpoints.create_endpoint(
            name=ENDPOINT_NAME,
            endpoint_type="STANDARD",
        )
        print(f"Creating endpoint '{ENDPOINT_NAME}' — this is asynchronous and takes a few minutes.")
    except ResourceAlreadyExists:
        print(f"Endpoint '{ENDPOINT_NAME}' already exists — reusing it.")

print("\nAll endpoints in this workspace:")
for e in w.vector_search_endpoints.list_endpoints():
    state = e.endpoint_status.state if e.endpoint_status else "UNKNOWN"
    print(f"  {e.name:<24} {state}")

# COMMAND ----------

# DBTITLE 1,Wait for the Endpoint to Be ONLINE
import time

DEADLINE_MINUTES = 20
deadline = time.time() + DEADLINE_MINUTES * 60

while time.time() < deadline:
    ep = w.vector_search_endpoints.get_endpoint(ENDPOINT_NAME)
    state = str(ep.endpoint_status.state) if ep.endpoint_status else "UNKNOWN"
    print(f"{time.strftime('%H:%M:%S')}  endpoint state: {state}")
    if "ONLINE" in state.upper():
        print("\n✅ Endpoint is ONLINE — continue to Step 8.")
        break
    if "FAILED" in state.upper():
        raise RuntimeError(f"Endpoint creation FAILED: {ep.endpoint_status}")
    time.sleep(30)
else:
    raise TimeoutError(
        f"Endpoint not ONLINE after {DEADLINE_MINUTES} minutes. "
        "Check the Compute > Vector Search page in the workspace UI."
    )

# COMMAND ----------

# DBTITLE 1,Step 8: Create the Delta Sync Index
# MAGIC %md
# MAGIC ## Step 8: Create the Delta Sync Index
# MAGIC
# MAGIC Create a **Delta Sync index with managed embeddings**. Databricks reads `article_chunks`, embeds the `content`
# MAGIC column with `databricks-gte-large-en`, and keeps the vectors in sync with the table.
# MAGIC
# MAGIC | Setting | Value | Why |
# MAGIC |---|---|---|
# MAGIC | Index name | `wavepoint_workshop.project_3_silver.article_chunks_index` | Lives in UC beside its source |
# MAGIC | Primary key | `chunk_id` | Unique key from Step 5 |
# MAGIC | Embedding source | **`chunk_to_embed`** | The context-enriched text (see below) |
# MAGIC | Model | `databricks-gte-large-en` | 1024-dim, 8192-token window, strong English quality |
# MAGIC | Pipeline type | `TRIGGERED` | Syncs when you ask, not continuously — cheaper for a workshop |
# MAGIC
# MAGIC ### Embed one column, return another
# MAGIC
# MAGIC We embed **`chunk_to_embed`** but sync **`content`** so queries return it. On the semantic path those differ —
# MAGIC the embedded text carries injected title/header/page context that sharpens retrieval, while `content` is the
# MAGIC clean text you actually want the LLM to read. On the fixed-window path they are identical, so the same index
# MAGIC configuration works unchanged either way.
# MAGIC
# MAGIC **`TRIGGERED` vs `CONTINUOUS`:** `TRIGGERED` syncs on demand and lets its compute spin down in between.
# MAGIC `CONTINUOUS` keeps compute running to sync within seconds. For documents that change rarely, `TRIGGERED` is the
# MAGIC right call — and cheaper. Remember that after changing chunk size you must **re-sync** (Step 10) to pick it up.
# MAGIC
# MAGIC > Index creation is **asynchronous** and the initial embedding pass takes several minutes.

# COMMAND ----------

# DBTITLE 1,Create the Index
# The SDK wants typed objects here, not plain dicts — passing a dict raises
# AttributeError: 'dict' object has no attribute 'as_dict'.
from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    PipelineType,
    VectorIndexType,
)

SOURCE_TABLE = "wavepoint_workshop.project_3_silver.article_chunks"
INDEX_NAME = "wavepoint_workshop.project_3_silver.article_chunks_index"
EMBEDDING_MODEL = "databricks-gte-large-en"

existing_indexes = [
    i.name for i in w.vector_search_indexes.list_indexes(endpoint_name=ENDPOINT_NAME)
]

if INDEX_NAME in existing_indexes:
    print(f"Index '{INDEX_NAME}' already exists — skipping creation.")
else:
    w.vector_search_indexes.create_index(
        name=INDEX_NAME,
        endpoint_name=ENDPOINT_NAME,
        primary_key="chunk_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=SOURCE_TABLE,
            pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=[
                EmbeddingSourceColumn(
                    # Embed the context-enriched text, not the bare chunk.
                    name="chunk_to_embed",
                    embedding_model_endpoint_name=EMBEDDING_MODEL,
                )
            ],
            # Columns returned by queries. `content` is what the LLM reads;
            # doc_uri and page are what the citation shows.
            columns_to_sync=[
                "chunk_id", "doc_uri", "page", "content", "chunk_method",
            ],
        ),
    )
    print(f"Creating index '{INDEX_NAME}' — asynchronous, allow several minutes.")

# COMMAND ----------

# DBTITLE 1,Step 9: Wait for ONLINE and Verify
# MAGIC %md
# MAGIC ## Step 9: Wait for ONLINE and Verify
# MAGIC
# MAGIC Two checks before querying:
# MAGIC
# MAGIC 1. The index reports **ONLINE**
# MAGIC 2. Its **indexed row count matches** `article_chunks`
# MAGIC
# MAGIC The second check is the one people skip. An index can come ONLINE having indexed only *some* rows — then
# MAGIC retrieval quietly misses documents and you waste time blaming chunk size. **Confirm the counts match.**

# COMMAND ----------

# DBTITLE 1,Wait for the Index to Come ONLINE
import time

DEADLINE_MINUTES = 30
deadline = time.time() + DEADLINE_MINUTES * 60

while time.time() < deadline:
    idx = w.vector_search_indexes.get_index(INDEX_NAME)
    status = idx.status
    ready = bool(status.ready) if status else False
    msg = status.message if status else "no status"
    print(f"{time.strftime('%H:%M:%S')}  ready={ready}  {msg}")
    if ready:
        print("\n✅ Index is ONLINE.")
        break
    time.sleep(30)
else:
    raise TimeoutError(f"Index not ready after {DEADLINE_MINUTES} minutes.")

# COMMAND ----------

# DBTITLE 1,Verify Indexed Row Count Matches the Source
idx = w.vector_search_indexes.get_index(INDEX_NAME)
status = idx.status

indexed = getattr(status, "indexed_row_count", None)
source_rows = spark.table(SOURCE_TABLE).count()

print(f"Source table rows : {source_rows:,}")
if isinstance(indexed, int):
    print(f"Indexed rows      : {indexed:,}")
else:
    print("Indexed rows      : not reported yet")

if isinstance(indexed, int) and indexed != source_rows:
    print(
        f"\n⚠️  MISMATCH — {source_rows - indexed:,} rows are not indexed.\n"
        "    Trigger a sync (Step 10) and re-check before trusting retrieval results."
    )
elif isinstance(indexed, int):
    print("\n✅ Counts match — retrieval covers every chunk.")

# COMMAND ----------

# DBTITLE 1,Step 10: Query the Index
# MAGIC %md
# MAGIC ## Step 10: Query the Index
# MAGIC
# MAGIC Query with **three test questions** and print the **top 5 hits** with scores and `doc_uri`.
# MAGIC
# MAGIC ### How to read the results
# MAGIC
# MAGIC - **Score** is similarity, higher is better. Compare scores *within* one query, not across queries — the
# MAGIC   absolute number is not meaningful on its own
# MAGIC - **`doc_uri`** is the citation. Ask yourself: is this genuinely the document that should answer this question?
# MAGIC - A high score on the **wrong** document is the interesting failure — it usually means the chunk shares
# MAGIC   vocabulary with the question without sharing its meaning
# MAGIC
# MAGIC > **Re-syncing:** if you change chunk size and rewrite `article_chunks`, the `TRIGGERED` index does **not**
# MAGIC > update by itself. Run the sync cell below, wait for it to finish, then re-query.

# COMMAND ----------

# DBTITLE 1,Run Three Test Questions
import os

TEST_QUESTIONS = [
    "What A/R aging buckets should a dental practice track?",
    "How do you post an insurance EOB in Open Dental?",
    "What is the difference between an HMO and a PPO dental plan?",
]


def search(question, k=5):
    res = w.vector_search_indexes.query_index(
        index_name=INDEX_NAME,
        columns=["chunk_id", "doc_uri", "page", "content"],
        query_text=question,
        num_results=k,
    )
    return res.result.data_array if res.result else []


for q in TEST_QUESTIONS:
    print("=" * 100)
    print(f"Q: {q}")
    print("=" * 100)
    rows = search(q)
    if not rows:
        print("  (no results)")
        continue
    for rank, row in enumerate(rows, 1):
        # column order matches `columns` above; similarity score is appended last
        _chunk_id, doc_uri, page, content = row[0], row[1], row[2], row[3]
        score = row[-1]
        snippet = " ".join(str(content).split())[:200]
        print(f"\n  {rank}. score={score:.4f}  page={page}")
        print(f"     source : {os.path.basename(str(doc_uri))}")
        print(f"     text   : {snippet}...")
    print()

# COMMAND ----------

# DBTITLE 1,Trigger a Re-Sync (only after changing the chunk table)
# Run this ONLY if you rewrote article_chunks (e.g. tuned CHUNK_SIZE) and need the
# TRIGGERED index to pick the changes up. Then re-run the verify cell in Step 9.
#
# w.vector_search_indexes.sync_index(index_name=INDEX_NAME)
# print("Sync triggered — re-run the Step 9 count check before querying again.")

# COMMAND ----------

# DBTITLE 1,Step 11: Test in the AI Playground
# MAGIC %md
# MAGIC ## Step 11: Test in the AI Playground
# MAGIC
# MAGIC 📖 **[AI Playground](https://docs.databricks.com/aws/en/large-language-models/ai-playground)**
# MAGIC
# MAGIC Steps 1–10 tested **retrieval** — does the index find the right text? Now test **generation** — does an LLM
# MAGIC handed that text produce a good, honest answer?
# MAGIC
# MAGIC ### Setup
# MAGIC
# MAGIC 1. Open **AI Playground** from the left sidebar (under *Machine Learning*)
# MAGIC 2. Pick a chat model (e.g. a Llama or Claude endpoint)
# MAGIC 3. Click **Tools** → **Add tool** → select
# MAGIC    `wavepoint_workshop.project_3_silver.article_chunks_index`
# MAGIC 4. Ask the questions below and **save each answer** into the issue or a markdown file
# MAGIC
# MAGIC ### The four answerable questions
# MAGIC
# MAGIC 1. *What A/R aging buckets should a dental practice track, and what share over 90 days is considered healthy?*
# MAGIC 2. *How do you post an insurance EOB in Open Dental, and what goes wrong most often?*
# MAGIC 3. *What's the difference between an HMO and a PPO dental plan for the practice's revenue?*
# MAGIC 4. *What are the most common mistakes practices make when outsourcing dental billing?*
# MAGIC
# MAGIC For each: **name the source document the answer traces back to.** If you cannot, the answer is not grounded.
# MAGIC
# MAGIC ### The fifth question — the important one
# MAGIC
# MAGIC > **"What is our largest outstanding invoice?"**
# MAGIC
# MAGIC The documents **cannot** answer this. It is a numbers question about *your* data, and these are general
# MAGIC articles. Watch carefully:
# MAGIC
# MAGIC | Behaviour | What it means |
# MAGIC |---|---|
# MAGIC | Says it doesn't know / not in the documents | ✅ Correct — grounded and honest |
# MAGIC | Invents a figure | ❌ **Hallucination** — exactly the failure RAG is supposed to prevent |
# MAGIC | Returns irrelevant chunks and hedges | ⚠️ Retrieval found nothing useful but generation pressed on |
# MAGIC
# MAGIC **Write down which happened.** This split — *document questions* vs *data questions* — is precisely what the
# MAGIC supervisor agent in a later project has to learn to route. Your structured A/R tables from Project 1 answer the
# MAGIC second kind; this index answers the first.

# COMMAND ----------

# DBTITLE 1,Step 12: Record Findings, Commit, and Tear Down
# MAGIC %md
# MAGIC ## Step 12: Record Findings, Commit, and Tear Down
# MAGIC
# MAGIC ### 12.1 Record your findings
# MAGIC
# MAGIC Write these down — they are graded parts of the exercise, not optional colour:
# MAGIC
# MAGIC - [ ] **One retrieval failure** — a question where the top hits were wrong or irrelevant — **and one sentence on
# MAGIC       why.** Likely causes: chunk too big to be specific, vocabulary mismatch, or the answer genuinely is not in
# MAGIC       the corpus
# MAGIC - [ ] **One answer where the retrieved chunk was vendor marketing rather than neutral industry practice.** These
# MAGIC       are marketing articles; some chunks pitch a product. Note which, and whether the LLM presented the pitch as
# MAGIC       fact
# MAGIC - [ ] The five Playground answers, each with the source document named
# MAGIC
# MAGIC ### 12.2 Done when
# MAGIC
# MAGIC - [ ] `article_chunks_index` is ONLINE and returns relevant chunks for all four answerable questions
# MAGIC - [ ] Each Playground answer traces back to a real source document you can name
# MAGIC - [ ] One retrieval failure written down, with a reason
# MAGIC - [ ] One vendor-marketing chunk noted
# MAGIC - [ ] This notebook committed under `2_RAG/`
# MAGIC
# MAGIC ### 12.3 Commit
# MAGIC
# MAGIC ```bash
# MAGIC git add 2_RAG/
# MAGIC git commit -m "Add hands-on project 2: vector search index over dental articles"
# MAGIC git push
# MAGIC ```
# MAGIC
# MAGIC ### 12.4 💰 Tear down — do not skip
# MAGIC
# MAGIC The endpoint **keeps billing until you delete it.** When you are finished (and only then), run the teardown cell
# MAGIC below. If you are coming back tomorrow, ask first whether to leave it up.
# MAGIC
# MAGIC Deleting the index and endpoint does **not** touch `article_chunks` — your silver table stays, and you can
# MAGIC rebuild the index from it at any time.

# COMMAND ----------

# DBTITLE 1,Teardown (uncomment when finished)
# ⚠️ Deletes the index and the endpoint. The article_chunks table is NOT affected —
# you can rebuild the index from it later by re-running Steps 7-9.
#
# w.vector_search_indexes.delete_index(index_name=INDEX_NAME)
# print(f"Deleted index {INDEX_NAME}")
#
# w.vector_search_endpoints.delete_endpoint(endpoint_name=ENDPOINT_NAME)
# print(f"Deleted endpoint {ENDPOINT_NAME} — billing stopped.")

# COMMAND ----------

# DBTITLE 1,Next Steps & Resources
# MAGIC %md
# MAGIC ## Next Steps & Resources
# MAGIC
# MAGIC ### What you built
# MAGIC
# MAGIC ```
# MAGIC 31 PDFs (bronze volume)
# MAGIC   → article_parsed    (raw parser output, one row per document)
# MAGIC   → article_pages     (parsed text + page numbers)
# MAGIC   → article_chunks    (silver, CDF enabled, semantically chunked)
# MAGIC   → article_chunks_index  (Delta Sync, managed embeddings)
# MAGIC   → AI Playground with retrieval, answering with citations
# MAGIC ```
# MAGIC
# MAGIC You now have both halves of the lakehouse: **structured** tables from Project 1 that answer *"what is our A/R
# MAGIC over 90 days?"*, and an **unstructured** index that answers *"what should our A/R over 90 days be?"*.
# MAGIC
# MAGIC ### Tuning ideas
# MAGIC
# MAGIC | Try | Why |
# MAGIC |---|---|
# MAGIC | Chunk at 500 and 2000 chars | See the vague/fragmentary trade-off first-hand |
# MAGIC | `query_type="HYBRID"` | Adds keyword matching — helps for exact terms like CDT codes (`D6010`) |
# MAGIC | Compare `semantic` vs `fixed_window` | Chunk both ways, re-index, diff the answers |
# MAGIC | Filter by `doc_uri` | Restrict retrieval to one theme and watch precision change |
# MAGIC
# MAGIC ### Documentation
# MAGIC
# MAGIC - 📖 [Create a Vector Search index](https://docs.databricks.com/aws/en/ai-search/create-ai-search/)
# MAGIC - 📖 [Vector Search overview](https://docs.databricks.com/aws/en/generative-ai/vector-search)
# MAGIC - 📖 [`ai_parse_document`](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)
# MAGIC - 📖 [Delta Change Data Feed](https://docs.databricks.com/aws/en/delta/delta-change-data-feed)
# MAGIC - 📖 [AI Playground](https://docs.databricks.com/aws/en/large-language-models/ai-playground)
# MAGIC
# MAGIC ### Troubleshooting
# MAGIC
# MAGIC | Problem | Fix |
# MAGIC |---|---|
# MAGIC | `ai_parse_document` not found | Needs **DBR 17.3+** — switch to serverless or a newer cluster |
# MAGIC | Index creation fails mentioning change data feed | **Step 6** — CDF is not enabled on `article_chunks` |
# MAGIC | `explode()` fails on a VARIANT | Cast first: `explode(variant_get(x, '$.path', 'ARRAY<VARIANT>'))` |
# MAGIC | Index ONLINE but row counts differ | Trigger a sync, wait, re-check before trusting results |
# MAGIC | `'dict' object has no attribute 'as_dict'` | `create_index` needs typed SDK objects (`DeltaSyncVectorIndexSpecRequest`, `EmbeddingSourceColumn`), not a dict |
# MAGIC | Index stuck on *"pending endpoint provisioning"* | Normal — the endpoint can report ONLINE while still provisioning underneath. Keep waiting |
# MAGIC | Results are vague | Chunks too big — lower `CHUNK_SIZE`, rewrite, re-sync |
# MAGIC | Results are fragmentary | Chunks too small — raise `CHUNK_SIZE`, rewrite, re-sync |
# MAGIC | `ai_prep_search` not found | Needs **DBR 18.2+ / serverless env v3+**. The Step 5 probe falls back automatically |
# MAGIC | Retrieval worse after switching to semantic | Check you embedded `chunk_to_embed`, not `content` |
# MAGIC | Vector Search unavailable in region | **Stop and flag in Slack** — it changes the Project 4 plan |
