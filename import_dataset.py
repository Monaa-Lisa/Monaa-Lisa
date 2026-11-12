#!/usr/bin/env python3
"""
Import jsonl into the Postgres database.

Handles the full dataset format including:
    - Paper metadata (entry_id, title, authors, abstract, ...)
    - 128-D embeddings (pre-reduced via PCA from 768-D SPECTER v2)
    - 2-D UMAP coordinates (tsne_x / tsne_y)
    - Citation and reference links (arXiv IDs)

Usage:
    python import_dataset.py [--file Full_Dataset_WithCoordsAndEmbeddings.jsonl] [--batch-size 5000]

Requirements:
    pip install psycopg2-binary  (already in requirements.txt)

Strategy:
    1. Read JSONL line-by-line (memory-safe for 10 GB+)
    2. Batch-insert papers via COPY (fastest Postgres bulk method)
    3. Batch-insert embeddings via COPY
    4. Collect citation / reference links and batch-insert via COPY
    5. Skip duplicates gracefully using a temp table + INSERT ... ON CONFLICT
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime

import psycopg2
import psycopg2.extras
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_dt(value: str | None) -> str | None:
    """Return an ISO timestamp string or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt.isoformat()
    except Exception:
        return None


def escape_copy(value) -> str:
    """Escape a value for Postgres COPY TSV format."""
    if value is None:
        return "\\N"
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("\t", "\\t")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return s


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection():
    """Create a psycopg2 connection from DATABASE_URL or individual env vars."""
    url = os.environ.get("DATABASE_URL")
    if url:
        url = url.replace("postgresql+psycopg2://", "postgresql://")
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "monaa"),
        password=os.environ.get("POSTGRES_PASSWORD", "monaa"),
        dbname=os.environ.get("POSTGRES_DB", "monaa"),
    )


def ensure_tables(conn):
    """Create core tables if they don't exist yet and drop link-table FKs."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS paper (
                id SERIAL PRIMARY KEY,
                entry_id VARCHAR UNIQUE NOT NULL,
                title VARCHAR NOT NULL,
                authors VARCHAR,
                abstract TEXT,
                categories VARCHAR,
                published TIMESTAMP,
                updated TIMESTAMP,
                doi VARCHAR,
                journal_ref VARCHAR,
                license VARCHAR,
                url VARCHAR,
                s2_id VARCHAR UNIQUE,
                non_arxiv_citation_count INTEGER,
                non_arxiv_reference_count INTEGER,
                related_arxiv_ids JSON,
                tsne JSON
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS embedding (
                id SERIAL PRIMARY KEY,
                belonging_paper_entry_id VARCHAR NOT NULL UNIQUE REFERENCES paper(entry_id),
                content JSON NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS paper_citation (
                belonging_paper_entry_id VARCHAR NOT NULL,
                cited_paper_entry_id VARCHAR NOT NULL,
                PRIMARY KEY (belonging_paper_entry_id, cited_paper_entry_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS paper_reference (
                belonging_paper_entry_id VARCHAR NOT NULL,
                referenced_paper_entry_id VARCHAR NOT NULL,
                PRIMARY KEY (belonging_paper_entry_id, referenced_paper_entry_id)
            );
        """)
        for constraint in [
            ("paper_citation", "paper_citation_belonging_paper_entry_id_fkey"),
            ("paper_citation", "paper_citation_cited_paper_entry_id_fkey"),
            ("paper_reference", "paper_reference_belonging_paper_entry_id_fkey"),
            ("paper_reference", "paper_reference_referenced_paper_entry_id_fkey"),
        ]:
            cur.execute(f"ALTER TABLE {constraint[0]} DROP CONSTRAINT IF EXISTS {constraint[1]};")
    conn.commit()
    print("[schema] Tables ensured, FK constraints on link tables dropped.")


# ---------------------------------------------------------------------------
# COPY-based bulk insert
# ---------------------------------------------------------------------------

PAPER_COLS = [
    "entry_id", "title", "authors", "abstract", "categories",
    "published", "updated", "doi", "journal_ref", "license",
    "url", "s2_id", "non_arxiv_citation_count", "non_arxiv_reference_count",
    "related_arxiv_ids", "tsne",
]

EMBEDDING_COLS = ["belonging_paper_entry_id", "content"]
PAPER_CITATION_COLS = ["belonging_paper_entry_id", "cited_paper_entry_id"]
PAPER_REFERENCE_COLS = ["belonging_paper_entry_id", "referenced_paper_entry_id"]


