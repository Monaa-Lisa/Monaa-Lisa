import json
import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, cast, List
import numpy as np
import requests
from pymupdf import pymupdf


from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
from Database.db_models import db_base, DBPaper, DBPaperRelation, DBEmbedding, ProgramRun, HistoricalCompletion
from object.paper import Paper
from object.relation import Relation
from util.logger import Logger

from object.embedding import Embedding

# os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

load_dotenv()

logger = Logger("Database")

class DatabaseTimeout(Exception):
    pass

@contextmanager  
def db_timeout(seconds=30):

    try:
        yield
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['timeout', 'connection', 'pool']):
            raise DatabaseTimeout(f"Database operation failed (likely timeout): {e}")
        raise e

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,  # Limit concurrent connections
    max_overflow=10,  # Maximum additional connections
    pool_timeout=30,  # Timeout when getting connection from pool
    echo=bool(os.getenv("DATABASE_DEBUG", True)),
    connect_args={
        "connect_timeout": 30,
        "application_name": "MonaaLisa-SemanticPaper",
        "options": "-c statement_timeout=60000 -c idle_in_transaction_session_timeout=30000"
    }
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def log_pool_status():
    pool = engine.pool
    logger.debug(f"DB Pool - Size: {pool.size()}, Checked out: {pool.checkedout()}, "
                f"Overflow: {pool.overflow()}, Invalid: {pool.invalidated()}")

import threading
import time

def pool_monitor():
    while True:
        time.sleep(60)  
        log_pool_status()

if os.getenv("DATABASE_POOL_MONITORING", "false").lower() == "true":
    monitor_thread = threading.Thread(target=pool_monitor, daemon=True)
    monitor_thread.start()


"""
05-August-2025 - Lenio
Abstract: Fetches all embeddings from the database and returns them as a dictionary.
Returns: A dictionary where keys are paper entry IDs and values are Embedding objects.
"""
def get_all_embeddings(limit=1000):
    session = SessionLocal()
    try:
        with db_timeout(60): 
            # Add limit and timeout to prevent hanging on large datasets
            db_embeddings_rows = (
                session.query(DBEmbedding)
                .filter(DBEmbedding.content.isnot(None))
                .order_by(DBEmbedding.id.desc())  
                .limit(limit)
                .all()
            )
            # Get rid of the warning in pycharm
            db_embeddings = cast(List[DBEmbedding], db_embeddings_rows)
            embedding_dict = {
                db_embedding.belonging_paper_entry_id: Embedding.from_db(db_embedding)
                for db_embedding in db_embeddings if db_embedding.content is not None
            }
            logger.info(f"Loaded {len(embedding_dict)} embeddings from database")
            return embedding_dict
    except DatabaseTimeout as e:
        logger.error(f"Timeout loading embeddings: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error loading embeddings: {e}")
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
    
    try:
        with db_timeout(45):  
            if paper_exists(session, paper.hash):
                logger.info(f"Paper already exists in DB: {paper.title} (hash: {paper.hash})")
                return True

            db_paper = paper.to_db_model()
            logger.info("hash: " + paper.hash)
            db_paper.hash = paper.hash
            session.add(db_paper)

            # Flush the session to save the paper and make its ID available for foreign keys
            try:
                session.flush()
            except Exception as e:
                logger.error(f"DB error on flush: {e}")
                session.rollback()
                return False

            # in the future when we have more calls to grobid this should not happen but rather in a sooner step so we process each paper only once
            references = paper.references if paper.references else []
            for ref in references:
                db_reference = ref.to_db_model()
                logger.info(f"Adding reference to DB: {db_reference.title}")
                session.add(db_reference)
            if paper.embedding is not None:
                db_embedding = paper.embedding.to_db_model()
                logger.info(f"Adding embedding to DB for paper: {paper.title}")
                session.add(db_embedding)

            try:
                session.commit()
                logger.info(f"Saved paper to DB: {paper.title}")
                return True
            except Exception as e:
                logger.error(f"DB error: {e}")
                session.rollback()
                return False
                
    except DatabaseTimeout as e:
        logger.error(f"Timeout saving paper {paper.title}: {e}")
        session.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving paper {paper.title}: {e}")
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
        with db_timeout(30): 
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
    except DatabaseTimeout as e:
        logger.error(f"Timeout saving paper relation: {e}")
        session.rollback()
        return False
    except Exception as e:
        logger.error(f"DB error saving paper relation: {e}")
        session.rollback()
        return False
    finally:
        session.close()

