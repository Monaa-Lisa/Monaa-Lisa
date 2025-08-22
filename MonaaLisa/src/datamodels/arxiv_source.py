# Nico
from typing import List
import requests # TODO: potentially implement own solution for requests
from .models import Publication
from datetime import datetime
from .data_source import DataSource

class ArxivSource(DataSource):
    def fetch_publications(self, query: str, max_results: int = 5) -> List[Publication]:
        '''
        retrieves all publications matching query from ArXiv
        
        Raises:
            Exception: When the response status != 200
        '''
        url = f'http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_results}'
        response = requests.get(url)
        
        if response.status_code != 200: # 200 = OK
            raise Exception(f"Error fetching data from Arxiv: {response.status_code}")
        
        return self.parse_publications(response.text)

    def parse_publications(self, raw_data: str) -> List[Publication]:
        from xml.etree import ElementTree as ET
        root = ET.fromstring(raw_data)
        
        publications = [] # List of all pubs
        
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"): # First iterate through all entries
            title = entry.find("{http://www.w3.org/2005/Atom}title").text # Get all titles
            authors = [author.find("{http://www.w3.org/2005/Atom}name").text for author in entry.findall("{http://www.w3.org/2005/Atom}author")] # Then the authors
            summary = entry.find("{http://www.w3.org/2005/Atom}summary").text
            published = entry.find("{http://www.w3.org/2005/Atom}published").text
            url = entry.find("{http://www.w3.org/2005/Atom}id").text
            
            # Convert published date to datetime object
            published_datetime = datetime.fromisoformat(published.replace("Z", "+00:00"))
            
            publication = Publication(title, authors, summary, published_datetime, url)
            publications.append(publication)
        
        return publications