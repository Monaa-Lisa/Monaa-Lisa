import os
import sys
from datetime import datetime, timezone
from typing import cast, List
from sqlalchemy import create_engine, or_, and_, exists, select, update
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from config import cfg
from sqlalchemy.exc import ProgrammingError
from Database.db_models import db_base, DBPaper, DBPaperRelation, DBEmbedding, ProgramRun, HistoricalCompletion, DBUncaughtPaper
from object.paper import Paper
from object.relation import Relation
from util.logger import Logger

from object.embedding import Embedding
# Imports für Typ-Prüfung bei Relationen
from object.paper_reference import PaperReference
from object.paper_citation import PaperCitation

# os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

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
05-August-2025 - Lenio
Abstract: Fetches all embeddings from the database and returns them as a dictionary.
Returns: A dictionary where keys are paper entry IDs and values are Embedding objects.
"""
def get_all_embeddings():
    session = SessionLocal()
    try:
        limit = cfg.get_int(
            "semanticpaper",
            "embeddings_preload_limit",
            int(os.getenv("EMBEDDINGS_PRELOAD_LIMIT", "5000"))
        )
        q = session.query(DBEmbedding)
        if limit > 0:
            q = q.limit(limit)
        try:
            db_embeddings_rows = q.all()
        except ProgrammingError as e:
            logger.warning(f"Embeddings table missing or not initialized yet: {e}")
            return {}
        # Get rid of the warning in pycharm
        db_embeddings = cast(List[DBEmbedding], db_embeddings_rows)
        embedding_dict = {
            db_embedding.belonging_paper_entry_id: Embedding.from_db(db_embedding)
            for db_embedding in db_embeddings if db_embedding.content is not None
        }
        return embedding_dict
    finally:
        session.close()


"""
20-December-2025 - Basti - Refactor for the supervised UMAP
Abstract: Returns a mapping of paper entry_id to its arXiv category for supervised reducers.
Args:
- limit: optional limit mirroring embedding preload limits to avoid excessive memory use
Returns: Dict[str, str | None]
"""
def get_embedding_labels(limit: int | None = None) -> dict[str, str | None]:
    session = SessionLocal()
    try:
        q = session.query(DBPaper.entry_id, DBPaper.categories).filter(DBPaper.categories.isnot(None))
        if limit is not None:
            q = q.limit(limit)
        rows = q.all()
        return {entry_id: categories for entry_id, categories in rows if entry_id}
    except Exception as e:
        logger.error(f"Failed to load embedding labels: {e}")
        return {}
    finally:
        session.close()

"""
25-May-2025 - Basti
Abstract: Saves one given arXiv paper into the Postgres database
Args:
- paper: The given arXiv paper
Returns: bool -> True if: paper was successfully committed to the database | False if: commit failed/Exception occured
21-August-2025 - Lenio
Annotation: Removed redundant parameters hash and date, these should come from the paper object.
"""

def save_paper_to_db(paper: Paper):
    session = SessionLocal()

    # 1. Check if paper already exists (by entry_id)
    if paper_exists(session, paper):
        logger.info(f"Paper already exists in DB: {paper.title}")
        session.close()
        return True

    try:
        # 2. Check if paper exists as a Stub (by entry_id)
        existing_paper = session.query(DBPaper).filter_by(entry_id=paper.entry_id).first()

        if existing_paper:
            logger.info(f"Updating existing stub/paper: {paper.title}")
            existing_paper.title = paper.title
            existing_paper.authors = ", ".join(paper.authors)
            existing_paper.abstract = paper.abstract
            existing_paper.published = paper.published
            existing_paper.categories = paper.categories
            existing_paper.tsne = json.dumps(paper.tsne) if paper.tsne else None
            existing_paper.url = paper.url
        else:
            # Insert new paper
            db_paper = paper.to_db_model()
            session.add(db_paper)

        # Flush to ensure the paper (or update) is applied before we add relations
        session.flush()

        # 3. Handle Missing Targets for Relations (Create Stubs)
        # This ensures that referenced papers exist in the DB so Foreign Keys don't fail
        references = paper.references if paper.references else []
        citations = paper.citations if paper.citations else []

        needed_ids = set()

        # Collect IDs from PaperReference and PaperCitation objects
        for ref in references:
            if isinstance(ref, PaperReference):
                needed_ids.add(ref.referenced_paper_id)

        for cite in citations:
            if isinstance(cite, PaperCitation):
                needed_ids.add(cite.cited_paper_id)

        if needed_ids:
            # Find which ones are missing in DB
            existing_stubs = session.query(DBPaper.entry_id).filter(DBPaper.entry_id.in_(needed_ids)).all()
            found_ids = {r.entry_id for r in existing_stubs}

            missing_ids = needed_ids - found_ids

            if missing_ids:
                logger.info(f"Creating {len(missing_ids)} stubs for missing relations...")
                for mid in missing_ids:
                    stub = DBPaper(
                        entry_id=mid,
                        title="[STUB] Pending Fetch",
                    )
                    session.add(stub)
                session.flush()

        # 4. Save Relations
        for ref in references:
            db_reference = ref.to_db_model()
            session.add(db_reference)

        for cite in citations:
            db_citation = cite.to_db_model()
            session.add(db_citation)

        # 5. Handle Embedding
        if paper.embedding is not None:
            # Remove existing embedding if we are updating a stub/paper to avoid unique constraint violation
            session.query(DBEmbedding).filter_by(belonging_paper_entry_id=paper.entry_id).delete()

            db_embedding = paper.embedding.to_db_model()
            logger.info(f"Adding embedding to DB for paper: {paper.title}")
            session.add(db_embedding)

        session.commit()
        logger.info(f"Saved paper to DB: {paper.title}")
        return True

    except Exception as e:
        logger.error(f"DB error: {e}")
        session.rollback()
        return False
    finally:
        session.close()

"""
20-August-2025 - Lenio & Reviewed by Nico
Abstract: Saves a relation between two papers in the database.
Args:
PaperRelation: The relation object containing source_id, target_id, and confidence.
"""
def save_paper_relation(paper_relation: Relation):
    session = SessionLocal()
    try:
        if not relation_exists(session, paper_relation.source_id, paper_relation.target_id):
            db_paper_relation = paper_relation.to_db_model()
            session.add(db_paper_relation)
            session.commit()
            logger.info(
                f"Saved paper relation: {paper_relation.source_id} -> "
                f"{paper_relation.target_id} with confidence {paper_relation.confidence}"
            )
            return True
        else:
            logger.info(
                f"Relation already exists: {paper_relation.source_id} -> {paper_relation.target_id}"
            )
            return True
    except Exception as e:
        logger.error(f"DB error saving paper relation: {e}")
        session.rollback()
        return False
    finally:
        session.close()

"""
14-Dec 2025 - Basti
Abstract: We can not "freeze" the papers location in the DB when we save them, because the t-SNE/UMAP projection
may be calculated later. This function updates the projection field of a paper in the DB.
Args:
- entry_id: The entry_id of the paper to update
- projection: The new projection dict to set
Returns: bool -> True if update was successful, False otherwise
"""
def update_paper_projection(entry_id: str, projection: dict) -> bool:
    session = SessionLocal()
    try:
        result = session.execute(
            update(DBPaper)
            .where(DBPaper.entry_id == entry_id)
            .values(tsne=projection)
        )
        if result.rowcount == 0:
            logger.warning(f"No paper found to update projection for entry_id={entry_id}")
            session.rollback()
            return False
        session.commit()
        logger.info(f"Updated projection for paper {entry_id}")
        return True
    except Exception as e:
        logger.error(f"Failed updating projection for {entry_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def get_entry_ids_missing_projection(limit: int | None = None) -> list[str]:
    session = SessionLocal()
    try:
        query = session.query(DBPaper.entry_id).filter(DBPaper.tsne.is_(None))
        if limit is not None:
            query = query.limit(limit)
        rows = query.all()
        return [row[0] for row in rows if row[0] is not None]
    except Exception as e:
        logger.error(f"Failed to fetch papers missing projection: {e}")
        return []
    finally:
        session.close()

"""
25-May-2025 - Basti - Tweaked 30-September-2025 - Lenio
Abstract: Checks if a paper hash already exists in the database
Args:
- session: -> Current database session
- paper: -> the paper object to check for
Returns: bool -> True if: query of the paper is not Null/None | False if: query of the paper is None

