from dataclasses import dataclass
import numpy as np

from Database.db_models import DBEmbedding


"""
21-August-2025 - Lenio
Abstract: Represents an embedding in the system, helpful for keeping track of paper embeddings.
Variables:
- belonging_paper_entry_id: str -> The ID of the paper this embedding belongs to.  
- content: np.ndarray -> The content of the embedding, stored as a numpy array.
Suggestion for later: Consider adding more metadata like embedding model version, creation date, etc.
"""
@dataclass
class Embedding:
    belonging_paper_entry_id: str
    content: np.ndarray
    label: str | None = None

    """
    21-August-2025 - Lenio
    Abstract: Converts the Embedding object from an SQLAlchemy model.
    Args: DBEmbedding: SQLAlchemy model class for the embedding.
    Returns: An Embedding object with the content as a numpy array.
    """
    @classmethod
    def from_db(cls, db_embedding: DBEmbedding):
        if db_embedding.content is None:
            raise ValueError("Embedding content cannot be None")
        return cls(
            belonging_paper_entry_id=db_embedding.belonging_paper_entry_id,
            content=np.array(db_embedding.content, dtype=np.float32)
        )

    """
    21-August-2025 - Lenio
    Abstract: Converts the Paper object to a SQLAlchemy model.
    Args: DBPaper: SQLAlchemy model class for the paper.
    Abstract: Converts the Embedding object to a SQLAlchemy model (DBEmbedding).
    Returns: DBEmbedding -> An instance of the SQLAlchemy model with the embedding's data.
    """
    def to_db_model(self):
        return DBEmbedding(
            belonging_paper_entry_id=self.belonging_paper_entry_id,
            content=self.content.tolist() if isinstance(self.content, np.ndarray) else self.content
        )