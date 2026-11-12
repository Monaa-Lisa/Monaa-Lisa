import hashlib
import os
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
import arxiv as arx
from typing import List, Optional, Dict

import requests

from object.citation import Citation

from object.paper_citation import PaperCitation
from object.paper_reference import PaperReference

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from Database.db_models import DBPaper
from util.logger import Logger
from object.reference import Reference
from object.embedding import Embedding
from lxml import etree


@dataclass
class Paper:
    entry_id: str
    title: str
    authors: List[str]
    abstract: str
    published: datetime
    url: str
    categories: Optional[str] = None
    references: list[Reference | PaperReference] = field(default_factory=list)
    citations: list[Citation | PaperCitation] = field(default_factory=list)
    tsne: Optional[Dict] = None
    embedding: Optional[Embedding] = None
    _grobid_xml: Optional[str] = None
    _paper_txt: Optional[str] = None
    _paper_logger = None
    _grobid_logger = None

    @property
    def logger(self):
        if Paper._paper_logger is None:
            Paper._paper_logger = Logger("Paper")
        return Paper._paper_logger

    @staticmethod
    def get_grobid_logger():
        if Paper._grobid_logger is None:
            Paper._grobid_logger = Logger("Grobid")
        return Paper._grobid_logger

    """
    26-July-2025 - Lenio
    Abstract: Returns a Paper object from an arXiv result.
    Args: arvix_result: arxiv.Result -> Arxiv result object containing paper metadata.
    Returns: Paper -> A Paper object with metadata from the arXiv result.
    """
    @classmethod
    def from_arxiv(cls, arxiv_result: arx.Result):
        entry_id = arxiv_result.entry_id.replace("http://arxiv.org/", "")
        pdf_url = arxiv_result.pdf_url
        if not pdf_url:
            slug = entry_id.split("/")[-1]
            if slug:
                pdf_url = f"https://arxiv.org/pdf/{slug}.pdf"
        return cls(
            entry_id=entry_id,  # Remove base URL
            title=arxiv_result.title,
            authors=[str(a) for a in arxiv_result.authors], # TODO # Normalize authors as objects
            abstract=arxiv_result.summary,
            published=arxiv_result.published,
            url=pdf_url
        )

    """
    26-July-2025 - Lenio
    Abstract: Converts the Paper object to a SQLAlchemy model.
    Args: DBPaper: SQLAlchemy model class for the paper.
    Returns: DBPaper -> An instance of the SQLAlchemy model with the paper's data.
    """
    def to_db_model(self):
        return DBPaper(
            entry_id=self.entry_id,
            title=self.title,
            authors=", ".join(self.authors),
            abstract=self.abstract,
            published=self.published,
            categories=self.categories,
            tsne=self.tsne if self.tsne else None,
            url=self.url,
        )


    """
    31-July-2025 - Lenio
    Abstract: Returns paper text if processed
    Returns: Optional[str] -> The processed paper text or None if not processed.
    """
    def get_formatted_text(self):
        return self._paper_txt if self._paper_txt else None


    """
    29-July-2025 - Lenio
    Abstract: Extracts metadata from the paper's PDF using Grobid.
    Args: None
    Returns: None
    """
    def extract_metadata(self):
        self._grobid_xml = self.extract_paper_text_semantic()
        """ - Basti - 13. August 2025
        Handling if Grobid returns no XML => skip section and reference extraction
        This used to cause an Exception
        """

        if not self._grobid_xml:
            self.logger.warning(f"No GROBID XML returned for {self.title}, skipping metadata extraction")
            self.references = []
            return
        sections = self.get_sections()
        if sections:
            for section in sections:
                self.logger.info(f"{section['title']}")
                # format text
                content = section['content'].strip().lstrip('.')
                wrapped_text = textwrap.fill(content,
                                             width=100,
                                             break_long_words=False,
                                             replace_whitespace=True,
                                             break_on_hyphens=True)
                self._paper_txt = wrapped_text

    """
    29-July-2025 - Lenio
    Abstract: Extracts references from the paper's PDF using Grobid.
    returns: List[Reference] -> A list of Reference objects found in the paper.
    """
    def extract_references(self) -> List['Reference']:
        references = []
        # Skip if no Grobid XML available
        if not self._grobid_xml:
            return references
        if self._grobid_xml is not None:
            try:
                data = self._grobid_xml.encode("utf-8")
                parser = etree.XMLParser(recover=True, huge_tree=True)
                root = etree.fromstring(data, parser=parser)
            except etree.XMLSyntaxError as e:
                self.logger.error(f"XML parse error while extracting references for '{self.title}': {e}")
                return []
            except Exception as e:
                self.logger.error(f"Unexpected error parsing references XML for '{self.title}': {e}")
                return []

            ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
            # Search for <div type="references"> in the <back> section
            references_xml = root.findall('.//tei:div[@type="references"]//tei:biblStruct', ns)
            for ref in references_xml:
                titles = ref.findall('.//tei:title', ns)
                if titles:
                    title_texts = [title.text or "" for title in titles]
                    # Only join non-empty strings
                    combined_title = ", ".join(filter(None, title_texts))
                    if combined_title:  # Only create reference if there is a title
                        references.append(Reference(self.entry_id, combined_title))

            if not references:
                self.logger.warning("Could not extract references from paper or none were found!")
                # Sometimes the xpath seems to fail, gotta look into this later
            return references
        return []

    """
    30-July-2025 - Lenio
    Abstract: Extracts sections from the paper's XML text.
    Args: 
    - root: ET.Element -> The root element of the XML document.
    - ns: dict -> A dictionary containing XML namespaces.
    """
    def get_sections(self) -> list[dict]:
        # Skip if no Grobid XML available
        if not self._grobid_xml:
            self.logger.warning(f"No GROBID XML available for {self.title}, skipping sections")
            return []
        try:
            data = self._grobid_xml.encode("utf-8")
            parser = etree.XMLParser(recover=True, huge_tree=True)
            root = etree.fromstring(data, parser=parser)
        except etree.XMLSyntaxError as e:
            self.logger.error(f"XML parse error while extracting sections for '{self.title}': {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error parsing sections XML for '{self.title}': {e}")
            return []
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        sections = []
        for section in root.findall('.//tei:body//tei:div', ns):
            # Get the section header and content xml elements
            head_element = section.find('.//tei:head', ns)
            content_elements = section.findall('.//tei:p', ns)
            if head_element is not None and content_elements is not None:
                # The section data dictionary
                section_data = {}
                # The index indicating the section number
                section_header_index = head_element.attrib.get('n', '')
                content = ""
                # Get all paragraphs in a section
                for paragraph in content_elements:
                    text = (paragraph.text or "").strip()
                    if text:
                        content += text + "\n"
                if section_header_index != "":
                    # If section has a number in its attribute 'n'
                    section_data['title'] = section_header_index + " " + (
                        head_element.text if head_element is not None else "")
                else:
                    """ Sometimes grobid get's Sections wrong so if there is a section without an index
                        we merge its content with the previous section.
                    """
                    if len(sections) >= 1:
                        sections[-1]['content'] += "\n" + content
                        continue
                    else:
                        self.logger.warning("Section without index found but no previous section to merge with!")
                        self.logger.warning(f"Section header: {head_element.text}")
                        self.logger.warning(f"Section content: {content}")
                        section_data['title'] = head_element.text if head_element is not None else ""
                # If section has a title add it's content to the section data
                section_data['content'] = content
                sections.append(section_data)
            else:
                """
                31-July-2025 - Lenio
                This seems to happen when a section does not contain any head, its debatable if this should lead
                to the sections content being merged with the previous section or if the section should be skipped.
                for now we skip it and log an error.
                """
                self.logger.error("No valid section found in the XML data!")
                self.logger.error(f"Section: {etree.tostring(section)}")
        return sections

    """
    27-July-2025 - Lenio
    Abstract: Extracts the full text of a paper using grobid from a given URL, only for testing right now.
    Args: url: str -> The URL of the paper to extract text from.
    Returns: Optional[str] -> The extracted text from the paper, or None if extraction fails.
    """
    def extract_paper_text_semantic(self) -> Optional[str]:
        local_logger = Paper.get_grobid_logger()
        temp_file_path = None
        try:
            pdf_url = self.url
            if not pdf_url:
                local_logger.warning(
                    "No PDF URL available for '%s'; skipping Grobid extraction", self.title
                )
                return None
            if not pdf_url.startswith(("http://", "https://")):
                pdf_url = f"https://{pdf_url.lstrip('/')}"
                # Persist sanitized URL so future calls reuse it
                self.url = pdf_url
            # Download PDF with timeout and streaming to avoid blocking and large memory usage
            response = requests.get(pdf_url, stream=True, timeout=(5, 60))
            if not response.ok:
                raise Exception(f"Failed to download PDF: HTTP Error Code is - {response.status_code}")

            # Create a temporary file to store the PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        tmp_file.write(chunk)
                temp_file_path = tmp_file.name

            # Send to Grobid for processing
            with open(temp_file_path, 'rb') as pdf_file:
                files = {'input': pdf_file}
                grobid_url = 'http://grobid:8070/api/processFulltextDocument'
                grobid_response = requests.post(
                    grobid_url,
                    files=files,
                    headers={'Accept': 'application/xml'},
                    timeout=(5, 120)
                )

            if not grobid_response.ok:
                raise Exception(f"Grobid-Processing failed: {grobid_response.status_code}")
            local_logger.info(f"Grobid processing finished successfully!")
            return grobid_response.text

        except Exception as e:
            local_logger.error(f"Error while extracting text: {str(e)}")
            return None

        finally:
            # Clean up the temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    local_logger.error(f"Failed to delete temporary file: {str(e)}")


    """
    25-May-2025 - Basti, updated 26-July-2025 - Lenio, Moved to paper.py 03-August-2025 - Lenio
    Abstract: Hashes the data of a arXiv Paper using SHA256 and returns its hash
    Args:
    
    - paper: Paper -> A given paper object
    
    Returns: str -> Unique hash of the paper
    """
    def hash_paper_details(self) -> str:
        to_hash = self.title + '|' + self.abstract
        self.hash = hashlib.sha256(to_hash.encode()).hexdigest()
        self.logger.debug(f"[DEBUG] Printing to hash text: {to_hash}")

        return self.hash