import sys
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

# Database.db creates a SQLAlchemy engine at module level, which requires
# DATABASE_URL.  We inject a MagicMock into sys.modules BEFORE importing
# incremental.py so that the real module is never loaded during tests.
sys.modules.setdefault("Database.db", MagicMock())

from MonaaLisa.src.SemanticPaper.pipeline.incremental import (
    _fetch_new_arxiv_papers,
    _normalize_entry_id,
    run_incremental_update,
    retry_uncaught_papers,
)

MODULE = "MonaaLisa.src.SemanticPaper.pipeline.incremental"


# because arxiv.Result is a complex object with many fields, we create a helper function

def _make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00001v1",
                       title="Test Paper", authors=None, summary="Abstract La La La Wait till I...",
                       primary_category="cs.AI", published=None,
                       pdf_url="http://arxiv.org/pdf/2401.00001v1"):
    """Creates a Mock that mimics an arxiv.Result object with all fields the pipeline accesses."""
    r = Mock()
    r.entry_id = entry_id
    r.title = title
    r.authors = authors or [Mock(__str__=lambda s: "Author A")]
    r.summary = summary
    r.primary_category = primary_category
    r.published = published or datetime(2024, 1, 1)
    r.updated = datetime(2024, 1, 2)
    r.doi = "10.1234/test"
    r.journal_ref = None
    r.pdf_url = pdf_url
    return r


class TestNormalizeEntryId:
    """Tests the URL-stripping and version-suffix logic in _normalize_entry_id()."""

    def test_strips_abs_url_prefix(self):
        """
        Tests: eid = entry_id_or_url.replace("http://arxiv.org/abs/", "")

        The raw entry_id from arXiv is a full URL.  Without stripping,
        DB lookups would fail because we store bare IDs.
        """
        result = _normalize_entry_id("http://arxiv.org/abs/2401.00001v1")

        # The URL prefix must be gone; only the bare ID (possibly with version) remains
        assert "http://arxiv.org" not in result

    def test_strips_plain_url_prefix(self):
        """
        Tests: .replace("http://arxiv.org/", "")

        Some entry_ids use the non-/abs/ URL variant.
        """
        result = _normalize_entry_id("http://arxiv.org/2401.00001v1")

        assert "http://arxiv.org" not in result

    def test_removes_version_suffix(self):
        """
        Tests: if "v" in eid ... parts[-1].isdigit() → strip version

        Version suffixes must be removed so that v1 and v2 of the same
        paper map to the same ID in the database.
        """
        result = _normalize_entry_id("2401.00001v2")

        assert result == "2401.00001"

    def test_preserves_id_without_version(self):
        """
        Tests the False branch: parts[-1].isdigit() is False → keep eid unchanged.

        Not every ID has a version suffix.  A bare ID like "2401.00001"
        contains no 'v' followed by digits, so it must pass through as-is.
        """
        result = _normalize_entry_id("2401.00001")

        assert result == "2401.00001"


class TestFetchNewArxivPapers:
    """Tests conditional logic inside _fetch_new_arxiv_papers()."""

    @patch(f"{MODULE}.arx.Search")
    @patch(f"{MODULE}.logger")
    def test_returns_empty_list_when_no_results(self, mock_logger, mock_search):
        """
        Tests: the for-loop body never executes → returns []

        If arXiv has nothing new, the caller must receive an empty list
        so that downstream ``if not raw_results`` triggers correctly.
        """
        # Mock the API to return an empty iterator, simulating no new papers on arXiv
        arxiv_client = Mock()
        arxiv_client.client.results.return_value = iter([])

        result = _fetch_new_arxiv_papers(arxiv_client, datetime(2024, 1, 1))

        assert result == []
        assert isinstance(result, list)

    @patch(f"{MODULE}.arx.Search")
    @patch(f"{MODULE}.logger")
    def test_respects_max_results_cap(self, mock_logger, mock_search):
        """
        Tests: if max_results and len(results) >= max_results: break

        Without this guard the fetcher would exhaust the entire arXiv
        iterator, consuming unbounded memory and API quota.
        """
        # 10 results available, but we only want 3
        papers = [Mock() for _ in range(10)]
        arxiv_client = Mock()
        arxiv_client.client.results.return_value = iter(papers)

        # We set max_results=3, so the function should stop after collecting 3 papers
        result = _fetch_new_arxiv_papers(arxiv_client, datetime(2024, 1, 1), max_results=3)

        assert len(result) == 3

    @patch(f"{MODULE}.arx.Search")
    @patch(f"{MODULE}.logger")
    def test_catches_exception_and_returns_partial_results(self, mock_logger, mock_search):
        """
        Tests: except Exception as e: logger.error(...)

        If the arXiv API raises mid-iteration, papers collected so far
        must still be returned instead of crashing the pipeline.
        """
        # Iterator that yields 2 valid results, then explodes – simulates a network timeout mid-stream
        def _exploding_iterator():
            yield Mock()
            yield Mock()
            raise ConnectionError("timeout")

        arxiv_client = Mock()
        arxiv_client.client.results.return_value = _exploding_iterator()

        result = _fetch_new_arxiv_papers(arxiv_client, datetime(2024, 1, 1))

        # 2 papers were collected before the exception; they must not be lost
        assert len(result) == 2
        # The error must be logged so operators can investigate
        mock_logger.error.assert_called_once()


