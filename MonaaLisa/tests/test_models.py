from MonaaLisa.src.datamodels.models import Publication
from MonaaLisa.src.datamodels.arxiv_source import ArxivSource
import datetime

# No online connection req. all data is mocked
# Tests basic behaviour of Publication
def test_publication():
    publication = Publication("Test Title", ["Test Author"], "Test Summary", datetime.datetime.fromisoformat("2025-05-06"), "Test Url")
    assert publication.title == "Test Title"
    assert publication.authors == ["Test Author"]
    assert publication.summary == "Test Summary"
    assert publication.published.strftime("%d.%m.%Y") == "06.05.2025"
    assert publication.url == "Test Url"
    assert isinstance(publication.to_json(), dict)
    assert publication.to_json().keys() == {"title", "authors", "summary", "published", "url"}

# Tests basic behaviour of ArxivSource
def test_arxivsource():
    arxiv_source = ArxivSource()
    assert isinstance(arxiv_source.fetch_publications("test"), list)


def test_arxivsource_parse():
    arxiv_source = ArxivSource()
    raw_data = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>test</title><author><name>test</name></author><summary>test</summary><published>2024-02-22Z</published><id>test</id></entry></feed>"""
    assert isinstance(arxiv_source.parse_publications(raw_data), list)