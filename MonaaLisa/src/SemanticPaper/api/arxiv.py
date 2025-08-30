import arxiv as arx
import feedparser
import requests
import random
import hashlib
import urllib.parse
from datetime import datetime

from object.paper import Paper
from util.logger import Logger
import os
from SemanticPaper.api.rate_limiter import RateLimiter
from SemanticPaper.api.arxiv_result import SimpleResult

logger = Logger("arxiv")

_interval = float(os.getenv("ARXIV_MIN_INTERVAL", "3.0"))
rate_limiter = RateLimiter(min_interval=_interval)

# Funny test comment ! :D

# categories = [
#     # Physics
#     'astro-ph', 'cond-mat', 'gr-qc', 'hep-ex', 'hep-lat', 'hep-ph', 'hep-th',
#     'math-ph', 'nlin', 'nucl-ex', 'nucl-th', 'physics', 'quant-ph',
    
#     # Mathematics
#     'math', 'math.AG', 'math.AT', 'math.AP', 'math.CT', 'math.CA', 'math.CO',
#     'math.AC', 'math.CV', 'math.DG', 'math.DS', 'math.FA', 'math.GM', 'math.GN',
#     'math.GT', 'math.GR', 'math.HO', 'math.IT', 'math.KT', 'math.LO', 'math.MP',
#     'math.MG', 'math.NT', 'math.NA', 'math.OA', 'math.OC', 'math.PR', 'math.QA',
#     'math.RT', 'math.RA', 'math.SP', 'math.ST', 'math.SG',
    
#     # Computer Science
#     # cs.CG - Scheffer Fokus
#     'cs.AI', 'cs.AR', 'cs.CC', 'cs.CE', 'cs.CG', 'cs.CL', 'cs.CR', 'cs.CV',
#     'cs.CY', 'cs.DB', 'cs.DC', 'cs.DL', 'cs.DM', 'cs.DS', 'cs.ET', 'cs.FL',
#     'cs.GL', 'cs.GR', 'cs.GT', 'cs.HC', 'cs.IR', 'cs.IT', 'cs.LG', 'cs.LO',
#     'cs.MA', 'cs.MM', 'cs.MS', 'cs.NA', 'cs.NE', 'cs.NI', 'cs.OH', 'cs.OS',
#     'cs.PF', 'cs.PL', 'cs.RO', 'cs.SC', 'cs.SD', 'cs.SE', 'cs.SI', 'cs.SY',
    
#     # Quantitative Biology
#     'q-bio', 'q-bio.BM', 'q-bio.CB', 'q-bio.GN', 'q-bio.MN', 'q-bio.NC',
#     'q-bio.OT', 'q-bio.PE', 'q-bio.QM', 'q-bio.SC', 'q-bio.TO',
    
#     # Quantitative Finance
#     'q-fin.CP', 'q-fin.EC', 'q-fin.GN', 'q-fin.MF', 'q-fin.PM', 'q-fin.PR',
#     'q-fin.RM', 'q-fin.ST', 'q-fin.TR',
    
#     # Statistics
#     'stat.AP', 'stat.CO', 'stat.ME', 'stat.ML', 'stat.OT', 'stat.TH',
    
#     # Electrical Engineering and Systems Science
#     'eess.AS', 'eess.IV', 'eess.SP', 'eess.SY',
    
#     # Economics
#     'econ.EM', 'econ.GN', 'econ.TH'
# ]

CS_CG_CATEGORY = 'cs.CG'

# Global client that communicates with the arXiv API
client = arx.Client()


"""
04-May-2025 - Basti
Abstract: Retrieves a paper and prints out its metadata
Args:
    - paper: The current paper to be read out

Returns: Metadata of the provided Paper
"""
def read_meta(paper: Paper):
    if paper:
        logger.info(f"Title: {paper.title}\n")
        logger.info(f"Authors: {', '.join(str(author) for author in paper.authors)}\n")
        logger.info(f"Published: {paper.published}\n")
        logger.info(f"Abstract: {paper.abstract}\n")
        logger.info(f"PDF URL: {paper.url}\n")
        logger.info(f"Entry ID: {paper.entry_id}\n")


    else:
        logger.error("No Paper!")

"""
04-May-2025 - Basti
Abstract: Takes one paper from the cs_CG category and proceeds to retrieve the newest paper from that category
Args: None 
Returns: One arXiv paper -> Result
"""
def fetch_latest_paper() -> Paper:
    rate_limiter.wait()
    search = arx.Search(
        query=f"cat:{CS_CG_CATEGORY}", 
        max_results=1, 
        sort_by=arx.SortCriterion.SubmittedDate, 
        sort_order=arx.SortOrder.Descending
    )
    results = list(client.results(search))
    return Paper.from_arxiv(results[0]) if results else None

