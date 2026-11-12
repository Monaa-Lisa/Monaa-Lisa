import arxiv as arx
from object.paper import Paper
from util.logger import Logger
import os
from SemanticPaper.api.rate_limiter import RateLimiter
from config import cfg
from typing import Optional

"""
Original File by Basti - 04-May-2025
Refactored into a class by Lenio - 20-September-2025
Abstract: This class provides methods to interact with the arXiv API, including fetching papers by category,
fetching the latest paper, and reading paper metadata.
"""
class ArxivAPI:

    def __init__(self):
        self.logger = Logger("ArxivAPI")
        self.client = arx.Client()
        _interval = cfg.get_float("semanticpaper", "arxiv_min_interval", float(os.getenv("ARXIV_MIN_INTERVAL", "3.0")))
        self.rate_limiter = RateLimiter(min_interval=_interval)


    """
    29-September-2025 - Lenio
    Abstract: Returns the rate limiter instance.
    Returns: RateLimiter instance
    """
    def get_rate_limiter(self) -> RateLimiter:
        return self.rate_limiter

    """
    04-May-2025 - Basti
    Abstract: Retrieves a paper and prints out its metadata
    Args:
        - paper: The current paper to be read out
    
    Returns: Metadata of the provided Paper
    """
    def read_meta(self, paper: Paper):
        if paper:
            self.logger.info(f"Title: {paper.title}\n")
            self.logger.info(f"Authors: {', '.join(str(author) for author in paper.authors)}\n")
            self.logger.info(f"Published: {paper.published}\n")
            self.logger.info(f"Abstract: {paper.abstract}\n")
            self.logger.info(f"PDF URL: {paper.url}\n")
            self.logger.info(f"Entry ID: {paper.entry_id}\n")


        else:
            self.logger.error("No Paper!")

    """
    04-May-2025 - Basti
    Updated 30 09 Nico
    Abstract: Takes one paper from the cs.CG category and proceeds to retrieve the newest paper from that category
    Args: None 
    Returns: One arXiv paper -> Result or None
    """
    def fetch_latest_paper(self) -> Optional[Paper]:
        self.rate_limiter.wait()
        search = arx.Search(
            query=f"cat:cs.CG",
            max_results=1,
            sort_by=arx.SortCriterion.SubmittedDate,
            sort_order=arx.SortOrder.Descending
        )
        results = list(self.client.results(search))
        return Paper.from_arxiv(results[0]) if results else None

    """
    30-09 Nico Komplett refactored benutzt jetzt unseren erstellten Client mit Rate limiting auth usw
    Abstract: Fetches a x amount of papers in y category
    Args:
    
    - category: Category from one of arXiv's category
    - amount: Amount of papers to be fetched starting from the newest papers
    
    Returns: List -> of fetches papers
    """
    def fetch_papers(self, category: str = "cs.CG", amount: int = 10) -> list:
        self.rate_limiter.wait()
        search = arx.Search(
            query=f"cat:{category}",
            max_results=amount,
            sort_by=arx.SortCriterion.SubmittedDate,
            sort_order=arx.SortOrder.Descending
        )
        papers: list[Paper] = [] # Typisieren wenn es geht hilft beim Coding
        for result in self.client.results(search):
            # 15-December-2025 - Lenio - Question: Why do we wait here again?
            self.rate_limiter.wait()
            if result:
                paper = Paper.from_arxiv(result)
                # TODO: Need to rework category assignment, since arxiv api returns multiple categories
                paper.categories = category
                papers.append(paper)
            else:
                papers.append(None)
        return papers

    """
    15-December-2025 - Lenio
    Abstract: Fetches papers by their arXiv IDs.
    Args:
    - arxiv_ids: List of arXiv IDs to fetch papers for.
    Returns: List of Paper objects corresponding to the provided arXiv IDs.
    """
    def fetch_papers_by_ids(self, arxiv_ids: list[str]) -> list[Paper]:
        self.rate_limiter.wait()
        search = arx.Search(id_list=arxiv_ids)
        papers: list[Paper] = []
        for result in self.client.results(search):
            if result:
                paper = Paper.from_arxiv(result)
                # TODO: Need to rework category assignment, since arxiv api returns multiple categories
                paper.categories = result.primary_category
                papers.append(paper)
            else:
                papers.append(None)
        return papers

    def fetch_historical_batch(self, category: str, batch_size: int = 50, start_offset: int = 0) -> tuple[list[Paper], bool]:
        self.rate_limiter.wait()
        try:
            # Ask for enough results to reach the desired offset without materializing all
            total_needed = start_offset + batch_size
            search = arx.Search(
                query=f"cat:{category}",
                max_results=total_needed,
                sort_by=arx.SortCriterion.SubmittedDate,
                sort_order=arx.SortOrder.Ascending
            )
            results_iter = self.client.results(search)

            # Skip up to start_offset results without storing them
            skipped = 0
            try:
                while skipped < start_offset:
                    next(results_iter)
                    skipped += 1
            except StopIteration:
                # Nothing left at or beyond this offset
                self.logger.info(f"No more historical results for {category} at offset {start_offset}")
                return [], False

            papers: list[Paper] = []
            for _ in range(batch_size):
                try:
                    result = next(results_iter)
                except StopIteration:
                    break
                if result:
                    paper = Paper.from_arxiv(result)
                    paper.categories = category
                    papers.append(paper)

            has_more = len(papers) == batch_size
            self.logger.info(f"Fetched {len(papers)} historical papers for {category} (offset: {start_offset})")
            return papers, has_more

        except Exception as e:
            self.logger.error(f"Error fetching historical batch for {category}: {e}")
            return [], False