Tweak:
Previously this only checked if the hash is saved into the database, now it checks via the unique entry_id of the paper.
This is necessary because A) hash collisions are possible (though unlikely) and B) the entry_id is a unique field in the DB so it is more reliable.

Additionally:
Checking by hash could be a way of checking for updates to a paper, but that is not implemented yet.
"""
def paper_exists(session, paper: Paper):
    return session.query(DBPaper).filter_by(entry_id=paper.entry_id).first() is not None


""" 28.09. Nico
    Prüft, ob eine Relation zwischen zwei Paper-IDs existiert, 
    unabhängig von der Richtung (source_id ↔ target_id).

    Hintergrund:
    - Frühere Implementierung führte zwei separate SQL-Abfragen aus 
      und lieferte vollständige Zeilen zurück.
    - Diese Version kombiniert beide Bedingungen in einer Abfrage mit OR 
      und nutzt `EXISTS`, um direkt ein Boolean-Ergebnis zu erzeugen.

    SQL-Äquivalent:
        SELECT EXISTS (
            SELECT 1
            FROM paper_relation
            WHERE (source_id = :source_id AND target_id = :target_id)
               OR (source_id = :target_id AND target_id = :source_id)
        );
    """
def relation_exists(session, source_id: str, target_id: str):
    # 29.09.25 Nico - Verbesserte Version der Abfrage. Aktuell werden 2 SQL Befehle ausgeführt (nicht effizient) dabei kann man das in einem Befehl mit OR kombinieren.
    # Die Variante mit beiden Befehlen liefert auch die kompletten Zeilen obwohl man am Ende nur ein Boolean generieren möchte

    # Check if the relation exists in either direction
    sql_statement = select(exists().where(
        or_(
            and_(DBPaperRelation.source_id == source_id, DBPaperRelation.target_id == target_id),
            and_(DBPaperRelation.source_id == target_id, DBPaperRelation.target_id == source_id),
        )
    ))
    return bool(session.execute(sql_statement).scalar())

"""
13-August-2025 - Basti
Abstract: Creates a new program run record and returns its ID.
"""
def create_program_run():
    session = SessionLocal()
    try:
        session.query(ProgramRun).filter_by(is_active="true").update({"is_active": "false"})
        run = ProgramRun(start_date=datetime.now(timezone.utc).replace(tzinfo=None), is_active="true")
        session.add(run)
        session.commit()
        logger.info(f"Created ProgramRun ID: {run.id}")
        return run.id
    except Exception as e:
        logger.error(f"Error creating program run: {e}")
        session.rollback()
        return None
    finally:
        session.close()


"""
20-December-2025 - Basti
Abstract: Checks whether a program run exists.
"""
def program_run_exists(run_id: int) -> bool:
    session = SessionLocal()
    try:
        return session.query(ProgramRun.id).filter_by(id=run_id).first() is not None
    except Exception as e:
        logger.error(f"Error checking program run existence: {e}")
        return False
    finally:
        session.close()


"""
Abstract: Reactivates an existing program run and deactivates the others.
Returns: bool -> True if the run was reactivated, False otherwise.
"""
def set_active_program_run(run_id: int) -> bool:
    session = SessionLocal()
    try:
        if session.query(ProgramRun.id).filter_by(id=run_id).first() is None:
            return False
        session.query(ProgramRun).update({"is_active": "false"})
        session.query(ProgramRun).filter_by(id=run_id).update({"is_active": "true"})
        session.commit()
        logger.info(f"Reactivated ProgramRun ID: {run_id}")
        return True
    except Exception as e:
        logger.error(f"Error reactivating program run {run_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

"""
13-August-2025 - Basti
Abstract: Checks if a category is already completed historically in this run.
"""
def is_category_historically_completed(program_run_id, category):
    session = SessionLocal()
    try:
        record = (
            session.query(HistoricalCompletion)
            .filter_by(program_run_id=program_run_id, category=category)
            .filter(HistoricalCompletion.end_date.isnot(None))
            .first()
        )
        return record is not None
    except Exception as e:
        logger.error(f"Error checking completion: {e}")
        return False
    finally:
        session.close()

"""
21-September-2025 - Basti
Abstract: Converts a datetime to naive UTC (if no timezone info)
Args: dt: datetime 
Returns: datetime in UTC without tzinfo or None if input was None
"""
def _to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    try:
        if dt.tzinfo is not None and dt.utcoffset() is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return dt

"""
13-August-2025 - Basti
Abstract: Ensures a HistoricalCompletion start record exists for a category in this run.
Optionally sets the goal oldest paper date.
"""
def ensure_historical_start(program_run_id, category, goal_oldest_paper_date: datetime | None = None):
    session = SessionLocal()
    try:
        normalized_goal = _to_naive_utc(goal_oldest_paper_date)
        record = (
            session.query(HistoricalCompletion)
            .filter_by(program_run_id=program_run_id, category=category)
            .order_by(HistoricalCompletion.start_date.desc())
            .first()
        )
        if record is None or record.end_date is not None:
            new_rec = HistoricalCompletion(
                program_run_id=program_run_id,
                category=category,
                start_date=datetime.now(),
                goal_oldest_paper_date=normalized_goal,
            )
            session.add(new_rec)
            session.commit()
            logger.info(f"Started historical fetch for {category} in run {program_run_id}")
        elif record.goal_oldest_paper_date is None and normalized_goal is not None:
            record.goal_oldest_paper_date = normalized_goal
            session.commit()
        return True
    except Exception as e:
        logger.error(f"Error ensuring historical start: {e}")
        session.rollback()
        return False
    finally:
        session.close()

"""
13-August-2025 - Basti
Abstract: Updates progress for a category's historical fetch with the current oldest fetched date.
"""
def update_historical_progress(program_run_id, category, oldest_seen_date: datetime | None):
    session = SessionLocal()
    try:
        record = (
            session.query(HistoricalCompletion)
            .filter_by(program_run_id=program_run_id, category=category)
            .order_by(HistoricalCompletion.start_date.desc())
            .first()
        )
        if not record:
            logger.error(f"No start entry to update for {category} in run {program_run_id}")
            return False
        # Keep storing any incidental progress-related state here in future if needed.
        # Intentionally not toggling goal_reached anymore.
        session.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating historical progress: {e}")
        session.rollback()
        return False
    finally:
        session.close()

"""
13-August-2025 - Basti
Updated: 20-September-2025 - Align semantics
Abstract: Marks a category as completed historically for this run.
Behavior: Sets end_date and marks goal_reached = true with reached_date = now,
          treating "goal" as completion of historical ingestion.
