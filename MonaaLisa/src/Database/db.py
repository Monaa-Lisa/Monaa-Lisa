"""
Database access for the Python pipeline. The schema itself is owned by the
SQL migrations in db/migrations (dbmate), this module only reads and writes rows.
"""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker

from Database.db_models import DBEmbedding, DBPaper, DBUncaughtPaper
from util.logger import Logger

load_dotenv()

logger = Logger("Database")

# DATABASE_URL remains env-driven for Docker; do not move into config.ini
DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_pre_ping=True,
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


"""
Abstract: Checks whether the paper table is empty (first-run indicator).
Returns: bool -> True if no papers exist in the DB.
"""
def is_database_empty() -> bool:
    session = SessionLocal()
    try:
        count = session.query(DBPaper.id).limit(1).count()
        return count == 0
    except Exception as e:
        logger.warning(f"Could not check database emptiness: {e}")
        return True
    finally:
        session.close()


"""
Abstract: Returns the most recent published date across all papers.
Returns: datetime | None
"""
def get_newest_paper_date():
    from sqlalchemy import func as sa_func
    session = SessionLocal()
    try:
        result = session.query(sa_func.max(DBPaper.published)).scalar()
        return result
    except Exception as e:
        logger.error(f"Failed to get newest paper date: {e}")
        return None
    finally:
        session.close()


"""
Abstract: Returns the total number of papers in the DB.
Returns: int
"""
def get_paper_count() -> int:
    session = SessionLocal()
    try:
        return session.query(DBPaper.id).count()
    except Exception:
        return 0
    finally:
        session.close()


