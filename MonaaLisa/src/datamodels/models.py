from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class Publication:
    '''
    Basic information that every publication has.
    Includes name, author, year, title, etc.
    Makes it easier to examine corresponding data in isolation.
    '''
    title: str
    authors: List[str]
    summary: str
    published: datetime
    url: str

    def to_json(self) -> dict:
        '''
        Returns the JSON representation of Publication as dictionary
        '''
        return {
            "title": self.title,
            "authors": self.authors,
            "summary": self.summary,
            "published": self.published.isoformat(), # self.published cannot be stringified directly, so use iso format
            "url": self.url
        }
        