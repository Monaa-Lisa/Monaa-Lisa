import asyncio
import time
from typing import Tuple

import requests
import semanticscholar.Paper as SemanticScholarPaper
from semanticscholar import AsyncSemanticScholar

from SemanticPaper.api.arxiv import ArxivAPI
from object.paper import Paper
from util.logger import Logger


"""
27-December-2025 - Lenio
Abstract: A client for interacting with the Semantic Scholar API.
"""
class SemanticScholarAPI:

    """
    27-December-2025 - Lenio
    Initializes the Semantic Scholar API client.
    Args:
        api_key (str | None): Optional API key for authenticated requests.
    Note: Without an API key, the client will operate in unauthenticated mode with limited rate limits.
    """
    def __init__(self, api_key: str | None = None):
        self.client = AsyncSemanticScholar(api_key=api_key)
        self.api_key = api_key
        self.logger = Logger("SemanticScholarAPI")
        if api_key:
            self.logger.debug("SemanticScholarAPI initialized with API key (authenticated).")
        else:
            self.logger.debug("SemanticScholarAPI initialized without API key (unauthenticated).")

    """
    27-December-2025 - Lenio
    Fetches a paper from Semantic Scholar by its Semantic Scholar ID.
    Args:
        semantic_scholar_id (str): The Semantic Scholar ID of the paper to fetch.
    Returns:
        Paper: The fetched paper object.
    """
    def fetch_paper(self, semantic_scholar_id: str) -> Paper:
        async def fetch_semantic_scholar_paper(paper_id: str):
            return await self.client.get_paper(paper_id)

        return asyncio.run(fetch_semantic_scholar_paper(semantic_scholar_id))

    """
    27-December-2025 - Lenio
    Fetches citations for a given paper from Semantic Scholar.
    Args:
        p_paper (Paper): The paper object for which to fetch citations.
        arxiv_client (ArxivAPI): An instance of the ArxivAPI to fetch papers
    Returns:
        Tuple[list[Paper], list[SemanticScholarPaper]]: A tuple containing two lists:
            - A list of Paper objects for citations found on arXiv.
            - A list of SemanticScholarPaper objects for citations not found on arXiv.
    """
    def fetch_citations(self, p_paper: Paper, arxiv_client: ArxivAPI) -> Tuple[list[Paper], list[SemanticScholarPaper]]:
        async def get_citations(paper_obj: Paper):
            entry_id = paper_obj.entry_id or ""
            parts = entry_id.split("/")
            raw_id = "/".join(parts[1:]) if len(parts) >= 2 else (parts[-1] if parts else "")
            normalized_paper_id = raw_id.split("v")[0] if raw_id else ""

            paper = await self.client.get_paper(f"ARXIV:{normalized_paper_id}")
            return getattr(paper, "citations", []) or []

        citations = asyncio.run(get_citations(p_paper))

        def _external_ids(obj) -> dict:
            ext = getattr(obj, "externalIds", None)
            return ext if isinstance(ext, dict) else {}

        citation_arxiv_ids: list[str] = []
        citations_not_present: list[SemanticScholarPaper] = []

        for c in citations:
            ext = _external_ids(c)
            arxiv_id = ext.get("ArXiv")
            if arxiv_id:
                citation_arxiv_ids.append(arxiv_id)
            else:
                citations_not_present.append(c)

        if citation_arxiv_ids:
            self.logger.info(citation_arxiv_ids)
            citations_on_arxiv = arxiv_client.fetch_papers_by_ids(citation_arxiv_ids)
        else:
            citations_on_arxiv = []
        return (citations_on_arxiv, citations_not_present)


    """
    27-December-2025 - Lenio
    Fetches references for a given paper from Semantic Scholar.
    Args:
        p_paper (Paper): The paper object for which to fetch references.
        arxiv_client (ArxivAPI): An instance of the ArxivAPI to fetch papers
    Returns:
        Tuple[list[Paper], list[SemanticScholarPaper]]: A tuple containing two lists:
            - A list of Paper objects for references found on arXiv.
            - A list of SemanticScholarPaper objects for references not found on arXiv.
    """
    def fetch_references(self, p_paper: Paper, arxiv_client: ArxivAPI) -> Tuple[list[Paper], list[SemanticScholarPaper]]:
        async def get_references(paper_obj: Paper):
            entry_id = paper_obj.entry_id or ""
            parts = entry_id.split("/")
            raw_id = "/".join(parts[1:]) if len(parts) >= 2 else (parts[-1] if parts else "")
            normalized_paper_id = raw_id.split("v")[0] if raw_id else ""

            paper = await self.client.get_paper(f"ARXIV:{normalized_paper_id}")
            return getattr(paper, "references", []) or []

        references = asyncio.run(get_references(p_paper))

        def _external_ids(obj) -> dict:
            ext = getattr(obj, "externalIds", None)
            return ext if isinstance(ext, dict) else {}

        references_arxiv_ids: list[str] = []
        references_not_present: list[SemanticScholarPaper] = []

        for r in references:
            ext = _external_ids(r)
            arxiv_id = ext.get("ArXiv")
            if arxiv_id:
                references_arxiv_ids.append(arxiv_id)
            else:
                references_not_present.append(r)

        if references_arxiv_ids:
            self.logger.info(references_arxiv_ids)
            references_on_arxiv = arxiv_client.fetch_papers_by_ids(references_arxiv_ids)
        else:
            references_on_arxiv = []
        return (references_on_arxiv, references_not_present)


    # ------------------------------------------------------------------
    # Batch API methods – Feb 2026 – Basti
    # ------------------------------------------------------------------

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

            try:
                # semanticscholar hat keinen offiziellen batch-endpoint in der python library, daher direkt mit requests
                resp = requests.post(
                    url,
                    json=payload,
                    params={"fields": fields},
                    headers=headers,
                    timeout=120,
                )
                
                resp.raise_for_status()
                results = resp.json()
            except Exception as e:

                self.logger.error(f"SemanticScholar batch request failed: {e}")
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