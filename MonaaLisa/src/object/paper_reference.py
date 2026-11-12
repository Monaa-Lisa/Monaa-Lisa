from dataclasses import dataclass
from typing import List, Optional, Dict
from Database.db_models import DBPaperReference
from semanticscholar.Paper import Paper

"""
27-December-2025 - Lenio
Abstract: 
    Represents a reference found in a paper
Variables:
- belonging_paper_id: str -> The ID of the paper this reference belongs to
- reference_paper_id: str -> The ID of the referenced paper
"""
@dataclass
class PaperReference:
    belonging_paper_id: str
    referenced_paper_id: str


    """
    27-December-2025 - Lenio
    Abstract: Converts the PaperReference object to a SQLAlchemy model.
    Returns: DBPaperReference -> An instance of the SQLAlchemy model with the ids of each paper in the relationship.
    """
    def to_db_model(self):
        return DBPaperReference(
            belonging_paper_entry_id=self.belonging_paper_id,
            referenced_paper_entry_id=self.referenced_paper_id,
        )