"""
04-May-2025 - Basti
Abstract: Fetches a x amount of papers in y category
Args:

- category: Category from one of arXiv's category
- amount: Amount of papers to be fetched starting from the newest papers

Returns: List -> of fetches papers
"""
def fetch_papers(category: str = CS_CG_CATEGORY, amount: int = 10) -> list:
    rate_limiter.wait()
    search = arx.Search(
        query=f"cat:{category}",
        max_results=amount,
        sort_by=arx.SortCriterion.SubmittedDate, 
        sort_order=arx.SortOrder.Descending
    )
    papers = []
    for result in search.results():
        if result:
            paper = Paper.from_arxiv(result)
            paper.category = category
            papers.append(paper)
        else:
            papers.append(None)
    return papers


def fetch_historical_batch(category: str, batch_size: int = 50, start_offset: int = 0) -> tuple[list[Paper], bool]:
    rate_limiter.wait()
    try:
        query_encoded = urllib.parse.quote(f"cat:{category}")
        feed_url = f"https://export.arxiv.org/api/query?search_query={query_encoded}&sortBy=submittedDate&sortOrder=ascending&start={start_offset}&max_results={batch_size}"
        
        response = requests.get(feed_url)
        if response.status_code != 200:
            logger.error(f"Failed to fetch from arXiv API: {response.status_code}")
            return [], False
            
        feed = feedparser.parse(response.content)
        
        total_results = int(feed.feed.opensearch_totalresults) if hasattr(feed.feed, 'opensearch_totalresults') else 0
        
        if start_offset == 0:
            logger.info(f"Got first page: {len(feed.entries)} of {total_results} total results")
        
        papers = []
        for entry in feed.entries:
            try:
                result = SimpleResult(entry)
                paper = Paper.from_arxiv(result)
                paper.category = category
                papers.append(paper)
            except Exception as e:
                logger.warning(f"Error creating paper from entry {entry.id}: {e}")
                continue
        
        has_more = len(feed.entries) >= batch_size and (start_offset + len(feed.entries)) < total_results
        
        logger.info(f"Fetched {len(papers)} historical papers for {category} (offset: {start_offset})")
        return papers, has_more
        
    except Exception as e:
        logger.error(f"Error fetching historical batch for {category}: {e}")
        return [], False


"""
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
FROM HERE ON ONLY SOME TESTING FUNCTIONS WILL BE DECLARED - THESE WILL LATER MOVE TO UNIT TESTS - IGNORE FOR NOW!

"""

"""
04-May-2025 - Basti
Abstract: Simple method to test (as of now the API of testing_arxiv - should not have much use for production)
Args:
Returns: 
"""
def testing_arxiv():
    search = arx.Search(
        query="submittedDate:[NOW-7DAYS TO NOW]",
        max_results = 10,
        sort_by = arx.SortCriterion.SubmittedDate,
        sort_order = arx.SortOrder.Descending
    )

    results = client.results(search)

    for r in results:
        logger.debug(f"Title: {r.title}\nDate: {r.published}")


"""
04-May-2025 - Basti
Abstract: Simple method to fetch the newest arXiv Results using feedparser instead of the arXiv Python API
Args:
Returns:
"""
def testing_feedparser():
    url = "http://export.arxiv.org/api/query?search_query=all:*&sortBy=lastUpdatedDate&sortOrder=descending&max_results=5&version=2"
    feed = feedparser.parse(url)
    logger.debug(len(feed.entries))
    for entry in feed.entries:
        logger.debug(f"Title: {entry.title}")
        logger.debug(f"Updated: {entry.updated}")
        logger.debug(f"Link: {entry.link}")
        logger.debug('-' * 80)



"""
04-May-2025 - Basti
Abstract: Tests if every category is accessible and is reachable through the arXiv API
Args:
Returns: 

@DeprecationWarning
def test_categories():
    print("Deprecated now! Categories have all passed the check as of 4th May 2025")
    client = arx.Client()
    for cat in categories:
        current_search = arx.Search(query=f"{cat}", max_results=1, sort_by=arx.SortCriterion.SubmittedDate, sort_order=arx.SortOrder.Descending)
        results = list(client.results(current_search))
        if len(results) == 0:
            print(f"Failed for category: {cat}")
            break

        print(f"Category {cat} passed!")
"""