def flush_papers(conn, rows: list[tuple]):
    """Bulk-insert papers via temp table + ON CONFLICT."""
    if not rows:
        return
    cols = ", ".join(PAPER_COLS)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE _tmp_paper (LIKE paper INCLUDING DEFAULTS)
                ON COMMIT DROP;
            """)
            cur.execute("ALTER TABLE _tmp_paper DROP COLUMN IF EXISTS id;")

            buf = io.StringIO()
            for row in rows:
                buf.write("\t".join(escape_copy(v) for v in row) + "\n")
            buf.seek(0)
            cur.copy_from(buf, "_tmp_paper", columns=PAPER_COLS)

            cur.execute(f"""
                INSERT INTO paper ({cols})
                SELECT {cols} FROM _tmp_paper
                ON CONFLICT (entry_id) DO UPDATE SET
                    title     = EXCLUDED.title,
                    authors   = EXCLUDED.authors,
                    abstract  = EXCLUDED.abstract,
                    categories = EXCLUDED.categories,
                    published = EXCLUDED.published,
                    updated   = EXCLUDED.updated,
                    doi       = EXCLUDED.doi,
                    journal_ref = EXCLUDED.journal_ref,
                    license   = EXCLUDED.license,
                    url       = EXCLUDED.url,
                    s2_id     = EXCLUDED.s2_id,
                    non_arxiv_citation_count  = EXCLUDED.non_arxiv_citation_count,
                    non_arxiv_reference_count = EXCLUDED.non_arxiv_reference_count,
                    related_arxiv_ids = EXCLUDED.related_arxiv_ids,
                    tsne      = EXCLUDED.tsne;
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[warn] Bulk paper insert failed ({e}), falling back to row-by-row...")
        _flush_papers_rowwise(conn, cols, rows)


