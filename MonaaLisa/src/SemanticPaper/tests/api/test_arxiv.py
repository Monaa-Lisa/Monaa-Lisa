import pytest
from unittest.mock import Mock, patch

from MonaaLisa.src.SemanticPaper.api.arxiv import ArxivAPI


@pytest.fixture
def arxiv_api():
    """Creates an ArxivAPI instance with mocked external dependencies."""
    with patch('MonaaLisa.src.SemanticPaper.api.arxiv.RateLimiter'), \
         patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Client'), \
         patch('MonaaLisa.src.SemanticPaper.api.arxiv.Logger'):
        api = ArxivAPI()
        api.rate_limiter = Mock()
        api.client = Mock()
        api.logger = Mock()
        return api


class TestFetchLatestPaper:
    """Tests the conditional logic in fetch_latest_paper()."""

    # patch the Search class used in fetch_latest_paper to control its behavior
    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_returns_none_when_api_returns_empty_results(self, mock_search, arxiv_api):
        """
        Tests the branch: if results: ... else return None

        Without this check, accessing results[0] on an empty list
        would raise IndexError.
        """
        # Mock the API to return an empty iterator, simulating no results found
        arxiv_api.client.results.return_value = iter([])

        result = arxiv_api.fetch_latest_paper()

        assert result is None


class TestFetchPapers:
    """Tests conditional logic and edge cases in fetch_papers()."""

    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_returns_empty_list_when_no_results(self, mock_search, arxiv_api):
        """
        Verifies empty iterator handling.

        Downstream code iterates over the returned list, so returning
        an empty list instead of None is critical.
        """
        arxiv_api.client.results.return_value = iter([])

        result = arxiv_api.fetch_papers(category="cs.AI", amount=5)

        assert result == []
        assert isinstance(result, list)


    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.Paper')
    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_handles_none_in_results_without_crashing(self, mock_search, mock_paper, arxiv_api):
        """
        Tests: if result: ... else: papers.append(None)

        arXiv API can return None for some results. We must preserve these None values in the
        output list without crashing.
        """
        # Mock the API to return an iterator with a mix of valid results and None
        arxiv_api.client.results.return_value = iter([Mock(), None, Mock()])
        # from_arxiv should only be called for the valid Mock results, not for None,
        # so we set side_effect to return a Mock for the first and third call
        # and it won't be called for the None.
        mock_paper.from_arxiv.side_effect = [Mock(), Mock()]

        result = arxiv_api.fetch_papers(category="cs.AI", amount=3)

        # We expect 3 results: the first and third are Paper objects, the second is None.
        assert len(result) == 3
        # Check that the second result is None, which means the None was preserved in the output list.
        assert result[1] is None  # None was preserved, not crashed


class TestFetchPapersByIds:
    """Tests fetch_papers_by_ids() specific logic."""

    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_handles_empty_id_list(self, mock_search, arxiv_api):
        """
        Edge case: empty ID list should return empty list, not error.
        """
        arxiv_api.client.results.return_value = iter([])

        result = arxiv_api.fetch_papers_by_ids([])

        assert result == []

    # Logic for testing if None results are handled correctly is already covered in TestFetchPapers
    # since fetch_papers_by_ids uses the same pattern.


class TestFetchHistoricalBatch:
    """
    Tests pagination logic in fetch_historical_batch().
    """

    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.Paper')
    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_has_more_true_when_batch_is_full(self, mock_search, mock_paper, arxiv_api):
        """
        Tests: has_more = len(papers) == batch_size

        When we get exactly batch_size results, there MIGHT be more.
        If has_more is wrong, pagination breaks.
        """
        # We mock the API to return an iterator that yields 5 results, which is our batch_size.
        arxiv_api.client.results.return_value = iter([Mock() for _ in range(5)])
        mock_paper.from_arxiv.side_effect = [Mock() for _ in range(5)]

        # We set batch_size=5, so if we get 5 papers, has_more should be True.
        papers, has_more = arxiv_api.fetch_historical_batch("cs.AI", batch_size=5)
        assert len(papers) == 5
        assert has_more is True

    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.Paper')
    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_has_more_false_when_batch_is_partial(self, mock_search, mock_paper, arxiv_api):
        """
        Tests: has_more = len(papers) == batch_size (False case)

        Fewer results than requested means we've reached the end.
        """
        # Mock the API to return an iterator that yields only 2 results, even though we ask for 10.
        # This simulates the case where there are only 2 papers left to fetch, so has_more should be False.
        arxiv_api.client.results.return_value = iter([Mock(), Mock()])
        mock_paper.from_arxiv.side_effect = [Mock(), Mock()]

        # We set batch_size=10, but only 2 results are returned, so has_more should be False.
        papers, has_more = arxiv_api.fetch_historical_batch("cs.AI", batch_size=10)

        assert len(papers) == 2
        assert has_more is False

    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_returns_empty_when_offset_exceeds_available_results(self, mock_search, arxiv_api):
        """
        Tests the StopIteration handling in the skip loop.

        Without the try/except around the skip loop, StopIteration
        would propagate and crash the scheduler.
        """
        arxiv_api.client.results.return_value = iter([])

        papers, has_more = arxiv_api.fetch_historical_batch("cs.AI", batch_size=10, start_offset=1000)

        assert papers == []
        assert has_more is False

    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_catches_api_exceptions_and_returns_safe_defaults(self, mock_search, arxiv_api):
        """
        Tests: except Exception as e: return [], False

        Network errors, timeouts, etc. must not crash the application.
        The try/except block is critical for reliability.
        """
        # Generic exception to simulate an API failure, such as a network timeout.
        arxiv_api.client.results.side_effect = Exception("Network timeout")

        papers, has_more = arxiv_api.fetch_historical_batch("cs.AI", batch_size=10)

        assert papers == []
        assert has_more is False
        arxiv_api.logger.error.assert_called_once()

    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.Paper')
    @patch('MonaaLisa.src.SemanticPaper.api.arxiv.arx.Search')
    def test_skip_logic_processes_correct_results(self, mock_search, mock_paper, arxiv_api):
        """
        Tests the skip loop: while skipped < start_offset: next(results_iter)

        With offset=2 and batch_size=2, we should skip first 2 and return next 2.
        If skip logic is wrong, we'd return wrong papers or crash.
        """
        # 4 results: [skip, skip, return, return]
        results = [Mock() for _ in range(4)]
        arxiv_api.client.results.return_value = iter(results)

        paper3, paper4 = Mock(), Mock()
        mock_paper.from_arxiv.side_effect = [paper3, paper4]

        papers, _ = arxiv_api.fetch_historical_batch("cs.AI", batch_size=2, start_offset=2)

        assert len(papers) == 2
        # from_arxiv should only be called for results[2] and results[3]
        assert mock_paper.from_arxiv.call_count == 2
