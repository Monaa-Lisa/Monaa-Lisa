"""
Abstract: Implements the incremental update pipeline that keeps the database
    in sync with arXiv.

    Flow
    ────
    1.  Query the DB for the most recent ``published`` date.
    2.  Fetch every paper published on arXiv after that date.
    3.  Filter out papers already in the DB (by entry_id).
    4.  Batch-request SemanticScholar for SPECTER v2 embeddings (768-D),
        citations, and references.
    5.  For papers with embeddings:
        -> PCA 768
        -> 128-D  
        -> UMAP 128
        -> 2-D  
        -> save to ``paper`` + ``embedding``.
    6.  Papers without SemanticScholar data 
        -> ``uncaught_paper`` table.
    7.  Periodically retry uncaught papers; drop after max retries.
        The pipeline is designed to run as a scheduled job (default: monthly)
        via APScheduler inside ``main.py``.
"""

import os
import time
from datetime import datetime, timedelta

import arxiv as arx

from config import cfg
from util.logger import Logger
from SemanticPaper.api.semantic_scholar import SemanticScholarAPI
from SemanticPaper.api.arxiv import ArxivAPI
from SemanticPaper.pipeline.embedding_pipeline import EmbeddingPipeline
from Database.db import (
    get_newest_paper_date,
    paper_exists_by_id,
    save_processed_paper,
    save_uncaught_paper,
    get_uncaught_papers_due,
    increment_uncaught_retry,
    delete_uncaught_paper,
    purge_expired_uncaught,
    get_paper_count,
)

logger = Logger("IncrementalPipeline")


# ------------------------------------------------------------------
#  arXiv gap-fill fetcher
# ------------------------------------------------------------------


def _fetch_new_arxiv_papers(arxiv_client: ArxivAPI, since: datetime,
                            max_results: int | None = None) -> list:
    """
    Abstract: Fetches papers from arXiv submitted after ``since``.
        Returns a list of ``arxiv.Result`` objects (not our Paper dataclass)
        so we keep all metadata available.
    Args:
    - arxiv_client: ArxivAPI instance
    - since: datetime – fetch papers newer than this date
    - max_results: optional cap
    Returns: list[arxiv.Result]
    """
    # arXiv Suchdatum-Format: YYYYMMDDHHMMSS
    date_str = since.strftime("%Y%m%d%H%M%S")
    # Suche nach allen Papern, die nach dem übergebenen Datum eingereicht wurden
    query = f"submittedDate:[{date_str} TO 99991231235959]"

    logger.info(f"Querying arXiv for papers since {since.isoformat()} ...")

    search = arx.Search(
        query=query,
        max_results=max_results,
        sort_by=arx.SortCriterion.SubmittedDate,
        sort_order=arx.SortOrder.Ascending,
    )

    results = []
    try:
        client = arxiv_client.client
        for result in client.results(search):
            results.append(result)
            if max_results and len(results) >= max_results:
                break
    except Exception as e:
        logger.error(f"Error fetching papers from arXiv: {e}")

    logger.info(f"Fetched {len(results)} papers from arXiv since {since.isoformat()}")
    return results


def _normalize_entry_id(entry_id_or_url: str) -> str:
    """Strips the arxiv.org URL prefix and version suffix."""
    # Entferne die URL-Präfixe, um nur die reine ID zu erhalten
    eid = entry_id_or_url.replace("http://arxiv.org/abs/", "").replace("http://arxiv.org/", "")
    # Entferne Versions-Suffix (z.B. v1, v2)
    if "v" in eid.split("/")[-1]:
        parts = eid.rsplit("v", 1)
        if parts[-1].isdigit():
            eid = parts[0]
    return eid



