import time

import requests

from util.logger import Logger


class SemanticScholarAPI:
    """
    27-December-2025 - Lenio, batch API Feb 2026 - Basti

    Client for the Semantic Scholar Graph API batch endpoint. It returns the
    SPECTER v2 embedding plus citations and references for many papers at once.
    Without an API key the shared (lower) rate limit applies.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.logger = Logger("SemanticScholarAPI")
        if api_key:
            self.logger.debug("SemanticScholarAPI initialized with API key (authenticated).")
        else:
            self.logger.debug("SemanticScholarAPI initialized without API key (unauthenticated).")

    # Status codes worth retrying: rate limited or temporary server problems
    RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

    def _post_with_retry(self, url: str, payload: dict, params: dict, headers: dict,
                         max_attempts: int = 5, base_delay: float = 2.0) -> list | None:
        """
        Sends one batch request. Retries with exponential backoff (2s, 4s, 8s, ...)
        on rate limiting (429), 5xx responses, timeouts and connection errors.
        Returns the parsed JSON list, or None if the request did not succeed.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(url, json=payload, params=params, headers=headers, timeout=120)
                resp.raise_for_status()
                return resp.json()
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status not in self.RETRY_STATUS_CODES:
                    self.logger.error(f"SemanticScholar batch request failed with HTTP {status}: {e}")
                    return None
                reason = f"HTTP {status}"
            except (requests.ConnectionError, requests.Timeout) as e:
                reason = type(e).__name__
            except Exception as e:
                self.logger.error(f"SemanticScholar batch request failed: {e}")
                return None

            if attempt < max_attempts:
                delay = base_delay * 2 ** (attempt - 1)
                self.logger.warning(
                    f"SemanticScholar batch request: {reason}, retry {attempt}/{max_attempts - 1} in {delay:.0f}s"
                )
                time.sleep(delay)

        self.logger.error(f"SemanticScholar batch request failed after {max_attempts} attempts")
        return None

    """
    Abstract: Batch-fetches SPECTER v2 embeddings (768-D), citations, and references
        from the SemanticScholar REST API for a list of arXiv IDs.

        Papers that SemanticScholar does not know yet return ``null`` in the
        response array – those are collected separately so the caller can send
        them to the uncaught-paper table.

    Args:
    - arxiv_ids: list[str]         – bare arXiv IDs (e.g. ``["2302.01234", "2401.05678"]``)
    - batch_size: int              – papers per HTTP request (max 500, default 400)
    - pause_seconds: float         – sleep between batches for rate-limit safety

    Returns: tuple(found, not_found)
        found: list[dict] – each dict has keys:
            ``arxiv_id``, ``s2_id``, ``embedding_768d``, ``citation_arxiv_ids``,
            ``reference_arxiv_ids``, ``non_arxiv_citation_count``, ``non_arxiv_reference_count``
        not_found: list[str] – arXiv IDs that returned null (not on SemanticScholar)
    """
    def fetch_batch(
        self,
        arxiv_ids: list[str],
        batch_size: int = 400,
        pause_seconds: float = 1.0,
    ) -> tuple[list[dict], list[str]]:
        


        url = "https://api.semanticscholar.org/graph/v1/paper/batch"
        fields = "externalIds,embedding.specter_v2,citations.externalIds,references.externalIds"
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        found: list[dict] = []
        not_found: list[str] = []

        # iteriert durch die arxiv ids in batches, um die API zu schonen
        for start in range(0, len(arxiv_ids), batch_size):
            chunk = arxiv_ids[start:start + batch_size]
            payload = {"ids": [f"ARXIV:{aid}" for aid in chunk]}

            results = self._post_with_retry(url, payload, {"fields": fields}, headers)
            if results is None:
                # Not reachable after all retries: the caller puts these papers
                # into the uncaught queue so they are tried again later.
                not_found.extend(chunk)
                continue

            # alle unbekannten paper (null in response) sammeln, damit caller sie uncaught-paper-tabelle schicken kann
            for i, item in enumerate(results):
                arxiv_id = chunk[i] if i < len(chunk) else None
                if item is None or not isinstance(item, dict):
                    if arxiv_id:
                        not_found.append(arxiv_id)
                    continue
                # s2_id, embedding, citation arXiv IDs, reference arXiv IDs extrahieren
                s2_id = item.get("paperId")
                embedding_data = item.get("embedding")
                vector_768 = None
                if embedding_data and isinstance(embedding_data, dict):
                    vector_768 = embedding_data.get("vector")

                # citation arXiv IDs extrahieren
                citation_arxiv_ids = []
                non_arxiv_citation_count = 0
                for cit in (item.get("citations") or []):
                    ext = (cit or {}).get("externalIds") or {}
                    cit_arxiv = ext.get("ArXiv")
                    if cit_arxiv:
                        citation_arxiv_ids.append(cit_arxiv)
                    else:
                        non_arxiv_citation_count += 1

                # reference arXiv IDs extrahieren
                reference_arxiv_ids = []
                non_arxiv_reference_count = 0
                for ref in (item.get("references") or []):
                    ext = (ref or {}).get("externalIds") or {}
                    ref_arxiv = ext.get("ArXiv")
                    if ref_arxiv:
                        reference_arxiv_ids.append(ref_arxiv)
                    else:
                        non_arxiv_reference_count += 1

                # nur paper mit gültigem embedding zurückgeben, damit caller sie direkt in embedding-tabelle speichern kann – paper ohne embedding (z.B. weil S2 sie kennt aber noch nicht verarbeitet hat) werden wie unbekannte paper behandelt und in not_found gesammelt
                if vector_768 is None:
                    
                    if arxiv_id:
                        not_found.append(arxiv_id)
                    continue
                    # zum schluss alle gefundenen paper mit embedding und extrahierten citation/reference arXiv IDs zurückgeben
                found.append({
                    "arxiv_id": arxiv_id,
                    "s2_id": s2_id,
                    "embedding_768d": vector_768,
                    "citation_arxiv_ids": citation_arxiv_ids,
                    "reference_arxiv_ids": reference_arxiv_ids,
                    "non_arxiv_citation_count": non_arxiv_citation_count,
                    "non_arxiv_reference_count": non_arxiv_reference_count,
                })

            self.logger.info(
                f"Batch {start // batch_size + 1}: "
                f"{len(chunk)} requested, {len([r for r in results if r])} returned"
            )
            if start + batch_size < len(arxiv_ids):
                time.sleep(pause_seconds)

        self.logger.info(
            f"Batch fetch complete: {len(found)} found, {len(not_found)} not found "
            f"out of {len(arxiv_ids)} total"
        )
        return found, not_found