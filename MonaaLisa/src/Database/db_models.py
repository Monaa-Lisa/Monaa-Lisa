"""
SQLAlchemy models for the tables the Python pipeline reads and writes.

The tables are created by the SQL migrations in db/migrations (dbmate), so
these classes only describe them, they are never used to create tables.
Keep them in sync with the migrations.
"""
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

db_base = declarative_base()


class DBPaper(db_base):
    """One arXiv paper with its metadata and 2-D map position."""
    __tablename__ = "paper"
    id = Column(Integer, primary_key=True)
    entry_id = Column(String, unique=True, nullable=False)  # arXiv id without version, e.g. 2401.00001
    title = Column(String, nullable=False)
    authors = Column(String, nullable=True)  # comma separated
    abstract = Column(Text, nullable=True)
    categories = Column(String, nullable=True)  # space separated, primary category first
    published = Column(DateTime, nullable=True)
    updated = Column(DateTime, nullable=True)
    doi = Column(String, nullable=True)
    journal_ref = Column(String, nullable=True)
    license = Column(String, nullable=True)
    url = Column(String, nullable=True)
    s2_id = Column(String, nullable=True, unique=True)  # Semantic Scholar paper id
    non_arxiv_citation_count = Column(Integer, nullable=True)
    non_arxiv_reference_count = Column(Integer, nullable=True)
    arxiv_citation_count = Column(Integer, nullable=False, default=0, server_default="0")
    related_arxiv_ids = Column(JSON, nullable=True)
    # UMAP coordinates {"x", "y", "method": "umap"}. The name is left over from t-SNE.
    tsne = Column(JSON, nullable=True)


class DBEmbedding(db_base):
    """The 128-d PCA reduced SPECTER v2 embedding of a paper."""
    __tablename__ = "embedding"
    id = Column(Integer, primary_key=True, autoincrement=True)
    belonging_paper_entry_id = Column(String, unique=True, nullable=False)
    content = Column(Vector(128), nullable=False)


class DBPaperCitation(db_base):
    """
    Citation edge. cited_paper_entry_id is a paper that CITES the belonging paper
    (the name is misleading, see Semantic Scholar's "citations" field).
    The other paper does not have to be in the database.
    """
    __tablename__ = "paper_citation"
    belonging_paper_entry_id = Column(String, primary_key=True)
    cited_paper_entry_id = Column(String, primary_key=True)


class DBPaperReference(db_base):
    """Reference edge: the belonging paper references referenced_paper_entry_id."""
    __tablename__ = "paper_reference"
    belonging_paper_entry_id = Column(String, primary_key=True)
    referenced_paper_entry_id = Column(String, primary_key=True)


class DBUncaughtPaper(db_base):
    """
    Papers Semantic Scholar has no embedding for yet (usually because they are
    very new). They are retried periodically and dropped after max_retries.
    """
    __tablename__ = "uncaught_paper"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=True)
    authors = Column(String, nullable=True)
    abstract = Column(Text, nullable=True)
    categories = Column(String, nullable=True)
    published = Column(DateTime, nullable=True)
    url = Column(String, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=4, nullable=False)
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
