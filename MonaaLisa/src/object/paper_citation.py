from dataclasses import dataclass
from typing import List, Optional, Dict
from Database.db_models import DBPaperCitation
from semanticscholar.Paper import Paper

"""
23-December-2025 - Lenio
Abstract:
    Represents a citation found in a paper, linking two paper IDs.
Variables:
- belonging_paper_id: str -> The ID of the paper this citation belongs to
- is_arxiv: bool -> Indicates if the citation is present on arXiv
- semantic_scholar_obj -> The original object from Semantic Scholar, in case a paper is not found on arXiv
"""
@dataclass
class PaperCitation:
    belonging_paper_id: str
    cited_paper_id: str


    """
    23-December-2025 - Lenio
    Abstract: 
        Converts the Citation object to a SQLAlchemy model.
    Returns:
        DBPaperCitation -> An instance of the SQLAlchemy model which represents the citation relationship between two papers.
    """
    def to_db_model(self):
        return DBPaperCitation(
            belonging_paper_entry_id=self.belonging_paper_id,
            cited_paper_entry_id=self.cited_paper_id
        )