"""
25-May-2025 - Basti
Abstract: Checks if a paper hash already exists in the database
Args:
- session: -> Current database session
- paper_hash: -> the hash of the given arXiv paper
Returns: bool -> True if: query of the paper is not Null/None | False if: query of the paper is None 
"""
def paper_exists(session, paper_hash):
    return session.query(DBPaper).filter_by(hash=paper_hash).first() is not None


"""
20-August-2025 - Lenio
Abstract: Checks if a relation between two papers already exists in the database.
Args:
- session: The current database session.
- source_id: The ID of the first paper.
- target_id: The ID of the second paper.
Returns: bool -> True if the relation exists, False otherwise.
"""
def relation_exists(session, source_id: str, target_id: str):
    # Check if the relation exists in either direction
    relation1 = session.query(DBPaperRelation).filter_by(source_id=source_id, target_id=target_id).first()
    relation2 = session.query(DBPaperRelation).filter_by(source_id=target_id, target_id=source_id).first()
    return relation1 is not None or relation2 is not None

"""
25-May-2025 - Basti
Abstract: (for future development) - 
Args:
- None
Returns: 
"""
@FutureWarning
def update_paper_references(paper_id, related_papers, citations):
    session = SessionLocal()
    try:
        paper = session.query(DBPaper).filter_by(entry_id=paper_id).first()
        if paper:
            paper.related_papers = related_papers
            paper.citations = citations
            session.commit()
            logger.info(f"Updated references for paper: {paper.title}")
            return True
        else:
            logger.warning(f"Paper with ID {paper_id} not found for reference update")
            return False
    except Exception as e:
        logger.error(f"DB error updating references: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    logger.info("Creating database tables...")
    db_base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully!")

"""
13-August-2025 - Basti
Abstract: Creates a new program run record and returns its ID.
"""
def create_program_run():
    session = SessionLocal()
    try:
        # Deactivate any prior runs
        session.query(ProgramRun).filter_by(is_active="true").update({"is_active": "false"})
        run = ProgramRun(start_date=datetime.now(), is_active="true")
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
13-August-2025 - Basti
Abstract: Marks a category as completed historically for this run.
"""
def mark_category_historically_completed(program_run_id, category, oldest_paper_date=None):

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
        record.end_date = datetime.now()
        record.oldest_paper_date = oldest_paper_date
        session.commit()
        logger.info(f"Completed historical fetch for {category} in run {program_run_id}")
        return True
    except Exception as e:
        logger.error(f"Error marking completion: {e}")
        session.rollback()
        return False
    finally:
        session.close()

"""
30-August-2025 - Basti
Abstract: Starts historical fetch tracking for a category.
"""
def start_category_historical_fetch(program_run_id, category):
    session = SessionLocal()
    try:
        existing = (
            session.query(HistoricalCompletion)
            .filter_by(program_run_id=program_run_id, category=category)
            .filter(HistoricalCompletion.end_date.is_(None))
            .first()
        )
        
        if existing:
            logger.debug(f"Historical fetch already started for {category} in run {program_run_id}")
            return True
            
        record = HistoricalCompletion(
            program_run_id=program_run_id,
            category=category,
            start_date=datetime.now()
        )
        session.add(record)
        session.commit()
        logger.info(f"Started historical fetch for {category} in run {program_run_id}")
        return True
    except Exception as e:
        logger.error(f"Error starting historical fetch: {e}")
        session.rollback()
        return False
    finally:
        session.close()
