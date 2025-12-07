from sentence_transformers import SentenceTransformer
from ..api.arxiv import ArxivAPI
from sklearn.manifold import TSNE
import numpy as np
import torch
import os
from object.paper import Paper
from util.logger import Logger
from config import cfg

from object.embedding import Embedding

"""
03-August-2025 - Lenio
Abstract: This class is used to handle the model and its methods
Args: None
Returns: None
Annotation: largely refactored Bastians code here to fit the new structure
"""
class Model:

    def __init__(self, arxiv_client: ArxivAPI):
        """
        Testing it as of 4th May 2025 with this Pretrained Sentence Transformer
        replace this later with SciBERT or allenai/specter
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._arxiv = arxiv_client
        model_name = cfg.get("semanticpaper", "transformer_model", os.getenv("TRANSFORMER_MODEL", "all-MiniLM-L6-v2"))
        self._transformer = SentenceTransformer(model_name)
        self._model = self._transformer.to(self.device)
        self.logger = Logger("Model")
        self.logger.info(f"Using device: {self.device}")


    """
    03-August-2025 - Lenio
    Abstract: Returns the model object.
    Returns: SentenceTransformer model object
    """
    def get_model(self):
        return self._transformer

    """
    06-May-2025 - Basti
    Abstract: Takes a whole paper and embeds them chunk by chunk (chunk size - in chars! - pre-defined in constructor)
    Args:
    
    - paper: The to be worked with paper
    - chunk_size: size of chars in which the full text will be divided into
    
    Returns: dict -> containing the Result/Embedding + total of processed chunks
    Annotation: about to be deprecated, will be replaced with the embedding method of the PaperProcessor class
    """
    def parse_full_data(self, paper: Paper, chunk_size: int = 512):
        self.logger.info("Reading current paper...\n")
        self._arxiv.read_meta(paper)

        full_text = paper.get_formatted_text()
        if not full_text:
            self.logger.info("Processing PDF failed!")
            return None

        try:
            chunks = [full_text[i:i + chunk_size]
                     for i in range(0, len(full_text), chunk_size)]

            embeddings = []
            for c in chunks:
                c_embeddings = self.model.encode(c)
                embeddings.append(c_embeddings)

            final_embedding = np.mean(embeddings,axis=0)

            return {
                "Embedding": final_embedding,
                "Chunks_Processed": len(chunks)
            }
        except Exception as e:
            self.logger.info(f"Error processing embeddings for {paper.title} with error: {str(e)}")
            return None


    """
    19-06-2025 - Basti
    Abstract: Reduces a list of high-dimensional embedding vectors to 2D t-SNE coordinates for visualization/saving them easily into the database.
    Args:
    - embeddings: List or array of embedding vectors (e.g., output from parse_full_data)
    - random_state: Seed for reproducibility (default: 42) - this ensures determinism
    
    Returns: 
    - Tuple -> of (tsne1, tsne2) tuples one per embedding (x,y)
    """
    @staticmethod
    def extract_tsne_coordinates(embeddings, random_state=42):

        cleaned = []
        for e in embeddings:
            # extra check ob wir hier wirklich ein object.Embedding haben
            if isinstance(e, Embedding):
                vector = e.content
            # weiterer fall falls wir direkt nparrays oder lists bekommen
            elif hasattr(e, "content"):
                vector = getattr(e, "content")
            else:
                # letzter seltener fall wo wir direkt nparray/list kriegen
                vector = e

            # failed -> raise error und skip
            if vector is None:
                raise ValueError("Embedding content cannot be None")

            
            cleaned.append(np.asarray(vector, dtype=np.float32))

        embeddings = np.array(cleaned)
        if len(embeddings) < 2:
            raise ValueError("At least two embeddings are required for t-SNE.")
        
        perplexity = min(30, len(embeddings) - 1)
        tsne = TSNE(n_components=2, random_state=random_state, perplexity=perplexity)
        reduced = tsne.fit_transform(embeddings)
        return [tuple(map(float, coords)) for coords in reduced]