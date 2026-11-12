from dataclasses import dataclass
from Database.db_models import DBPaperRelation



"""
20-August-2025 - Lenio
Abstract: Represents a relation between two papers
Variables:
- source_id: str -> The ID of the first paper of this relation
- target_id: str -> The ID of the second paper that relates to the first
- confidence: float -> A float representing the confidence level of the relation
Suggestion for later: Consider adding more fields like relation type, context, etc. for better relation
"""
@dataclass
class Relation:
    source_id: str
    target_id: str
    confidence: float


    """
    20-August-2025 - Lenio
    Abstract: Converts the Relation object to a SQLAlchemy model.
    Args: DBPaperRelation: SQLAlchemy model class for the paper.
    Returns: DBPaper -> An instance of the SQLAlchemy model with the paper's data.
    """
    def to_db_model(self):
        return DBPaperRelation(
            source_id=self.source_id,
            target_id=self.target_id,
            confidence=self.confidence
        )

