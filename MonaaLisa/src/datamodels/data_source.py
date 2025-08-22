# Nico
from abc import ABC, abstractmethod
from typing import List
from .models import Publication


class DataSource(ABC): # ABC = abstract base class
    '''
    The DataSource superclass defines a generic interface for fetching and parsing
    publications that is derived from specific data sources.
    It is an ABC, so it's abstract.
    This allows us to create specific classes for arxiv, open-access, etc. that the scraper can then collect.
    '''
    @abstractmethod
    def fetch_publications(self, query: str, max_results: int = 5) -> List[Publication]:
        '''
        Fetches publications with given configs
        '''
    
    @abstractmethod
    def parse_publications(self, raw_data: str) -> List[Publication]:
        '''
        Fetches publications with given configs
        '''
    