class TestRunIncrementalUpdate:
    """Tests branching logic inside run_incremental_update()."""

    # get_paper_count is patched but should NOT be called – it sits after the early return
    @patch(f"{MODULE}.get_paper_count")
    # newest_date is None when the DB is empty (initial import hasn't run yet)
    @patch(f"{MODULE}.get_newest_paper_date", return_value=None)
    @patch(f"{MODULE}.logger")
    def test_returns_early_when_db_is_empty(self, mock_logger, mock_newest, mock_count):
        """
        Tests: if newest_date is None: ... return

        An empty database means the initial import hasn't run yet.
        Without this guard, the pipeline would query arXiv with
        since=None and crash.
        """
        run_incremental_update(Mock(), Mock(), Mock())

        # A warning is the only thing that should happen – no API calls, no exceptions
        mock_logger.warning.assert_called_once()
        # get_paper_count sits AFTER the early return, so it must not have been reached
        mock_count.assert_not_called()

    # _fetch_new_arxiv_papers returns [] to simulate "arXiv has nothing new"
    @patch(f"{MODULE}._fetch_new_arxiv_papers", return_value=[])
    @patch(f"{MODULE}.get_paper_count", return_value=100)
    @patch(f"{MODULE}.get_newest_paper_date", return_value=datetime(2024, 1, 1))
    @patch(f"{MODULE}.logger")
    def test_returns_early_when_no_new_arxiv_papers(self, mock_logger, mock_newest,
                                                     mock_count, mock_fetch):
        """
        Tests: if not raw_results: ... return

        When arXiv has nothing new, the pipeline must exit cleanly
        without touching SemanticScholar or the DB.
        """
        s2_client = Mock()

        run_incremental_update(Mock(), s2_client, Mock())

        # SemanticScholar should never be called when there's nothing to process
        s2_client.fetch_batch.assert_not_called()

    # arXiv returns papers, but paper_exists_by_id always returns True → all are duplicates.
    # This covers the case where arXiv returns results, but after deduplication nothing is left.
    @patch(f"{MODULE}.paper_exists_by_id", return_value=True)
    @patch(f"{MODULE}._fetch_new_arxiv_papers")
    @patch(f"{MODULE}.get_paper_count", return_value=100)
    @patch(f"{MODULE}.get_newest_paper_date", return_value=datetime(2024, 1, 1))
    @patch(f"{MODULE}.logger")
    def test_returns_early_when_all_papers_already_in_db(self, mock_logger, mock_newest,
                                                          mock_count, mock_fetch,
                                                          mock_exists):
        """
        Tests: if not new_papers: ... return

        After dedup, if every fetched paper already exists in the DB,
        we must not call SemanticScholar.  Without this check we'd
        waste API quota on papers we already have.
        """
        mock_fetch.return_value = [_make_arxiv_result()]

        s2_client = Mock()
        run_incremental_update(Mock(), s2_client, Mock())

        s2_client.fetch_batch.assert_not_called()

   # The next two tests cover the "if found:" branch: success vs failure of save_processed_paper

    @patch(f"{MODULE}.save_uncaught_paper")
    # save_processed_paper returns True → paper saved successfully
    @patch(f"{MODULE}.save_processed_paper", return_value=True)
    @patch(f"{MODULE}.cfg")
    @patch(f"{MODULE}.paper_exists_by_id", return_value=False)
    @patch(f"{MODULE}._fetch_new_arxiv_papers")
    @patch(f"{MODULE}.get_paper_count", return_value=100)
    @patch(f"{MODULE}.get_newest_paper_date", return_value=datetime(2024, 1, 1))
    @patch(f"{MODULE}.logger")
    def test_processes_found_papers_through_pipeline(self, mock_logger, mock_newest,
                                                      mock_count, mock_fetch,
                                                      mock_exists, mock_cfg,
                                                      mock_save, mock_save_uncaught):
        """
        Tests: if found: ... pipeline.batch_process(vectors_768)

        Papers that SemanticScholar returns embeddings for must be
        processed through PCA+UMAP and saved to the main tables.
        """
        mock_fetch.return_value = [_make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00001v1")]
        mock_cfg.get_int.return_value = 400

        # SemanticScholar "finds" the paper and returns an embedding
        s2_client = Mock()
        s2_client.fetch_batch.return_value = (
            [{"arxiv_id": "2401.00001", "embedding_768d": [0.1] * 768,
              "s2_id": "s2_123", "non_arxiv_citation_count": 5,
              "non_arxiv_reference_count": 3,
              "citation_arxiv_ids": [], "reference_arxiv_ids": []}],
            [],  # not_found is empty
        )

        # Pipeline mock returns a reduced 128-D embedding + 2-D coordinates
        pipeline = Mock()
        pipeline.batch_process.return_value = [([0.1] * 128, (1.0, 2.0))]

        run_incremental_update(Mock(), s2_client, pipeline)

        # The embedding must go through the pipeline, and the result must be saved
        pipeline.batch_process.assert_called_once()
        mock_save.assert_called_once()

    @patch(f"{MODULE}.save_uncaught_paper")
    # save_processed_paper returns False → simulates a DB write failure
    @patch(f"{MODULE}.save_processed_paper", return_value=False)
    @patch(f"{MODULE}.cfg")
    @patch(f"{MODULE}.paper_exists_by_id", return_value=False)
    @patch(f"{MODULE}._fetch_new_arxiv_papers")
    @patch(f"{MODULE}.get_paper_count", return_value=100)
    @patch(f"{MODULE}.get_newest_paper_date", return_value=datetime(2024, 1, 1))
    @patch(f"{MODULE}.logger")
    def test_logs_warning_when_save_fails(self, mock_logger, mock_newest,
                                           mock_count, mock_fetch,
                                           mock_exists, mock_cfg,
                                           mock_save, mock_save_uncaught):
        """
        Tests: if ok: processed_count += 1 / else: logger.warning(...)

        When save_processed_paper returns False, the failure must be
        logged so operators can investigate.
        """
        mock_fetch.return_value = [_make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00001v1")]
        mock_cfg.get_int.return_value = 400

        # SemanticScholar returns data, but the DB save will fail (mocked above)
        s2_client = Mock()
        s2_client.fetch_batch.return_value = (
            [{"arxiv_id": "2401.00001", "embedding_768d": [0.1] * 768,
              "s2_id": "s2_123"}],
            [],
        )

        pipeline = Mock()
        pipeline.batch_process.return_value = [([0.1] * 128, (1.0, 2.0))]

        run_incremental_update(Mock(), s2_client, pipeline)

        # save returned False → a warning about the failed paper must be logged
        mock_logger.warning.assert_called()

   # This test covers the "for arxiv_id in not_found:" loop

    @patch(f"{MODULE}.save_uncaught_paper")
    @patch(f"{MODULE}.cfg")
    @patch(f"{MODULE}.paper_exists_by_id", return_value=False)
    @patch(f"{MODULE}._fetch_new_arxiv_papers")
    @patch(f"{MODULE}.get_paper_count", return_value=100)
    @patch(f"{MODULE}.get_newest_paper_date", return_value=datetime(2024, 1, 1))
    @patch(f"{MODULE}.logger")
    def test_saves_not_found_papers_as_uncaught(self, mock_logger, mock_newest,
                                                 mock_count, mock_fetch,
                                                 mock_exists, mock_cfg,
                                                 mock_save_uncaught):
        """
        Tests: for arxiv_id in not_found: save_uncaught_paper(...)

        Papers that SemanticScholar doesn't know about yet must be
        saved to uncaught_paper so the retry loop can pick them up later.
        """
        r1 = _make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00001v1")
        r2 = _make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00002v1")
        mock_fetch.return_value = [r1, r2]
        mock_cfg.get_int.return_value = 4

        # SemanticScholar doesn't know either paper
        s2_client = Mock()
        s2_client.fetch_batch.return_value = (
            [],                                  # found is empty
            ["2401.00001", "2401.00002"],         # both papers are not_found
        )

        pipeline = Mock()

        run_incremental_update(Mock(), s2_client, pipeline)

        # Both papers should be saved to the uncaught table
        assert mock_save_uncaught.call_count == 2
        # Pipeline should NOT have been called – there are no embeddings to process
        pipeline.batch_process.assert_not_called()

   # This test covers the dedup filter: if not paper_exists_by_id(eid)

    # paper_exists_by_id is given a side_effect so we can control per-paper results
    @patch(f"{MODULE}.paper_exists_by_id")
    @patch(f"{MODULE}._fetch_new_arxiv_papers")
    @patch(f"{MODULE}.get_paper_count", return_value=100)
    @patch(f"{MODULE}.get_newest_paper_date", return_value=datetime(2024, 1, 1))
    @patch(f"{MODULE}.logger")
    def test_dedup_filters_existing_papers(self, mock_logger, mock_newest,
                                            mock_count, mock_fetch,
                                            mock_exists):
        """
        Tests: if not paper_exists_by_id(eid): new_papers.append(...)

        The dedup loop must skip papers that already exist in the DB.
        Without this filter we'd create duplicates.
        """
        r1 = _make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00001v1")
        r2 = _make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00002v1")
        r3 = _make_arxiv_result(entry_id="http://arxiv.org/abs/2401.00003v1")
        mock_fetch.return_value = [r1, r2, r3]

        # Paper 1: new, Paper 2: already exists, Paper 3: new
        mock_exists.side_effect = [False, True, False]

        s2_client = Mock()
        s2_client.fetch_batch.return_value = ([], [])

        with patch(f"{MODULE}.cfg") as mock_cfg, \
             patch(f"{MODULE}.save_uncaught_paper"):
            mock_cfg.get_int.return_value = 400
            run_incremental_update(Mock(), s2_client, Mock())

        # fetch_batch should receive only the 2 new IDs; the duplicate must be filtered out
        called_ids = s2_client.fetch_batch.call_args[0][0]
        assert len(called_ids) == 2
        assert "2401.00002" not in called_ids  # the existing paper was skipped


class TestRetryUncaughtPapers:
    """Tests branching logic inside retry_uncaught_papers()."""

    @patch(f"{MODULE}.purge_expired_uncaught")
    # get_uncaught_papers_due returns [] to simulate "nothing is due for retry"
    @patch(f"{MODULE}.get_uncaught_papers_due", return_value=[])
    @patch(f"{MODULE}.cfg")
    @patch(f"{MODULE}.logger")
    def test_returns_early_when_no_papers_due(self, mock_logger, mock_cfg,
                                               mock_due, mock_purge):
        """
        Tests: if not due: ... return

        When there are no uncaught papers due for retry, the function
        must exit without calling SemanticScholar.
        """
        mock_cfg.get_int.return_value = 14

        s2_client = Mock()
        retry_uncaught_papers(s2_client, Mock())

        # SemanticScholar should never be called when there's nothing to retry
        s2_client.fetch_batch.assert_not_called()

   # The next two tests cover "if ok: delete_uncaught_paper" – True vs False branch

    @patch(f"{MODULE}.purge_expired_uncaught")
    @patch(f"{MODULE}.delete_uncaught_paper")
    # save_processed_paper returns True → paper rescued successfully
    @patch(f"{MODULE}.save_processed_paper", return_value=True)
    @patch(f"{MODULE}.get_uncaught_papers_due")
    @patch(f"{MODULE}.cfg")
    @patch(f"{MODULE}.logger")
    def test_rescues_found_papers_and_deletes_from_uncaught(self, mock_logger, mock_cfg,
                                                             mock_due, mock_save,
                                                             mock_delete, mock_purge):
        """
        Tests: if ok: delete_uncaught_paper(arxiv_id)

        When a previously uncaught paper is now found on SemanticScholar,
        it must be saved to the main tables AND removed from the uncaught table.
        """
        # Build a fake uncaught paper with all fields the function reads
        uncaught = Mock()
        uncaught.entry_id = "2401.00001"
        uncaught.title = "Test"
        uncaught.authors = "Author"
        uncaught.abstract = "Abstract"
        uncaught.categories = "cs.AI"
        uncaught.published = datetime(2024, 1, 1)
        uncaught.url = "http://arxiv.org/pdf/2401.00001"
        mock_due.return_value = [uncaught]
        mock_cfg.get_int.return_value = 400

        # SemanticScholar now has data for this paper
        s2_client = Mock()
        s2_client.fetch_batch.return_value = (
            [{"arxiv_id": "2401.00001", "embedding_768d": [0.1] * 768,
              "s2_id": "s2_123", "non_arxiv_citation_count": 5,
              "non_arxiv_reference_count": 3,
              "citation_arxiv_ids": [], "reference_arxiv_ids": []}],
            [],  # not_found is empty
        )

        pipeline = Mock()
        pipeline.batch_process.return_value = [([0.1] * 128, (1.0, 2.0))]

        retry_uncaught_papers(s2_client, pipeline)

        # Paper must be saved to main tables AND removed from uncaught
        mock_save.assert_called_once()
        mock_delete.assert_called_once_with("2401.00001")

    @patch(f"{MODULE}.purge_expired_uncaught")
    @patch(f"{MODULE}.delete_uncaught_paper")
    # save_processed_paper returns False → DB write failed
    @patch(f"{MODULE}.save_processed_paper", return_value=False)
    @patch(f"{MODULE}.get_uncaught_papers_due")
    @patch(f"{MODULE}.cfg")
    @patch(f"{MODULE}.logger")
    def test_does_not_delete_uncaught_when_save_fails(self, mock_logger, mock_cfg,
                                                       mock_due, mock_save,
                                                       mock_delete, mock_purge):
        """
        Tests: if ok: delete_uncaught_paper (False branch)

        If save_processed_paper fails, the paper must remain in the
        uncaught table so it can be retried on the next cycle.
        """
        uncaught = Mock()
        uncaught.entry_id = "2401.00001"
        mock_due.return_value = [uncaught]
        mock_cfg.get_int.return_value = 400

        # SemanticScholar has data, but the save will fail (mocked above)
        s2_client = Mock()
        s2_client.fetch_batch.return_value = (
            [{"arxiv_id": "2401.00001", "embedding_768d": [0.1] * 768}],
            [],
        )

        pipeline = Mock()
        pipeline.batch_process.return_value = [([0.1] * 128, (1.0, 2.0))]

        retry_uncaught_papers(s2_client, pipeline)

        # save returned False → the paper must NOT be deleted from uncaught
        mock_delete.assert_not_called()

    # This test covers the for arxiv_id in loop

    @patch(f"{MODULE}.purge_expired_uncaught")
    @patch(f"{MODULE}.increment_uncaught_retry")
    @patch(f"{MODULE}.get_uncaught_papers_due")
    @patch(f"{MODULE}.cfg")
    @patch(f"{MODULE}.logger")
    def test_increments_retry_for_still_missing_papers(self, mock_logger, mock_cfg,
                                                        mock_due, mock_increment,
                                                        mock_purge):
        """
        Tests: for arxiv_id in not_found: increment_uncaught_retry(arxiv_id)

        Papers that SemanticScholar still doesn't know about must have
        their retry counter incremented so they eventually get purged
        after max_retries.
        """
        uncaught1 = Mock(); uncaught1.entry_id = "2401.00001"
        uncaught2 = Mock(); uncaught2.entry_id = "2401.00002"
        mock_due.return_value = [uncaught1, uncaught2]
        mock_cfg.get_int.return_value = 400

        # SemanticScholar still doesn't know about either paper
        s2_client = Mock()
        s2_client.fetch_batch.return_value = (
            [],                                  # found is empty
            ["2401.00001", "2401.00002"],         # both still missing
        )

        pipeline = Mock()
        retry_uncaught_papers(s2_client, pipeline)

        # Both papers must have their retry counter incremented
        assert mock_increment.call_count == 2
        mock_increment.assert_any_call("2401.00001")
        mock_increment.assert_any_call("2401.00002")