"""
Abstract: Saves a paper to the uncaught_paper table for later retry.
Args:
- entry_id, title, authors, abstract, categories, published, url
Returns: bool
"""
def save_uncaught_paper(entry_id: str, title: str, authors: str | None = None,
                        abstract: str | None = None, categories: str | None = None,
                        published=None, url: str | None = None,
                        max_retries: int = 4) -> bool:
    session = SessionLocal()
    try:
        existing = session.query(DBUncaughtPaper).filter_by(entry_id=entry_id).first()
        if existing:
            return True
        uncaught = DBUncaughtPaper(
            entry_id=entry_id,
            title=title,
            authors=authors,
            abstract=abstract,
            categories=categories,
            published=published,
            url=url,
            max_retries=max_retries,
        )
        session.add(uncaught)
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save uncaught paper {entry_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()


"""
Abstract: Returns uncaught papers whose last_checked is older than the given
          interval (or was never checked), limited to those below max_retries.
Args:
- retry_interval_days: minimum days since last check
Returns: list[DBUncaughtPaper]
"""
def get_uncaught_papers_due(retry_interval_days: int = 14) -> list:
    session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - __import__("datetime").timedelta(days=retry_interval_days)
        rows = (
            session.query(DBUncaughtPaper)
            .filter(DBUncaughtPaper.retry_count < DBUncaughtPaper.max_retries)
            .filter(
                (DBUncaughtPaper.last_checked.is_(None)) | (DBUncaughtPaper.last_checked <= cutoff)
            )
            .all()
        )
        # Detach from session so caller can use them freely
        session.expunge_all()
        return list(rows)
    except Exception as e:
        logger.error(f"Failed to query uncaught papers: {e}")
        return []
    finally:
        session.close()


"""
Abstract: Increments the retry_count and sets last_checked for an uncaught paper.
Args:
- entry_id: the arXiv entry_id
Returns: bool
"""
def increment_uncaught_retry(entry_id: str) -> bool:
    session = SessionLocal()
    try:
        row = session.query(DBUncaughtPaper).filter_by(entry_id=entry_id).first()
        if not row:
            return False
        row.retry_count += 1
        row.last_checked = datetime.now(timezone.utc).replace(tzinfo=None)
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to increment retry for {entry_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()


"""
Abstract: Removes an uncaught paper (either successfully processed or expired).
Args:
- entry_id: the arXiv entry_id
Returns: bool
"""
def delete_uncaught_paper(entry_id: str) -> bool:
    session = SessionLocal()
    try:
        session.query(DBUncaughtPaper).filter_by(entry_id=entry_id).delete()
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete uncaught paper {entry_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()


"""
Abstract: Drops uncaught papers whose retry_count >= max_retries.
Returns: int -> number of expired entries removed
"""
def purge_expired_uncaught() -> int:
    session = SessionLocal()
    try:
        count = (
            session.query(DBUncaughtPaper)
            .filter(DBUncaughtPaper.retry_count >= DBUncaughtPaper.max_retries)
            .delete()
        )
        session.commit()
        logger.info(f"Purged {count} expired uncaught papers")
        return count
    except Exception as e:
        logger.error(f"Failed to purge expired uncaught papers: {e}")
        session.rollback()
        return 0
    finally:
        session.close()


"""
Abstract: Returns which of the given entry_ids already exist in the paper table,
    using one query instead of one query per paper.
Args:
- entry_ids: list of arXiv entry_ids
Returns: set[str]
"""
def get_existing_entry_ids(entry_ids: list[str]) -> set[str]:
    if not entry_ids:
        return set()
    session = SessionLocal()
    try:
        rows = session.query(DBPaper.entry_id).filter(DBPaper.entry_id.in_(entry_ids)).all()
        return {row.entry_id for row in rows}
    finally:
        session.close()


"""
Abstract: Saves a fully processed paper (with embedding + coordinates) to the DB.
    Used by the incremental pipeline after SemanticScholar batch processing.
Args:
- entry_id, title, authors, abstract, categories, published, updated,
  doi, journal_ref, license_val, url, s2_id,
  non_arxiv_citation_count, non_arxiv_reference_count,
  embedding_128d (list[float]), tsne_x (float), tsne_y (float),
  citation_ids (list[str]), reference_ids (list[str])
Returns: bool
"""
def save_processed_paper(entry_id: str, title: str, authors: str | None,
                         abstract: str | None, categories: str | None,
                         published=None, updated=None,
                         doi: str | None = None, journal_ref: str | None = None,
                         license_val: str | None = None, url: str | None = None,
                         s2_id: str | None = None,
                         non_arxiv_citation_count: int | None = None,
                         non_arxiv_reference_count: int | None = None,
                         embedding_128d: list | None = None,
                         tsne_x: float | None = None, tsne_y: float | None = None,
                         citation_ids: list[str] | None = None,
                         reference_ids: list[str] | None = None) -> bool:
    from Database.db_models import DBPaperCitation, DBPaperReference
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    session = SessionLocal()
    try:
        # The column is JSON already, so pass the dict as-is (json.dumps here
        # would store a string and the frontend could not read x/y).
        tsne_val = None
        if tsne_x is not None and tsne_y is not None:
            tsne_val = {"x": tsne_x, "y": tsne_y, "method": "umap"}

        existing = session.query(DBPaper).filter_by(entry_id=entry_id).first()
        if existing:
            existing.title = title or existing.title
            existing.authors = authors or existing.authors
            existing.abstract = abstract or existing.abstract
            existing.categories = categories or existing.categories
            existing.published = published or existing.published
            existing.updated = updated or existing.updated
            existing.doi = doi or existing.doi
            existing.journal_ref = journal_ref or existing.journal_ref
            existing.license = license_val or existing.license
            existing.url = url or existing.url
            existing.s2_id = s2_id or existing.s2_id
            existing.non_arxiv_citation_count = non_arxiv_citation_count
            existing.non_arxiv_reference_count = non_arxiv_reference_count
            if tsne_val:
                existing.tsne = tsne_val
        else:
            paper = DBPaper(
                entry_id=entry_id,
                title=title,
                authors=authors,
                abstract=abstract,
                categories=categories,
                published=published,
                updated=updated,
                doi=doi,
                journal_ref=journal_ref,
                license=license_val,
                url=url,
                s2_id=s2_id,
                non_arxiv_citation_count=non_arxiv_citation_count,
                non_arxiv_reference_count=non_arxiv_reference_count,
                tsne=tsne_val,
            )
            session.add(paper)
        session.flush()

        # Embedding
        if embedding_128d is not None:
            session.query(DBEmbedding).filter_by(belonging_paper_entry_id=entry_id).delete()
            session.add(DBEmbedding(
                belonging_paper_entry_id=entry_id,
                content=embedding_128d,
            ))

        # Citation and reference links, one insert per table.
        # set() drops duplicate ids, which ON CONFLICT cannot handle inside one statement.
        citation_rows = [
            {"belonging_paper_entry_id": entry_id, "cited_paper_entry_id": cid}
            for cid in set(citation_ids or [])
        ]
        if citation_rows:
            session.execute(
                pg_insert(DBPaperCitation.__table__).values(citation_rows).on_conflict_do_nothing()
            )

        reference_rows = [
            {"belonging_paper_entry_id": entry_id, "referenced_paper_entry_id": rid}
            for rid in set(reference_ids or [])
        ]
        if reference_rows:
            session.execute(
                pg_insert(DBPaperReference.__table__).values(reference_rows).on_conflict_do_nothing()
            )

        # Keep the stored citation count in sync with paper_citation (used for sort=citations)
        session.execute(
            update(DBPaper)
            .where(DBPaper.entry_id == entry_id)
            .values(arxiv_citation_count=(
                select(func.count())
                .select_from(DBPaperCitation.__table__)
                .where(DBPaperCitation.belonging_paper_entry_id == entry_id)
                .scalar_subquery()
            ))
        )

        session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save processed paper {entry_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    # docker compose runs this file once before main.py as a connection check
    try:
        with engine.connect():
            logger.info("Connection to database successful.")
    except Exception as e:
        logger.error(f"Connection failed: {e}")
