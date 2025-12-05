from dataclasses import dataclass
from typing import List, Optional, Dict
from Database.db_models import DBReference



"""
29-July-2025 - Lenio
Abstract: Represents a reference found in a paper
Variables:
- belonging_paper_id: str -> The ID of the paper this reference belongs to
- title: str -> The title of the reference paper
Suggestion for later: Consider adding more fields like authors, publication date, etc. for better reference management.
"""
@dataclass
class Reference:
    belonging_paper_id: str
    title: str


    """
    26-July-2025 - Lenio
    Abstract: Converts the Paper object to a SQLAlchemy model.
    Args: DBPaper: SQLAlchemy model class for the paper.
    Returns: DBPaper -> An instance of the SQLAlchemy model with the paper's data.
    """
    def to_db_model(self):
        return DBReference(
            belonging_paper_entry_id=self.belonging_paper_id,
            title=self.title
        )

    def try_query_belonging_paper(self):
        if self.title:
            print(self.title)