"""
def mark_category_historically_completed(program_run_id, category, oldest_seen_date=None):
    session = SessionLocal()
    try:
        record = (
            session.query(HistoricalCompletion)
            .filter_by(program_run_id=program_run_id, category=category)
            .order_by(HistoricalCompletion.start_date.desc())
            .first()
        )
        if not record:
            logger.error(f"No start entry to complete for {category} in run {program_run_id}")
            return False
        record.end_date = datetime.now(timezone.utc).replace(tzinfo=None)
        if record.goal_reached != "true":
            record.goal_reached = "true"
            record.reached_date = datetime.now()
        session.commit()
        logger.info(f"Completed historical fetch for {category} in run {program_run_id}")
        return True
    except Exception as e:
        logger.error(f"Error marking completion: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    # Tabellen werden nur noch über Prisma gebaut nicht mehr über SQLAlchemy, daher ist dieser Schritt hier nicht mehr nötig.
    #logger.info("Creating database tables...")
    #db_base.metadata.create_all(bind=engine)
    #logger.info("Tables created successfully!")
    try:
        with engine.connect() as conn:
            logger.info("Connection to database successful.")
    except Exception as e:
        logger.error(f"Connection failed: {e}")


# ---------------------------------------------------------------------------
# New functions for the refactored pipeline – feb 2026 – Basti
# ---------------------------------------------------------------------------


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
        from sqlalchemy import func as sa_func
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
Abstract: Checks if a paper with the given entry_id exists in the paper table.
Args:
- entry_id: str
Returns: bool
"""
def paper_exists_by_id(entry_id: str) -> bool:
    session = SessionLocal()
    try:
        return session.query(DBPaper.id).filter_by(entry_id=entry_id).first() is not None
    except Exception:
        return False
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
        tsne_val = None
        if tsne_x is not None and tsne_y is not None:
            import json
            tsne_val = json.dumps({"x": tsne_x, "y": tsne_y, "method": "umap"})

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

        # Citation links
        for cid in (citation_ids or []):
            try:
                stmt = pg_insert(DBPaperCitation.__table__).values(
                    belonging_paper_entry_id=entry_id, cited_paper_entry_id=cid
                ).on_conflict_do_nothing()
                session.execute(stmt)
            except Exception:
                pass

        # Reference links
        for rid in (reference_ids or []):
            try:
                stmt = pg_insert(DBPaperReference.__table__).values(
                    belonging_paper_entry_id=entry_id, referenced_paper_entry_id=rid
                ).on_conflict_do_nothing()
                session.execute(stmt)
            except Exception:
                pass

        session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to save processed paper {entry_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()