def run_incremental_update(
    arxiv_client: ArxivAPI,
    s2_client: SemanticScholarAPI,
    pipeline: EmbeddingPipeline,
    max_papers: int | None = None,
):
    """
    Abstract: Executes one full incremental sync cycle.
    Args:
    - arxiv_client: ArxivAPI instance
    - s2_client: SemanticScholarAPI instance
    - pipeline: EmbeddingPipeline (PCA + UMAP)
    - max_papers: optional cap on how many arXiv papers to fetch per cycle
    """
    logger.info("=== Incremental update started ===")
    t0 = time.time()

    newest_date = get_newest_paper_date()
    if newest_date is None:
        # Wenn die Datenbank leer ist, brechen wir ab, da zuerst der initiale Import laufen muss
        logger.warning("No papers in database – skipping incremental update (run initial import first).")
        return

    logger.info(f"Newest paper in DB: {newest_date.isoformat()}")
    paper_count_before = get_paper_count()

    # 1. Hole neue Paper von arXiv
    raw_results = _fetch_new_arxiv_papers(arxiv_client, newest_date, max_results=max_papers)
    if not raw_results:
        logger.info("No new papers found on arXiv. Database is up to date.")
        return

    # 2. Filtere Paper heraus, die bereits in der DB existieren
    new_papers = []
    for result in raw_results:
        eid = _normalize_entry_id(result.entry_id)
        # Prüfe, ob die normalisierte ID bereits in der Datenbank vorhanden ist
        if not paper_exists_by_id(eid):
            new_papers.append((eid, result))

    logger.info(f"{len(new_papers)} genuinely new papers after dedup (out of {len(raw_results)} fetched)")
    if not new_papers:
        logger.info("All fetched papers already exist in the DB.")
        return

    # 3. Batch-Abfrage bei SemanticScholar
    arxiv_ids = [eid for eid, _ in new_papers]
    # Lade die Batch-Größe aus der Konfiguration oder nutze den Standardwert 400
    s2_batch_size = cfg.get_int(
        "semanticpaper", "s2_batch_size",
        int(os.getenv("S2_BATCH_SIZE", "400"))
    )
    found, not_found = s2_client.fetch_batch(arxiv_ids, batch_size=s2_batch_size)

    # Erstelle Lookup-Map für arXiv-Ergebnis-Metadaten, um später darauf zugreifen zu können
    result_map: dict[str, arx.Result] = {eid: res for eid, res in new_papers}

    # 4. Verarbeite Paper mit Embeddings
    processed_count = 0
    if found:
        # Sammle 768-D Vektoren für die Batch-Verarbeitung
        vectors_768 = [item["embedding_768d"] for item in found]
        logger.info(f"Running PCA + UMAP on {len(vectors_768)} embeddings...")
        # Führe PCA und UMAP auf den gesammelten Vektoren aus
        batch_results = pipeline.batch_process(vectors_768)

        for item, (emb_128_list, (x, y)) in zip(found, batch_results):
            arxiv_id = item["arxiv_id"]
            result = result_map.get(arxiv_id)

            title = result.title if result else "[Unknown]"
            authors = ", ".join(str(a) for a in result.authors) if result else None
            abstract = result.summary if result else None
            categories = result.primary_category if result else None
            published = result.published if result else None
            updated = getattr(result, "updated", None)
            doi = getattr(result, "doi", None)
            journal_ref = getattr(result, "journal_ref", None)
            pdf_url = result.pdf_url if result else None

            # Speichere das verarbeitete Paper mit allen Metadaten und Embeddings in der Datenbank
            ok = save_processed_paper(
                entry_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                categories=categories,
                published=published,
                updated=updated,
                doi=doi,
                journal_ref=journal_ref,
                url=pdf_url,
                s2_id=item.get("s2_id"),
                non_arxiv_citation_count=item.get("non_arxiv_citation_count"),
                non_arxiv_reference_count=item.get("non_arxiv_reference_count"),
                embedding_128d=emb_128_list,
                tsne_x=x,
                tsne_y=y,
                citation_ids=item.get("citation_arxiv_ids"),
                reference_ids=item.get("reference_arxiv_ids"),
            )
            if ok:
                processed_count += 1
            else:
                logger.warning(f"Failed to save paper {arxiv_id}")

    # 5. Speichere nicht gefundene Paper (uncaught) für spätere Retrys
    uncaught_count = 0
    # Lade die maximale Anzahl an Retrys aus der Konfiguration
    max_retries = cfg.get_int("semanticpaper", "uncaught_max_retries", int(os.getenv("UNCAUGHT_MAX_RETRIES", "4")))
    for arxiv_id in not_found:
        result = result_map.get(arxiv_id)
        title = result.title if result else "[Unknown]"
        authors = ", ".join(str(a) for a in result.authors) if result else None
        abstract = result.summary if result else None
        categories = result.primary_category if result else None
        published = result.published if result else None
        pdf_url = result.pdf_url if result else None

        save_uncaught_paper(
            entry_id=arxiv_id,
            title=title,
            authors=authors,
            abstract=abstract,
            categories=categories,
            published=published,
            url=pdf_url,
            max_retries=max_retries,
        )
        uncaught_count += 1

    elapsed = time.time() - t0
    paper_count_after = get_paper_count()
    logger.info(
        f"=== Incremental update complete in {elapsed:.1f}s === "
        f"Processed: {processed_count}, Uncaught: {uncaught_count}, "
        f"DB total: {paper_count_before} -> {paper_count_after}"
    )

