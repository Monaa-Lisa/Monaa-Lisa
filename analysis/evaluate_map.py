"""
How well does the 2-d map keep what the embedding and the citations say?

Reads the database (read only) and prints three measurements:

  1. Neighbourhoods: for a sample of papers, how many of their k nearest
     papers in the 128-d embedding (cosine distance) are also among their k
     nearest papers on the map. Only papers whose embedding is in the
     database take part.
  2. Citations: are two papers that cite each other closer on the map than
     two random papers? Given as the probability that a citing pair is the
     closer one (AUC, 0.5 = no better than chance), on the map and, for
     comparison, in the embedding.
  3. Categories: how many of the 10 nearest papers on the map share the
     primary category, or the subject, of a paper, against the share
     expected by chance.

The 768-d SPECTER2 vectors are not stored, so the reference is the 128-d PCA
embedding the map was projected from.

Usage:
    DATABASE_URL=postgresql://user:password@host:5432/db python analysis/evaluate_map.py
    ... --queries 2000 --edges 200000 --seed 7 --json results.json

Needs numpy and psycopg2 (both in requirements.txt). With 1.2 million papers
it takes a few minutes and about 2 GB of memory.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import psycopg2


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", file=sys.stderr, flush=True)


def subject_of(category):
    """arXiv subject of a category id, e.g. cs.LG -> Computer Science."""
    prefixes = {
        "cs.": "Computer Science",
        "math.": "Mathematics",
        "stat.": "Statistics",
        "eess.": "Electrical Engineering",
        "q-bio.": "Quantitative Biology",
        "q-fin.": "Quantitative Finance",
        "econ.": "Economics",
    }
    for prefix, name in prefixes.items():
        if category.startswith(prefix):
            return name
    return "Physics"


def load_papers(conn):
    """Every paper with a map position: ids, positions, primary categories."""
    with conn.cursor(name="papers") as cur:
        cur.itersize = 100_000
        cur.execute(
            """
            SELECT entry_id, (tsne->>'x')::float8, (tsne->>'y')::float8,
                   split_part(trim(categories), ' ', 1)
            FROM paper
            WHERE tsne IS NOT NULL AND tsne->>'x' IS NOT NULL
            ORDER BY id
            """
        )
        ids, xy, categories = [], [], []
        for entry_id, x, y, category in cur:
            ids.append(entry_id)
            xy.append((x, y))
            categories.append(category or "")
    return ids, np.asarray(xy, dtype=np.float32), categories


def load_embeddings(conn, index_of):
    """The stored embeddings as unit vectors, with the row of their paper."""
    rows, vectors = [], []
    with conn.cursor(name="embeddings") as cur:
        cur.itersize = 20_000
        cur.execute("SELECT belonging_paper_entry_id, content::text FROM embedding")
        for entry_id, text in cur:
            row = index_of.get(entry_id)
            if row is None:
                continue
            rows.append(row)
            vectors.append(np.fromstring(text[1:-1], sep=",", dtype=np.float32))
    matrix = np.vstack(vectors)
    matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
    return np.asarray(rows), matrix


def load_citing_pairs(conn, index_of, wanted, rng):
    """A random sample of (citing, cited) pairs with both papers on the map."""
    with conn.cursor() as cur:
        cur.execute("SELECT reltuples::bigint FROM pg_class WHERE relname = 'paper_reference'")
        total = max(cur.fetchone()[0], 1)
        # twice the share needed: many references point to papers outside the dataset
        percent = min(100.0, 100.0 * wanted * 4 / total)
        cur.execute(
            "SELECT belonging_paper_entry_id, referenced_paper_entry_id "
            "FROM paper_reference TABLESAMPLE BERNOULLI (%s) REPEATABLE (%s)",
            (percent, int(rng.integers(1, 2**31 - 1))),
        )
        pairs = [
            (index_of[a], index_of[b])
            for a, b in cur
            if a in index_of and b in index_of and a != b
        ]
    pairs = np.asarray(pairs)
    if len(pairs) > wanted:
        pairs = pairs[rng.choice(len(pairs), wanted, replace=False)]
    return pairs


def nearest_on_map(xy, queries, k, chunk=32):
    """Rows of the k nearest points for every query row (the query itself left out)."""
    result = np.empty((len(queries), k), dtype=np.int64)
    for start in range(0, len(queries), chunk):
        q = queries[start : start + chunk]
        d = ((xy[None, :, 0] - xy[q, 0, None]) ** 2) + ((xy[None, :, 1] - xy[q, 1, None]) ** 2)
        d[np.arange(len(q)), q] = np.inf
        part = np.argpartition(d, k, axis=1)[:, :k]
        order = np.argsort(np.take_along_axis(d, part, axis=1), axis=1)
        result[start : start + chunk] = np.take_along_axis(part, order, axis=1)
    return result


def nearest_in_embedding(matrix, queries, k, chunk=64):
    result = np.empty((len(queries), k), dtype=np.int64)
    for start in range(0, len(queries), chunk):
        q = queries[start : start + chunk]
        similarity = matrix[q] @ matrix.T
        similarity[np.arange(len(q)), q] = -np.inf
        part = np.argpartition(-similarity, k, axis=1)[:, :k]
        order = np.argsort(-np.take_along_axis(similarity, part, axis=1), axis=1)
        result[start : start + chunk] = np.take_along_axis(part, order, axis=1)
    return result


def auc_closer(linked, random):
    """Probability that a linked pair is closer than a random pair (ties count half)."""
    values = np.concatenate([linked, random])
    order = values.argsort(kind="mergesort")
    ranks = np.empty(len(values))
    ranks[order] = np.arange(1, len(values) + 1)
    # average the ranks of equal values
    sorted_values = values[order]
    starts = np.flatnonzero(np.r_[True, sorted_values[1:] != sorted_values[:-1]])
    ends = np.r_[starts[1:], len(values)]
    for s, e in zip(starts, ends):
        if e - s > 1:
            ranks[order[s:e]] = (s + 1 + e) / 2
    u = ranks[: len(linked)].sum() - len(linked) * (len(linked) + 1) / 2
    return 1 - u / (len(linked) * len(random))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queries", type=int, default=2000, help="papers sampled for the neighbourhood and category checks")
    parser.add_argument("--edges", type=int, default=200_000, help="citing pairs sampled")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--json", help="also write the numbers to this file")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Set DATABASE_URL to the database to evaluate.")
    conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))
    conn.set_session(readonly=True)
    rng = np.random.default_rng(args.seed)
    results = {"seed": args.seed}

    log("loading map positions")
    ids, xy, categories = load_papers(conn)
    index_of = {entry_id: i for i, entry_id in enumerate(ids)}
    results["papers_on_map"] = len(ids)

    log("loading embeddings")
    rows, matrix = load_embeddings(conn, index_of)
    results["papers_with_embedding"] = len(rows)

    # 1. neighbourhoods, among the papers that have an embedding
    log("neighbourhoods")
    sub_xy = xy[rows]
    queries = rng.choice(len(rows), min(args.queries, len(rows)), replace=False)
    ks = [10, 30, 100]
    in_embedding = nearest_in_embedding(matrix, queries, max(ks))
    on_map = nearest_on_map(sub_xy, queries, max(ks))
    results["neighbourhood"] = {"queries": len(queries), "among": len(rows), "recall": {}}
    for k in ks:
        shared = [len(set(a[:k]) & set(b[:k])) for a, b in zip(in_embedding, on_map)]
        results["neighbourhood"]["recall"][k] = {
            "mean": float(np.mean(shared) / k),
            "chance": k / len(rows),
        }
    # the 10 nearest in the embedding that are at least among the 100 nearest on the map
    kept = [len(set(a[:10]) & set(b[:100])) for a, b in zip(in_embedding, on_map)]
    results["neighbourhood"]["top10_within_map_top100"] = float(np.mean(kept) / 10)

    # 2. citations
    log("citations")
    pairs = load_citing_pairs(conn, index_of, args.edges, rng)
    random_pairs = rng.integers(0, len(ids), size=pairs.shape)
    random_pairs = random_pairs[random_pairs[:, 0] != random_pairs[:, 1]]
    distance = lambda p: np.linalg.norm(xy[p[:, 0]] - xy[p[:, 1]], axis=1)
    linked, unlinked = distance(pairs), distance(random_pairs)
    results["citations"] = {
        "pairs": len(pairs),
        "map": {
            "auc": float(auc_closer(linked, unlinked)),
            "median_distance_citing": float(np.median(linked)),
            "median_distance_random": float(np.median(unlinked)),
        },
    }
    # the same in the embedding, for the pairs where both papers have one
    row_of = np.full(len(ids), -1)
    row_of[rows] = np.arange(len(rows))
    both = pairs[(row_of[pairs[:, 0]] >= 0) & (row_of[pairs[:, 1]] >= 0)]
    if len(both) > 100:
        cosine = lambda a, b: 1 - np.einsum("ij,ij->i", matrix[a], matrix[b])
        random_rows = rng.integers(0, len(rows), size=(len(both), 2))
        linked_e = cosine(row_of[both[:, 0]], row_of[both[:, 1]])
        unlinked_e = cosine(random_rows[:, 0], random_rows[:, 1])
        linked_m = np.linalg.norm(sub_xy[row_of[both[:, 0]]] - sub_xy[row_of[both[:, 1]]], axis=1)
        unlinked_m = np.linalg.norm(sub_xy[random_rows[:, 0]] - sub_xy[random_rows[:, 1]], axis=1)
        results["citations"]["with_embedding"] = {
            "pairs": len(both),
            "auc_embedding": float(auc_closer(linked_e, unlinked_e)),
            "auc_map": float(auc_closer(linked_m, unlinked_m)),
        }

    # 3. categories
    log("categories")
    queries = rng.choice(len(ids), min(args.queries, len(ids)), replace=False)
    neighbours = nearest_on_map(xy, queries, 10)
    category = np.asarray(categories)
    subject = np.asarray([subject_of(c) for c in categories])
    chance = lambda labels: float(((np.unique(labels, return_counts=True)[1] / len(labels)) ** 2).sum())
    results["categories"] = {
        "queries": len(queries),
        "same_primary_category": float((category[neighbours] == category[queries, None]).mean()),
        "same_primary_category_chance": chance(category),
        "same_subject": float((subject[neighbours] == subject[queries, None]).mean()),
        "same_subject_chance": chance(subject),
    }
    conn.close()

    n, c, g = results["neighbourhood"], results["citations"], results["categories"]
    print(f"Papers on the map: {results['papers_on_map']:,}, with an embedding: {results['papers_with_embedding']:,}")
    print(f"\n1. Neighbourhoods ({n['queries']:,} papers, among the {n['among']:,} with an embedding)")
    for k, r in n["recall"].items():
        print(f"   {k:>3} nearest in the embedding also among the {k} nearest on the map: {r['mean']:.1%}  (chance {r['chance']:.3%})")
    print(f"   10 nearest in the embedding among the 100 nearest on the map: {n['top10_within_map_top100']:.1%}")
    print(f"\n2. Citations ({c['pairs']:,} citing pairs against as many random pairs)")
    print(f"   a citing pair is closer on the map than a random pair: AUC {c['map']['auc']:.3f}")
    print(f"   median map distance: citing {c['map']['median_distance_citing']:.2f}, random {c['map']['median_distance_random']:.2f}")
    if "with_embedding" in c:
        w = c["with_embedding"]
        print(f"   pairs with embeddings ({w['pairs']:,}): AUC {w['auc_embedding']:.3f} in the embedding, {w['auc_map']:.3f} on the map")
    print(f"\n3. Categories ({g['queries']:,} papers, their 10 nearest on the map)")
    print(f"   same primary category: {g['same_primary_category']:.1%}  (chance {g['same_primary_category_chance']:.1%})")
    print(f"   same subject:          {g['same_subject']:.1%}  (chance {g['same_subject_chance']:.1%})")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
