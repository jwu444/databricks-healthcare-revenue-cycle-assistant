#!/usr/bin/env python3
"""Verify the Claude Code <-> Databricks connection before starting project 1.

Run this on your own machine after completing the setup steps in README.md:

    python hands_on_project_0/verify_connection.py
    python hands_on_project_0/verify_connection.py --profile DEFAULT

`databricks current-user me` proves your credentials are valid. It does NOT
prove you can run a query, reach a model, or read Unity Catalog -- and those
are what projects 1-4 actually need. Each check below is independent, so a
failure names the broken capability instead of just "something is wrong".

Exit code is 0 when every check passes, 1 otherwise, so this is usable in CI.
"""
import argparse
import sys

try:
    from databricks.sdk import WorkspaceClient
except ImportError:
    sys.exit(
        "databricks-sdk is not installed.\n"
        "  pip install --user databricks-sdk    (exploration)\n"
        "  poetry add databricks-sdk            (project dependency)"
    )

EMBEDDING_ENDPOINT = "databricks-gte-large-en"


def build_checks(w):
    """(name, fn, needed_by). fn returns a detail string or raises."""

    def authentication():
        return w.current_user.me().user_name

    def unity_catalog():
        cats = [c.name for c in w.catalogs.list()]
        return f"{len(cats)} catalog(s): {', '.join(cats[:4])}"

    def warehouse():
        whs = list(w.warehouses.list())
        if not whs:
            raise RuntimeError("no SQL warehouse -- create one before project 1")
        return " | ".join(f"{x.name} [{x.state}]" for x in whs[:3])

    def sql_execution():
        wh = next(iter(w.warehouses.list()))
        r = w.statement_execution.execute_statement(
            warehouse_id=wh.id, statement="SELECT 1 AS ok", wait_timeout="30s"
        )
        return f"query returned {r.result.data_array[0][0]} on {wh.name}"

    def serving_endpoints():
        return f"{len(list(w.serving_endpoints.list()))} endpoint(s)"

    def embedding_model():
        names = [e.name for e in w.serving_endpoints.list()]
        emb = [n for n in names if any(k in n for k in ("gte", "bge", "embedding"))]
        if not emb:
            raise RuntimeError("no embedding endpoint -- project 2 cannot build an index")
        return ", ".join(emb[:3])

    def vector_search():
        # An empty list is a PASS: the API answered, which is what we're testing.
        # An actual endpoint would bill continuously -- see the root README.
        eps = list(w.vector_search_endpoints.list_endpoints())
        return f"API reachable, {len(eps)} endpoint(s) -- none is normal and costs nothing"

    return [
        ("Authentication", authentication, "all"),
        ("Unity Catalog read", unity_catalog, "1,2,3"),
        ("SQL warehouse", warehouse, "1,2,3"),
        ("SQL execution", sql_execution, "1,2,3"),
        ("Serving endpoints", serving_endpoints, "2,4"),
        ("Embedding model", embedding_model, "2"),
        ("Vector Search API", vector_search, "2"),
    ]


def end_to_end(w):
    """A real call that returns a real vector -- the same path project 2 depends on."""
    resp = w.serving_endpoints.query(
        name=EMBEDDING_ENDPOINT, input=["Post an insurance EOB in Open Dental."]
    )
    vec = resp.data[0].embedding
    if len(vec) != 1024:
        raise RuntimeError(f"expected 1024 dimensions, got {len(vec)}")
    return vec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--profile", help="~/.databrickscfg profile (omit to use the default)")
    ap.add_argument("--skip-end-to-end", action="store_true",
                    help="skip the live embedding call")
    args = ap.parse_args()

    try:
        w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
    except Exception as e:
        sys.exit(
            f"Could not create a WorkspaceClient: {e}\n\n"
            "Run `databricks configure --token` in YOUR OWN TERMINAL -- never through\n"
            "Claude Code. See README.md step 3."
        )

    results = []
    for name, fn, needed_by in build_checks(w):
        try:
            results.append(("PASS", name, fn(), needed_by))
        except Exception as e:
            results.append(("FAIL", name, str(e).split("\n")[0][:110], needed_by))

    width = max(len(r[1]) for r in results)
    print(f"{'':4} {'CHECK'.ljust(width)}  {'NEEDED BY':<10} DETAIL")
    print("-" * (width + 74))
    for status, name, detail, needed_by in results:
        print(f"{'PASS' if status == 'PASS' else 'FAIL'}  {name.ljust(width)}  "
              f"{needed_by:<10} {detail}")

    failed = [r for r in results if r[0] == "FAIL"]
    print()
    if failed:
        print(f"{len(failed)} check(s) failed -- see the Troubleshooting table in README.md:")
        for _, name, detail, needed_by in failed:
            print(f"  - {name} (needed by project {needed_by}): {detail}")
        return 1

    print("All capability checks passed.")

    if args.skip_end_to_end:
        print("End-to-end call skipped (--skip-end-to-end).")
        return 0

    print(f"\nEnd-to-end test via {EMBEDDING_ENDPOINT} ...")
    try:
        vec = end_to_end(w)
    except Exception as e:
        print(f"  FAILED: {str(e)[:200]}")
        print("  Does the endpoint appear above? Is the free daily limit exhausted?")
        return 1

    print(f"  dimensions : {len(vec)}")
    print(f"  first 5    : {[round(v, 4) for v in vec[:5]]}")
    print("\nConnection is ready for projects 1-4.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
