import gc
import os
from pathlib import Path

import joblib
import numpy as np

from util.logger import Logger
from config import cfg

logger = Logger("EmbeddingPipeline")

# Wir müssen das UMAP-Modell in Chunks laden, um OOM (Out Of Memory) auf Maschinen mit begrenztem RAM zu vermeiden
UMAP_CHUNK_SIZE = int(os.getenv("UMAP_CHUNK_SIZE", cfg.get("semanticpaper", "umap_chunk_size", "500")))


def _get_available_memory_gb() -> float | None:
    """
    Returns available system memory in GB, or None if unavailable.
    Works on Linux (including Docker/WSL) by reading /proc/meminfo.
    """
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    # Zeilenformat: "MemAvailable:   12345678 kB"
                    kb = int(line.split()[1])
                    return kb / (1024 * 1024) 
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return None


def _log_memory_status(context: str = ""):
    """Log current available memory if readable."""
    avail = _get_available_memory_gb()
    if avail is not None:
        level = "WARNING" if avail < 2.0 else "DEBUG"
        msg = f"[Memory] {context}: {avail:.2f} GB available"
        if level == "WARNING":
            logger.warning(msg)
        else:
            logger.debug(msg)

"""
Abstract: Loads pre-trained PCA and UMAP models and exposes methods to
    reduce raw SemanticScholar SPECTER v2 embeddings (768-D) into
    128-D representations stored in the DB, and further project them
    to 2-D coordinates for frontend visualisation.
"""
class EmbeddingPipeline:

    def __init__(self, pca_model_path: str | Path | None = None, umap_model_path: str | Path | None = None):
        """
        Args:
        - pca_model_path:  Path to the PCA .pkl (768 -> 128-D).  Resolved from
                           config / env if not given.
        - umap_model_path: Path to the UMAP .pkl (128 -> 2-D).  Same fallback.
        """
        if pca_model_path is None:
            pca_model_path = cfg.get(
                "semanticpaper", "pca_model_path",
                os.getenv("PCA_MODEL_PATH", "/app/data/models/pca_model_128d.pkl"),
            )
        if umap_model_path is None:
            umap_model_path = cfg.get(
                "semanticpaper", "umap_model_path",
                os.getenv("UMAP_MODEL_PATH", "/app/data/models/umap_model_2d.pkl"),
            )

        self._pca_path = Path(pca_model_path)
        self._umap_path = Path(umap_model_path)
        self._pca = None
        self._umap = None
        self._load_models()

    def _load_models(self):
        """
        Abstract: Loads PCA and UMAP models from disk.
        """
        if not self._pca_path.exists():
            logger.error(f"PCA model not found at {self._pca_path}")
            raise FileNotFoundError(f"PCA model not found: {self._pca_path}")
        if not self._umap_path.exists():
            logger.error(f"UMAP model not found at {self._umap_path}")
            raise FileNotFoundError(f"UMAP model not found: {self._umap_path}")

        logger.info(f"Loading PCA model from {self._pca_path} ...")
        self._pca = joblib.load(self._pca_path)
        logger.info(f"PCA model loaded (type: {type(self._pca).__name__})")

        _log_memory_status("Before UMAP load")

        # Vorab-Check: Warnung, wenn verfügbarer Speicher kritisch niedrig ist
        avail_gb = _get_available_memory_gb()
        if avail_gb is not None and avail_gb < 2.0:
            logger.warning(
                f"Low memory warning: Only {avail_gb:.2f} GB available. "
                f"UMAP model is {umap_size_gb:.2f} GB. OOM risk is high. "
                f"Consider increasing Docker/WSL memory or using a smaller model."
            )

        logger.info(f"Loading UMAP model from {self._umap_path} ...")
        umap_size_gb = self._umap_path.stat().st_size / (1024 ** 3)
        logger.info(f"UMAP file size: {umap_size_gb:.2f} GB – using mmap_mode='c' (copy-on-write) to reduce peak RAM")
        self._umap = joblib.load(self._umap_path, mmap_mode="c")
        logger.info(f"UMAP model loaded (type: {type(self._umap).__name__})")
        _log_memory_status("After UMAP load")

    # ---------- public API ----------

    def reduce_to_128d(self, vector_768d: list | np.ndarray) -> np.ndarray:
        """
        Abstract: Reduces a single 768-D SPECTER v2 vector to 128-D via PCA.
        Args:
        - vector_768d: 768-element list or ndarray
        Returns: np.ndarray of shape (128,)
        """
        arr = np.asarray(vector_768d, dtype=np.float32).reshape(1, -1)
        reduced = self._pca.transform(arr)
        return reduced[0]

    def project_to_2d(self, vector_128d: list | np.ndarray) -> tuple[float, float]:
        """
        Abstract: Projects a single 128-D embedding to 2-D via UMAP.
        Args:
        - vector_128d: 128-element list or ndarray
        Returns: (x, y) tuple of floats
        """
        arr = np.asarray(vector_128d, dtype=np.float32).reshape(1, -1)
        coords = self._umap.transform(arr)
        return float(coords[0][0]), float(coords[0][1])

    def process(self, vector_768d: list | np.ndarray) -> tuple[np.ndarray, tuple[float, float]]:
        """
        Abstract: Full pipeline – 768-D -> 128-D (PCA) -> 2-D (UMAP).
        Args:
        - vector_768d: 768-element list or ndarray (SPECTER v2)
        Returns: (embedding_128d, (x, y))
        """
        v128 = self.reduce_to_128d(vector_768d)
        coords = self.project_to_2d(v128)
        return v128, coords

    def batch_reduce_to_128d(self, vectors_768d: list[list] | np.ndarray) -> np.ndarray:
        """
        Abstract: Batch PCA reduction for multiple 768-D vectors.
        Args:
        - vectors_768d: (N, 768) array-like
        Returns: np.ndarray of shape (N, 128)
        """
        matrix = np.asarray(vectors_768d, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return self._pca.transform(matrix)

    def batch_project_to_2d(self, vectors_128d: list[list] | np.ndarray) -> np.ndarray:
        """
        Abstract: Batch UMAP projection for multiple 128-D vectors.
            Processes in chunks of UMAP_CHUNK_SIZE to prevent OOM on systems
            with limited RAM (e.g., 16 GB total, 8 GB to WSL).
        Args:
        - vectors_128d: (N, 128) array-like
        Returns: np.ndarray of shape (N, 2)
        """
        matrix = np.asarray(vectors_128d, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)

        n_vectors = matrix.shape[0]

        # Kleine Batches benötigen kein Chunking, also direkt verarbeiten
        if n_vectors <= UMAP_CHUNK_SIZE:
            return self._umap.transform(matrix)

        # Verarbeitung in Chunks, um den maximalen Speicherverbrauch zu begrenzen
        logger.info(f"Processing {n_vectors} vectors in chunks of {UMAP_CHUNK_SIZE} to limit memory usage...")
        results = []

        for start in range(0, n_vectors, UMAP_CHUNK_SIZE):
            end = min(start + UMAP_CHUNK_SIZE, n_vectors)
            chunk = matrix[start:end]
            chunk_result = self._umap.transform(chunk)
            results.append(chunk_result)

            # Explizite Garbage Collection zwischen den Chunks, um Speicher freizugeben
            if end < n_vectors:
                gc.collect()
                # Speicherauslastung alle paar Chunks loggen, um Probleme frühzeitig zu erkennen
                if (end // UMAP_CHUNK_SIZE) % 5 == 0:
                    _log_memory_status(f"After chunk {end // UMAP_CHUNK_SIZE}")

        # Nach allen Chunks noch eine finale GC durchführen
        gc.collect()

        return np.vstack(results)

    def batch_process(self, vectors_768d: list[list] | np.ndarray) -> list[tuple[list[float], tuple[float, float]]]:
        """
        Abstract: Full batch pipeline – 768-D -> 128-D -> 2-D for N vectors.
        Args:
        - vectors_768d: (N, 768) array-like
        Returns: list of (embedding_128d_list, (x, y)) tuples
        """
        reduced = self.batch_reduce_to_128d(vectors_768d)
        projected = self.batch_project_to_2d(reduced)
        results = []
        for i in range(len(reduced)):
            emb_list = reduced[i].tolist()
            coords = (float(projected[i][0]), float(projected[i][1]))
            results.append((emb_list, coords))
        return results

    def is_ready(self) -> bool:
        """Returns True if both models are loaded."""
        return self._pca is not None and self._umap is not None
