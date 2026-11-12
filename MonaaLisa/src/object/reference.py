from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from Database.db_models import DBReference
from semanticscholar.Paper import Paper

"""
29-July-2025 - Lenio
Abstract: Represents a reference found in a paper
Variables:
- belonging_paper_id: str -> The ID of the paper this reference belongs to
- semantic_scholar_obj -> The original object from Semantic Scholar, in case a paper is not found on arXiv
"""
@dataclass
class Reference:
    belonging_paper_id: str
    semanticscholar_obj: Paper

    """
    24-December-2025 - Lenio
    Converts a semantic scholar Paper object (or list of such objects) to a dictionary.
    Handles nested objects recursively.
    Args:
        obj: A semantic scholar Paper object or a list of such objects.
    Returns:
        dict: A dictionary representation of the Paper object or a list of such dictionaries.
    """
    def semantic_paper_to_dict(self, obj: Paper):
        if isinstance(obj, list):
            return [self.semantic_paper_to_dict(x) for x in obj]
        if hasattr(obj, 'raw_data'):
            return obj.raw_data
        if hasattr(obj, '__dict__'):
            return {k: self.semantic_paper_to_dict(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
        return obj

    """
    26-July-2025 - Lenio
    Abstract: Converts the Reference object to a SQLAlchemy model.
    Returns: 
        DBReference -> An instance of the SQLAlchemy model with the reference's data from Semantic Scholar.
    """
    def to_db_model(self):
        return DBReference(
            belonging_paper_entry_id=self.belonging_paper_id,
            semanticscholar_obj=self.semantic_paper_to_dict(self.semanticscholar_obj)
        )