def _flush_papers_rowwise(conn, cols: str, rows: list[tuple]):
    """Fallback: insert papers one by one."""
    placeholders = ", ".join(["%s"] * len(PAPER_COLS))
    skipped = 0
    for row in rows:
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO paper ({cols}) VALUES ({placeholders})
                    ON CONFLICT (entry_id) DO UPDATE SET
                        title     = EXCLUDED.title,
                        authors   = EXCLUDED.authors,
                        abstract  = EXCLUDED.abstract,
                        categories = EXCLUDED.categories,
                        published = EXCLUDED.published,
                        updated   = EXCLUDED.updated,
                        doi       = EXCLUDED.doi,
                        journal_ref = EXCLUDED.journal_ref,
                        license   = EXCLUDED.license,
                        url       = EXCLUDED.url,
                        s2_id     = EXCLUDED.s2_id,
                        non_arxiv_citation_count  = EXCLUDED.non_arxiv_citation_count,
                        non_arxiv_reference_count = EXCLUDED.non_arxiv_reference_count,
                        related_arxiv_ids = EXCLUDED.related_arxiv_ids,
                        tsne      = EXCLUDED.tsne;
                """, row)
            conn.commit()
        except Exception:
            conn.rollback()
            skipped += 1
    if skipped:
        print(f"[warn] Skipped {skipped} papers due to constraint violations.")


def flush_embeddings(conn, rows: list[tuple]):
    """Bulk-insert embeddings via temp table + ON CONFLICT."""
    if not rows:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE _tmp_embedding (
                    belonging_paper_entry_id TEXT NOT NULL,
                    content TEXT NOT NULL
                ) ON COMMIT DROP;
            """)
            buf = io.StringIO()
            for row in rows:
                buf.write(f"{escape_copy(row[0])}\t{escape_copy(row[1])}\n")
            buf.seek(0)
            cur.copy_from(buf, "_tmp_embedding", columns=EMBEDDING_COLS)
            cur.execute("""
                INSERT INTO embedding (belonging_paper_entry_id, content)
                SELECT belonging_paper_entry_id, content::vector FROM _tmp_embedding
                ON CONFLICT (belonging_paper_entry_id) DO UPDATE SET
                    content = EXCLUDED.content;
            """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[warn] Bulk embedding insert failed ({e}), falling back to row-by-row...")
        skipped = 0
        for row in rows:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO embedding (belonging_paper_entry_id, content)
                        VALUES (%s, %s::vector)
                        ON CONFLICT (belonging_paper_entry_id) DO UPDATE SET content = EXCLUDED.content;
                    """, row)
                conn.commit()
            except Exception:
                conn.rollback()
                skipped += 1
        if skipped:
            print(f"[warn] Skipped {skipped} embeddings due to errors.")


def flush_links(conn, table: str, cols: list[str], rows: list[tuple]):
    """Bulk-insert citation/reference links via temp table + ON CONFLICT."""
    if not rows:
        return
    with conn.cursor() as cur:
        tmp = f"_tmp_{table}"
        cur.execute(f"""
            CREATE TEMP TABLE {tmp} (
                {cols[0]} TEXT NOT NULL,
                {cols[1]} TEXT NOT NULL
            ) ON COMMIT DROP;
        """)
        buf = io.StringIO()
        for row in rows:
            buf.write(f"{escape_copy(row[0])}\t{escape_copy(row[1])}\n")
        buf.seek(0)
        cur.copy_from(buf, tmp, columns=cols)
        col_list = ", ".join(cols)
        cur.execute(f"""
            INSERT INTO {table} ({col_list})
            SELECT {col_list} FROM {tmp}
            ON CONFLICT DO NOTHING;
        """)
    conn.commit()


# ---------------------------------------------------------------------------
# Main import loop
# ---------------------------------------------------------------------------

def import_dataset(filepath: str, batch_size: int = 20000):
    conn = get_connection()
    print(f"[db] Connected to {conn.dsn}")
    ensure_tables(conn)

    paper_batch: list[tuple] = []
    embedding_batch: list[tuple] = []
    citation_batch: list[tuple] = []
    reference_batch: list[tuple] = []

    total_papers = 0
    total_embeddings = 0
    total_citations = 0
    total_references = 0
    t0 = time.time()

    # Get total file size for progress bar (rough estimate)
    file_size = os.path.getsize(filepath)

    with open(filepath, "r", encoding="utf-8") as fh:
        # Use tqdm for progress bar
        pbar = tqdm(fh, total=None, unit="papers", mininterval=1.0, desc="Importing")
        
        for line_no, line in enumerate(pbar, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[warn] Skipping line {line_no}: {e}")
                continue

            # Support both old ("id") and new ("entry_id") field name
            entry_id = (rec.get("entry_id") or rec.get("id", "")).strip()
            if not entry_id:
                continue

            title = rec.get("title", "").strip()
            authors = rec.get("authors", None)
            abstract = rec.get("abstract", None)
            published = parse_dt(rec.get("published"))
            updated = parse_dt(rec.get("updated"))
            categories = rec.get("categories", None)
            doi = rec.get("doi", None)
            journal_ref = rec.get("journal_ref", None)
            license_val = rec.get("license", None)
            url = rec.get("url", None)
            s2_id = rec.get("s2_id", None)
            non_arxiv_cit = rec.get("non_arxiv_citation_count", None)
            non_arxiv_ref = rec.get("non_arxiv_reference_count", None)

            # Related arXiv IDs (from Semantic Scholar)
            related_arxiv_ids = rec.get("related_arxiv_ids", None)
            related_arxiv_json = None
            if related_arxiv_ids and isinstance(related_arxiv_ids, list):
                related_arxiv_json = json.dumps(related_arxiv_ids)

            # Build tsne JSON from tsne_x / tsne_y if present
            tsne_x = rec.get("tsne_x")
            tsne_y = rec.get("tsne_y")
            tsne_json = None
            if tsne_x is not None and tsne_y is not None:
                tsne_json = json.dumps({"x": tsne_x, "y": tsne_y, "method": "umap"})

            paper_row = (
                entry_id, title, authors, abstract, categories,
                published, updated, doi, journal_ref,
                license_val, url, s2_id, non_arxiv_cit, non_arxiv_ref,
                related_arxiv_json, tsne_json,
            )
            paper_batch.append(paper_row)
            total_papers += 1

            # Embedding (128-D vector)
            embedding_vec = rec.get("embedding")
            if embedding_vec and isinstance(embedding_vec, list) and len(embedding_vec) > 0:
                embedding_batch.append((entry_id, json.dumps(embedding_vec)))
                total_embeddings += 1

            # Citations (arXiv IDs this paper is cited by)
            for cit_id in (rec.get("citations") or []):
                cit_id = str(cit_id).strip()
                if cit_id:
                    citation_batch.append((entry_id, cit_id))
                    total_citations += 1

            # References (arXiv IDs this paper references)
            for ref_id in (rec.get("references") or []):
                ref_id = str(ref_id).strip()
                if ref_id:
                    reference_batch.append((entry_id, ref_id))
                    total_references += 1

            # Flush papers
            if len(paper_batch) >= batch_size:
                flush_papers(conn, paper_batch)
                paper_batch.clear()

            # Flush embeddings
            if len(embedding_batch) >= batch_size:
                flush_embeddings(conn, embedding_batch)
                embedding_batch.clear()

            # Flush links
            if len(citation_batch) >= batch_size * 5:
                flush_links(conn, "paper_citation", PAPER_CITATION_COLS, citation_batch)
                citation_batch.clear()

            if len(reference_batch) >= batch_size * 5:
                flush_links(conn, "paper_reference", PAPER_REFERENCE_COLS, reference_batch)
                reference_batch.clear()

            # Update progress bar description with stats
            if line_no % 1000 == 0:
                pbar.set_postfix({
                    "papers": f"{total_papers:,}",
                    "cits": f"{total_citations:,}",
                    "refs": f"{total_references:,}"
                })

    # Flush remaining
    flush_papers(conn, paper_batch)
    flush_embeddings(conn, embedding_batch)
    flush_links(conn, "paper_citation", PAPER_CITATION_COLS, citation_batch)
    flush_links(conn, "paper_reference", PAPER_REFERENCE_COLS, reference_batch)

    elapsed = time.time() - t0
    print(
        f"\n[done] Imported {total_papers:,} papers, "
        f"{total_embeddings:,} embeddings, "
        f"{total_citations:,} citations, {total_references:,} references "
        f"in {elapsed:.1f}s"
    )
    conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import MonaaLisa JSONL dataset into Postgres")
    parser.add_argument(
        "--file", "-f",
        default="Full_Dataset_WithCoordsAndEmbeddings.jsonl",
        help="Path to the JSONL file (default: Full_Dataset_WithCoordsAndEmbeddings.jsonl)",
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=20000,
        help="Number of papers per batch INSERT (default: 20000)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"[error] File not found: {args.file}")
        sys.exit(1)

    import_dataset(args.file, args.batch_size)
