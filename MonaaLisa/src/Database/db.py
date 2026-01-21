import json
import os
import sys
from datetime import datetime, timezone
from typing import cast, List
from sqlalchemy import create_engine, or_, and_, exists, select, update
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from config import cfg
from sqlalchemy.exc import ProgrammingError
from Database.db_models import db_base, DBPaper, DBPaperRelation, DBEmbedding, ProgramRun, HistoricalCompletion
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
        q = session.query(DBPaper.entry_id, DBPaper.category).filter(DBPaper.category.isnot(None))
        if limit is not None:
            q = q.limit(limit)
        rows = q.all()
        return {entry_id: category for entry_id, category in rows if entry_id}
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

    # 1. Check if paper is already fully processed (by hash)
    if paper_exists(session, paper):
        logger.info(f"Paper already exists in DB: {paper.title} (hash: {paper.hash})")
        session.close()
        return True

    try:
        # 2. Check if paper exists as a Stub (by entry_id)
        # We use the entry_id to check because stubs have the ID but no Hash
        existing_paper = session.query(DBPaper).filter_by(entry_id=paper.entry_id).first()

        if existing_paper:
            logger.info(f"Updating existing stub/paper: {paper.title}")
            # Update fields of the existing stub
            existing_paper.title = paper.title
            existing_paper.authors = ", ".join(paper.authors)
            existing_paper.summary = paper.abstract
            existing_paper.published = paper.published
            existing_paper.category = paper.category
            existing_paper.tsne = json.dumps(paper.tsne) if paper.tsne else None
            existing_paper.url = paper.url
            existing_paper.hash = paper.hash
            # existing_paper.added remains as is (creation time of stub)
        else:
            # Insert new paper
            db_paper = paper.to_db_model()
            logger.info("hash: " + paper.hash)
            db_paper.hash = paper.hash
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
                    # Create Stub
                    # Hash is None (Postgres allows multiple NULLs in unique columns)
                    # Title indicates it's a placeholder
                    stub = DBPaper(
                        entry_id=mid,
                        added=datetime.now(),
                        title="[STUB] Pending Fetch",
                        hash=None
                    )
                    session.add(stub)
                # Flush stubs so they are available for FK checks immediately
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
    return session.query(DBPaper).filter_by(hash=paper.hash).first() is not None


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
    logger.info("Creating database tables...")
    db_base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully!")
