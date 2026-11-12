import pytest
import requests
from unittest.mock import Mock, patch

from MonaaLisa.src.SemanticPaper.api.semantic_scholar import SemanticScholarAPI


@pytest.fixture
def semantic_scholar_api():
    """Creates a SemanticScholarAPI instance with mocked external dependencies."""
    with patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.Logger'):
        api = SemanticScholarAPI(api_key="test_key")
        api.logger = Mock()
        return api


@pytest.fixture
def semantic_scholar_api_no_key():
    """Creates a SemanticScholarAPI instance without API key."""
    with patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.Logger'):
        api = SemanticScholarAPI(api_key=None)
        api.logger = Mock()
        return api


def _http_error_response(status_code):
    response = Mock()
    response.status_code = status_code
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


def _ok_response(items):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = items
    return response


class TestFetchBatchRetry:
    PAPER = {"paperId": "s2_1", "embedding": {"vector": [0.1] * 768}, "citations": [], "references": []}

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_retries_after_rate_limit(self, mock_post, mock_sleep, semantic_scholar_api):
        mock_post.side_effect = [_http_error_response(429), _ok_response([self.PAPER])]

        found, not_found = semantic_scholar_api.fetch_batch(["2101.00001"])

        assert [p["arxiv_id"] for p in found] == ["2101.00001"]
        assert not_found == []
        assert mock_post.call_count == 2

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_gives_up_after_max_attempts(self, mock_post, mock_sleep, semantic_scholar_api):
        mock_post.side_effect = requests.ConnectionError("down")

        found, not_found = semantic_scholar_api.fetch_batch(["2101.00001"])

        assert found == []
        assert not_found == ["2101.00001"]
        assert mock_post.call_count == 5

    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.time.sleep')
    @patch('MonaaLisa.src.SemanticPaper.api.semantic_scholar.requests.post')
    def test_does_not_retry_client_errors(self, mock_post, mock_sleep, semantic_scholar_api):
        mock_post.return_value = _http_error_response(400)

        found, not_found = semantic_scholar_api.fetch_batch(["2101.00001"])

        assert not_found == ["2101.00001"]
        assert mock_post.call_count == 1


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

