from datetime import datetime
from util.logger import Logger

logger = Logger("arxiv_result")

class SimpleResult:
    """
    A simplified result object that mimics the arxiv library's Result class
    for compatibility with Paper.from_arxiv() method.
    
    This class is used to convert feedparser entries from direct arXiv API calls
    into a format that the existing Paper creation logic can handle.
    """
    
    def __init__(self, entry):
        """
        Initialize SimpleResult from a feedparser entry.
        
        Args:
            entry: A feedparser entry from arXiv API response
        """
        try:
            self.entry_id = entry.id.split('/')[-1]
            
            self.title = entry.title if hasattr(entry, 'title') else ""
            self.summary = entry.summary if hasattr(entry, 'summary') else ""
            
            if hasattr(entry, 'authors') and entry.authors:
                self.authors = [
                    author.name if hasattr(author, 'name') else str(author) 
                    for author in entry.authors
                ]
            else:
                self.authors = []
            
            if hasattr(entry, 'published') and entry.published:
                try:
                    self.published = datetime.strptime(entry.published, '%Y-%m-%dT%H:%M:%SZ')
                except ValueError as e:
                    logger.warning(f"Could not parse published date '{entry.published}': {e}")
                    self.published = datetime.now()
            else:
                self.published = datetime.now()
            
            self.pdf_url = entry.id.replace('/abs/', '/pdf/') + '.pdf'
            
        except Exception as e:
            logger.error(f"Error initializing SimpleResult from entry {getattr(entry, 'id', 'unknown')}: {e}")
            self.entry_id = "unknown"
            self.title = ""
            self.summary = ""
            self.authors = []
            self.published = datetime.now()
            self.pdf_url = ""