def retry_uncaught_papers(
    s2_client: SemanticScholarAPI,
    pipeline: EmbeddingPipeline, ):

    # Diese Funktion wird in regelmäßigen Intervallen ausgeführt, um "uncaught papers" erneut abzufragen, 
    # die zuvor nicht in SemanticScholar gefunden wurden.
    retry_interval = cfg.get_int(
        "semanticpaper", "uncaught_retry_interval_days",
        int(os.getenv("UNCAUGHT_RETRY_INTERVAL_DAYS", "14"))
    )

    logger.info(f"=== Uncaught paper retry (interval: {retry_interval}d) ===")

    # Eliminiere uncaught papers, die das Retry-Limit überschritten haben
    purge_expired_uncaught()
    # Hole alle uncaught papers, die für einen Retry fällig sind
    due = get_uncaught_papers_due(retry_interval_days=retry_interval)
    if not due:
        logger.info("No uncaught papers due for retry.")
        return

    logger.info(f"{len(due)} uncaught papers due for retry")

    arxiv_ids = [p.entry_id for p in due]
    s2_batch_size = cfg.get_int(
        "semanticpaper", "s2_batch_size",
        int(os.getenv("S2_BATCH_SIZE", "400"))
    )
    found, not_found = s2_client.fetch_batch(arxiv_ids, batch_size=s2_batch_size)

    # Erstelle eine Map für schnellen Zugriff auf die uncaught papers anhand ihrer ID
    uncaught_map = {p.entry_id: p for p in due}

    # Verarbeite gefundene Paper wie im Haupt-Update, speichere sie und lösche sie aus der uncaught-Tabelle.
    rescued_count = 0
    if found:
        # Extrahiere die 768-D Vektoren und verarbeite sie im Batch
        vectors_768 = [item["embedding_768d"] for item in found]
        batch_results = pipeline.batch_process(vectors_768)
        for item, (emb_128_list, (x, y)) in zip(found, batch_results):
            arxiv_id = item["arxiv_id"]
            uncaught = uncaught_map.get(arxiv_id)
    
            ok = save_processed_paper(
                entry_id=arxiv_id,
                title=uncaught.title if uncaught else "[Unknown]",
                authors=uncaught.authors if uncaught else None,
                abstract=uncaught.abstract if uncaught else None,
                categories=uncaught.categories if uncaught else None,
                published=uncaught.published if uncaught else None,
                url=uncaught.url if uncaught else None,
                s2_id=item.get("s2_id"),
                non_arxiv_citation_count=item.get("non_arxiv_citation_count"),
                non_arxiv_reference_count=item.get("non_arxiv_reference_count"),
                embedding_128d=emb_128_list,
                tsne_x=x,
                tsne_y=y,
                citation_ids=item.get("citation_arxiv_ids"),
                reference_ids=item.get("reference_arxiv_ids"),
            )
            if ok:
                # Wenn das Speichern erfolgreich war, entferne das Paper aus der uncaught-Tabelle
                delete_uncaught_paper(arxiv_id)
                rescued_count += 1

    # Erhöhe den Retry-Zähler für weiterhin fehlende Paper
    still_missing = 0
    for arxiv_id in not_found:
        increment_uncaught_retry(arxiv_id)
        still_missing += 1

    # Bereinige abgelaufene Paper erneut nach den Erhöhungen
    purge_expired_uncaught()

    logger.info(
        f"=== Uncaught retry complete: rescued={rescued_count}, "
        f"still missing={still_missing} ==="
    )
