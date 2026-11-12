import pytest
from unittest.mock import Mock, patch

from MonaaLisa.src.SemanticPaper.api.semantic_scholar import SemanticScholarAPI


@pytest.fixture
def semantic_scholar_api():
    """Creates a SemanticScholarAPI instance with mocked external dependencies."""
    with patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.AsyncSemanticScholar'), \
         patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.Logger'):
        api = SemanticScholarAPI(api_key="test_key")
        api.client = Mock()
        api.logger = Mock()
        return api


@pytest.fixture
def semantic_scholar_api_no_key():
    """Creates a SemanticScholarAPI instance without API key."""
    with patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.AsyncSemanticScholar'), \
         patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.Logger'):
        api = SemanticScholarAPI(api_key=None)
        api.client = Mock()
        api.logger = Mock()
        return api


class TestFetchCitations:
    """Tests conditional logic in fetch_citations()."""

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_paper_with_arxiv_citations(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: if arxiv_id: branch in the citation loop

        When a citation has an ArXiv ID, it should be added to citation_arxiv_ids.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        # Mock citation with ArXiv ID
        mock_citation = Mock()
        mock_citation.externalIds = {"ArXiv": "2101.54321"}

        # Mock the async function return value
        mock_semantic_paper = Mock()
        mock_semantic_paper.citations = [mock_citation]
        # Since fetch_citations calls asyncio.run on a function that returns the citations,
        # we need to mock that return value
        mock_asyncio_run.return_value = [mock_citation]

        # Since we establish that the citation has an ArXiv ID, we expect the code
        # to call fetch_papers_by_ids on the Arxiv client with that ID.
        # We need to mock that as well to return a valid paper object.

        # Mock ArxivAPI
        mock_arxiv_client = Mock()
        mock_arxiv_client.fetch_papers_by_ids.return_value = [Mock()]

        citations_on_arxiv, citations_not_present = semantic_scholar_api.fetch_citations(
            mock_paper, mock_arxiv_client
        )

        # Verify ArXiv client was called with the correct ID
        mock_arxiv_client.fetch_papers_by_ids.assert_called_once()
        assert len(citations_on_arxiv) == 1
        assert len(citations_not_present) == 0

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_citations_without_arxiv_id(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: else branch when citation has no ArXiv ID

        Citations without ArXiv IDs should be added to citations_not_present.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        # Mock citation without ArXiv ID
        mock_citation = Mock()
        mock_citation.externalIds = {"DOI": "10.1234/example"}

        mock_asyncio_run.return_value = [mock_citation]

        mock_arxiv_client = Mock()

        # Same as before, we need to mock the Arxiv client,
        # but in this case we expect it not to be called since there were no ArXiv IDs.

        citations_on_arxiv, citations_not_present = semantic_scholar_api.fetch_citations(
            mock_paper, mock_arxiv_client
        )

        # Verify no ArXiv fetch was attempted
        mock_arxiv_client.fetch_papers_by_ids.assert_not_called()
        assert len(citations_on_arxiv) == 0
        assert len(citations_not_present) == 1

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_empty_citations_list(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: if citation_arxiv_ids: branch when list is empty

        When there are no citations with ArXiv IDs, citations_on_arxiv should be empty list.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        mock_asyncio_run.return_value = []

        mock_arxiv_client = Mock()

        citations_on_arxiv, citations_not_present = semantic_scholar_api.fetch_citations(
            mock_paper, mock_arxiv_client
        )

        assert citations_on_arxiv == []
        assert citations_not_present == []

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_mixed_citations(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: Mixed case with both ArXiv and non-ArXiv citations

        Verifies proper separation between citations_on_arxiv and citations_not_present.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        # Mock citation with ArXiv ID
        mock_citation_arxiv = Mock()
        mock_citation_arxiv.externalIds = {"ArXiv": "2101.54321"}

        # Mock citation without ArXiv ID
        mock_citation_no_arxiv = Mock()
        mock_citation_no_arxiv.externalIds = {"DOI": "10.1234/example"}

        mock_asyncio_run.return_value = [mock_citation_arxiv, mock_citation_no_arxiv]

        mock_arxiv_client = Mock()
        mock_arxiv_client.fetch_papers_by_ids.return_value = [Mock()]

        citations_on_arxiv, citations_not_present = semantic_scholar_api.fetch_citations(
            mock_paper, mock_arxiv_client
        )
        # Verify ArXiv client was called once for the one citation with an ArXiv ID
        assert len(citations_on_arxiv) == 1
        assert len(citations_not_present) == 1


class TestFetchReferences:
    """Tests conditional logic in fetch_references()."""
    # Annotation: Extremely similar to the citation tests, but we want to keep them separate for clarity and to ensure we cover the specific logic in references.

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_paper_with_arxiv_references(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: if arxiv_id: branch in the reference loop

        When a reference has an ArXiv ID, it should be added to references_arxiv_ids.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        # Mock reference with ArXiv ID
        mock_reference = Mock()
        mock_reference.externalIds = {"ArXiv": "2101.54321"}

        mock_asyncio_run.return_value = [mock_reference]

        mock_arxiv_client = Mock()
        mock_arxiv_client.fetch_papers_by_ids.return_value = [Mock()]

        references_on_arxiv, references_not_present = semantic_scholar_api.fetch_references(
            mock_paper, mock_arxiv_client
        )

        mock_arxiv_client.fetch_papers_by_ids.assert_called_once()
        assert len(references_on_arxiv) == 1
        assert len(references_not_present) == 0

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_references_without_arxiv_id(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: else branch when reference has no ArXiv ID

        References without ArXiv IDs should be added to references_not_present.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        # Mock reference without ArXiv ID
        mock_reference = Mock()
        mock_reference.externalIds = {"DOI": "10.1234/example"}

        mock_asyncio_run.return_value = [mock_reference]

        mock_arxiv_client = Mock()

        references_on_arxiv, references_not_present = semantic_scholar_api.fetch_references(
            mock_paper, mock_arxiv_client
        )

        mock_arxiv_client.fetch_papers_by_ids.assert_not_called()
        assert len(references_on_arxiv) == 0
        assert len(references_not_present) == 1

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_empty_references_list(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: if references_arxiv_ids: branch when list is empty

        When there are no references with ArXiv IDs, references_on_arxiv should be empty list.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        mock_asyncio_run.return_value = []

        mock_arxiv_client = Mock()

        references_on_arxiv, references_not_present = semantic_scholar_api.fetch_references(
            mock_paper, mock_arxiv_client
        )

        assert references_on_arxiv == []
        assert references_not_present == []

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.asyncio.run')
    def test_handles_mixed_references(self, mock_asyncio_run, semantic_scholar_api):
        """
        Tests: Mixed case with both ArXiv and non-ArXiv references

        Verifies proper separation between references_on_arxiv and references_not_present.
        """
        mock_paper = Mock()
        mock_paper.entry_id = "http://arxiv.org/abs/2101.12345v1"

        # Mock reference with ArXiv ID
        mock_reference_arxiv = Mock()
        mock_reference_arxiv.externalIds = {"ArXiv": "2101.54321"}

        # Mock reference without ArXiv ID
        mock_reference_no_arxiv = Mock()
        mock_reference_no_arxiv.externalIds = {"DOI": "10.1234/example"}

        mock_asyncio_run.return_value = [mock_reference_arxiv, mock_reference_no_arxiv]

        mock_arxiv_client = Mock()
        mock_arxiv_client.fetch_papers_by_ids.return_value = [Mock()]

        references_on_arxiv, references_not_present = semantic_scholar_api.fetch_references(
            mock_paper, mock_arxiv_client
        )

        assert len(references_on_arxiv) == 1
        assert len(references_not_present) == 1


class TestFetchBatch:
    """Tests conditional logic in fetch_batch()."""

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_papers_with_embeddings(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: if vector_768 is not None branch

        When a paper has a SPECTER v2 embedding, it should be added to found.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [],
                "references": [],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 1
        assert found[0]["arxiv_id"] == "2101.12345"
        assert found[0]["s2_id"] == "s2_123"
        assert found[0]["embedding_768d"] == [0.1] * 768
        assert len(not_found) == 0

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_papers_not_on_semantic_scholar(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: if item is None branch

        When Semantic Scholar returns null for a paper, it should be added to not_found.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [None]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.99999"])

        assert len(found) == 0
        assert len(not_found) == 1
        assert not_found[0] == "2101.99999"

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_papers_without_embedding(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: if vector_768 is None branch

        When a paper exists on Semantic Scholar but has no embedding, it should be added to not_found.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_456",
                "externalIds": {"ArXiv": "2101.11111"},
                "embedding": None,
                "citations": [],
                "references": [],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.11111"])

        assert len(found) == 0
        assert len(not_found) == 1
        assert not_found[0] == "2101.11111"

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_request_exception(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: except Exception branch

        When the HTTP request fails, all IDs in the chunk should be added to not_found.
        """
        mock_post.side_effect = Exception("Connection timeout")

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345", "2101.67890"])

        assert len(found) == 0
        assert len(not_found) == 2
        assert "2101.12345" in not_found
        assert "2101.67890" in not_found

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_empty_arxiv_ids_list(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: for start in range(0, len(arxiv_ids), batch_size) with empty list

        When there are no arXiv IDs to fetch, both found and not_found should be empty.
        """
        found, not_found = semantic_scholar_api.fetch_batch([])

        mock_post.assert_not_called()
        assert found == []
        assert not_found == []

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_citations_with_arxiv_ids(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: if cit_arxiv: branch in the citation extraction loop

        When a citation has an ArXiv ID, it should be added to citation_arxiv_ids.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [
                    {"externalIds": {"ArXiv": "2101.54321"}},
                    {"externalIds": {"ArXiv": "2101.99999"}},
                ],
                "references": [],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 1
        assert found[0]["citation_arxiv_ids"] == ["2101.54321", "2101.99999"]
        assert found[0]["non_arxiv_citation_count"] == 0

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_citations_without_arxiv_ids(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: else branch in the citation extraction loop

        When a citation has no ArXiv ID, non_arxiv_citation_count should be incremented.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [
                    {"externalIds": {"DOI": "10.1234/example"}},
                ],
                "references": [],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 1
        assert found[0]["citation_arxiv_ids"] == []
        assert found[0]["non_arxiv_citation_count"] == 1

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_references_with_arxiv_ids(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: if ref_arxiv: branch in the reference extraction loop

        When a reference has an ArXiv ID, it should be added to reference_arxiv_ids.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [],
                "references": [
                    {"externalIds": {"ArXiv": "2101.54321"}},
                    {"externalIds": {"ArXiv": "2101.99999"}},
                ],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 1
        assert found[0]["reference_arxiv_ids"] == ["2101.54321", "2101.99999"]
        assert found[0]["non_arxiv_reference_count"] == 0

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_references_without_arxiv_ids(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: else branch in the reference extraction loop

        When a reference has no ArXiv ID, non_arxiv_reference_count should be incremented.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [],
                "references": [
                    {"externalIds": {"DOI": "10.1234/example"}},
                ],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 1
        assert found[0]["reference_arxiv_ids"] == []
        assert found[0]["non_arxiv_reference_count"] == 1

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_mixed_found_and_not_found(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: Mixed case with both found and not_found papers in one batch

        Verifies proper separation between found and not_found.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [],
                "references": [],
            },
            None,
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345", "2101.99999"])

        assert len(found) == 1
        assert len(not_found) == 1
        assert found[0]["arxiv_id"] == "2101.12345"
        assert not_found[0] == "2101.99999"

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_mixed_citations_and_references(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: Mixed case with both ArXiv and non-ArXiv citations and references

        Verifies proper counting and separation across citations and references.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [
                    {"externalIds": {"ArXiv": "2101.54321"}},
                    {"externalIds": {"DOI": "10.1234/example"}},
                ],
                "references": [
                    {"externalIds": {"ArXiv": "2101.11111"}},
                    {"externalIds": {"DOI": "10.5678/example"}},
                    {"externalIds": {"DOI": "10.9999/example"}},
                ],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 1
        assert found[0]["citation_arxiv_ids"] == ["2101.54321"]
        assert found[0]["non_arxiv_citation_count"] == 1
        assert found[0]["reference_arxiv_ids"] == ["2101.11111"]
        assert found[0]["non_arxiv_reference_count"] == 2

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_sends_api_key_in_headers(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: if self.api_key: branch for header construction

        When an API key is present, it should be sent in the x-api-key header.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = []
        mock_post.return_value = mock_response

        semantic_scholar_api.fetch_batch(["2101.12345"])

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["x-api-key"] == "test_key"

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_sends_no_api_key_when_absent(self, mock_post, mock_sleep, semantic_scholar_api_no_key):
        """
        Tests: else branch when no API key is present

        When no API key is set, x-api-key should not be in headers.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = []
        mock_post.return_value = mock_response

        semantic_scholar_api_no_key.fetch_batch(["2101.12345"])

        _, kwargs = mock_post.call_args
        assert "x-api-key" not in kwargs["headers"]

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_multiple_batches(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: batching logic with batch_size smaller than total IDs

        When there are more IDs than batch_size, multiple requests should be made
        and time.sleep should be called between batches.
        """
        mock_response_1 = Mock()
        mock_response_1.raise_for_status = Mock()
        mock_response_1.json.return_value = [
            {
                "paperId": "s2_1",
                "externalIds": {"ArXiv": "2101.00001"},
                "embedding": {"vector": [0.1] * 768},
                "citations": [],
                "references": [],
            }
        ]

        mock_response_2 = Mock()
        mock_response_2.raise_for_status = Mock()
        mock_response_2.json.return_value = [
            {
                "paperId": "s2_2",
                "externalIds": {"ArXiv": "2101.00002"},
                "embedding": {"vector": [0.2] * 768},
                "citations": [],
                "references": [],
            }
        ]

        mock_post.side_effect = [mock_response_1, mock_response_2]

        found, not_found = semantic_scholar_api.fetch_batch(
            ["2101.00001", "2101.00002"], batch_size=1, pause_seconds=0.5
        )

        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(0.5)
        assert len(found) == 2
        assert len(not_found) == 0

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_constructs_correct_payload(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: payload construction with ARXIV: prefix

        Each arXiv ID should be prefixed with "ARXIV:" in the request payload.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = []
        mock_post.return_value = mock_response

        semantic_scholar_api.fetch_batch(["2101.12345", "2302.67890"])

        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"ids": ["ARXIV:2101.12345", "ARXIV:2302.67890"]}

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_null_citations_and_references(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: (item.get("citations") or []) and (item.get("references") or []) fallback

        When citations or references are null, they should be treated as empty lists.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"vector": [0.1] * 768},
                "citations": None,
                "references": None,
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 1
        assert found[0]["citation_arxiv_ids"] == []
        assert found[0]["reference_arxiv_ids"] == []
        assert found[0]["non_arxiv_citation_count"] == 0
        assert found[0]["non_arxiv_reference_count"] == 0

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_handles_embedding_dict_without_vector(self, mock_post, mock_sleep, semantic_scholar_api):
        """
        Tests: if embedding_data and isinstance(embedding_data, dict) branch with missing vector key

        When embedding is a dict but has no "vector" key, vector_768 should be None and paper goes to not_found.
        """
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {
                "paperId": "s2_123",
                "externalIds": {"ArXiv": "2101.12345"},
                "embedding": {"model": "specter_v2"},
                "citations": [],
                "references": [],
            }
        ]
        mock_post.return_value = mock_response

        found, not_found = semantic_scholar_api.fetch_batch(["2101.12345"])

        assert len(found) == 0
        assert len(not_found) == 1
        assert not_found[0] == "2101.12345"

