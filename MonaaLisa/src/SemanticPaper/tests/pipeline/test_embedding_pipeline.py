import pytest
import numpy as np
from unittest.mock import Mock, patch, mock_open

from MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline import (
    EmbeddingPipeline,
    _get_available_memory_gb,
    _log_memory_status,
)


@pytest.fixture
def pipeline():
    """Creates an EmbeddingPipeline with mocked PCA/UMAP models."""
    with patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.cfg'), \
         patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.Logger'):
        # Bypass __init__ entirely so we don't hit _load_models / disk access
        pipe = object.__new__(EmbeddingPipeline)
        pipe._pca = Mock()
        pipe._umap = Mock()
        pipe._pca_path = Mock()
        pipe._umap_path = Mock()
        return pipe


class TestGetAvailableMemoryGb:
    """Tests conditional logic in _get_available_memory_gb()."""

    def test_returns_gb_when_memavailable_line_present(self):
        """
        Tests the branch: if line.startswith("MemAvailable:") -> parse and return GB.

        Without this branch the function would always return None and all
        memory checks would be silently skipped.
        """
        fake_meminfo = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         2048000 kB\n"
            "MemAvailable:    8388608 kB\n"  # 8 GB
        )
        # Mock open() to return our fake /proc/meminfo content
        with patch("builtins.open", mock_open(read_data=fake_meminfo)):
            result = _get_available_memory_gb()

        assert result is not None
        # 8388608 kB = 8 GB, so we check for approximate equality with a small tolerance
        assert result == pytest.approx(8388608 / (1024 * 1024), rel=1e-3)

    def test_returns_none_when_file_not_found(self):
        """
        Tests: except (FileNotFoundError, ...) -> return None

        On Windows or containers without /proc/meminfo, the function must
        return None instead of crashing.
        """
        # We only need to test one of the exceptions since they all lead to the same outcome (return None)
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = _get_available_memory_gb()

        assert result is None

    def test_returns_none_when_memavailable_line_missing(self):
        """
        Tests the implicit branch: no line starts with "MemAvailable:" -> return None.

        A malformed or truncated /proc/meminfo must not crash the pipeline.
        """
        fake_meminfo = (
            "MemTotal:       16384000 kB\n"
            "MemFree:         2048000 kB\n"
        )
        with patch("builtins.open", mock_open(read_data=fake_meminfo)):
            result = _get_available_memory_gb()

        assert result is None


class TestLogMemoryStatus:
    """Tests conditional logic in _log_memory_status()."""

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.logger')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline._get_available_memory_gb')
    def test_logs_warning_when_memory_below_2gb(self, mock_get_mem, mock_logger):
        """
        Tests: if avail < 2.0 -> logger.warning(...)

        When available memory is critically low, the pipeline must emit
        a WARNING so operators can react before OOM kills the process.
        """
        mock_get_mem.return_value = 1.5  # below 2.0 GB threshold

        _log_memory_status("test-context")

        mock_logger.warning.assert_called_once()
        mock_logger.debug.assert_not_called()

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.logger')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline._get_available_memory_gb')
    def test_logs_debug_when_memory_above_2gb(self, mock_get_mem, mock_logger):
        """
        Tests: else -> logger.debug(...)

        Normal memory levels should only produce DEBUG output, not flood
        operators with warnings.
        """
        mock_get_mem.return_value = 8.0  # plenty of memory

        _log_memory_status("test-context")

        mock_logger.debug.assert_called_once()
        mock_logger.warning.assert_not_called()

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.logger')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline._get_available_memory_gb')
    def test_does_nothing_when_memory_unavailable(self, mock_get_mem, mock_logger):
        """
        Tests: if avail is not None (False path) -> no logging at all.

        On systems without /proc/meminfo the function must silently skip
        logging rather than raising an exception.
        """
        mock_get_mem.return_value = None

        _log_memory_status("test-context")

        mock_logger.warning.assert_not_called()
        mock_logger.debug.assert_not_called()


class TestLoadModels:
    """Tests conditional logic in _load_models()."""

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.Logger')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.cfg')
    def test_raises_when_pca_model_not_found(self, mock_cfg, mock_logger_cls):
        """
        Tests: if not self._pca_path.exists() -> raise FileNotFoundError

        A missing PCA model file must fail fast with a clear error. Without
        this check, joblib.load would raise a cryptic exception later.
        """
        with pytest.raises(FileNotFoundError, match="PCA model not found"):
            EmbeddingPipeline(
                pca_model_path="/nonexistent/pca.pkl",
                umap_model_path="/nonexistent/umap.pkl",
            )

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.joblib')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline._get_available_memory_gb')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.Logger')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.cfg')
    def test_raises_when_umap_model_not_found(self, mock_cfg, mock_logger_cls,
                                               mock_get_mem, mock_joblib):
        """
        Tests: if not self._umap_path.exists() -> raise FileNotFoundError

        Same as PCA – the UMAP file must exist before we attempt to load it.
        """
        import tempfile, os
        # Create a real temp file for PCA so the first check passes
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as pca_f:
            pca_path = pca_f.name

        try:
            with pytest.raises(FileNotFoundError, match="UMAP model not found"):
                EmbeddingPipeline(
                    pca_model_path=pca_path,
                    umap_model_path="/nonexistent/umap.pkl",
                )
        finally:
            os.unlink(pca_path)


class TestBatchReduceTo128d:
    """Tests conditional logic in batch_reduce_to_128d()."""

    def test_reshapes_1d_input_to_2d(self, pipeline):
        """
        Tests: if matrix.ndim == 1 -> matrix = matrix.reshape(1, -1)

        A single flat vector (1-D) must be reshaped to (1, 768) before
        PCA transform, otherwise sklearn raises a ValueError.
        """
        single_vector = np.zeros(768, dtype=np.float32)  # 1-D
        pipeline._pca.transform.return_value = np.zeros((1, 128))

        result = pipeline.batch_reduce_to_128d(single_vector)

        # Verify PCA was called with a 2-D array
        call_args = pipeline._pca.transform.call_args[0][0]
        assert call_args.ndim == 2
        assert call_args.shape == (1, 768)

    def test_passes_2d_input_unchanged(self, pipeline):
        """
        Tests: if matrix.ndim == 1 (False path) -> no reshape

        A proper (N, 768) matrix must be forwarded directly without
        unnecessary reshaping.
        """
        batch = np.zeros((3, 768), dtype=np.float32)  # already 2-D
        pipeline._pca.transform.return_value = np.zeros((3, 128))

        result = pipeline.batch_reduce_to_128d(batch)

        call_args = pipeline._pca.transform.call_args[0][0]
        assert call_args.ndim == 2
        assert call_args.shape == (3, 768)


class TestBatchProjectTo2d:
    """Tests conditional logic and chunking in batch_project_to_2d()."""

    def test_reshapes_1d_input_to_2d(self, pipeline):
        """
        Tests: if matrix.ndim == 1 -> matrix = matrix.reshape(1, -1)

        A single flat 128-D vector must be reshaped before UMAP transform.
        """
        single_vector = np.zeros(128, dtype=np.float32)  # 1-D
        pipeline._umap.transform.return_value = np.array([[1.0, 2.0]])

        result = pipeline.batch_project_to_2d(single_vector)

        call_args = pipeline._umap.transform.call_args[0][0]
        assert call_args.ndim == 2
        assert call_args.shape == (1, 128)

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.UMAP_CHUNK_SIZE', 500)
    def test_small_batch_skips_chunking(self, pipeline):
        """
        Tests: if n_vectors <= UMAP_CHUNK_SIZE -> return self._umap.transform(matrix)

        Batches smaller than the chunk size must be processed in a single
        transform call without chunking overhead.
        """
        batch = np.zeros((10, 128), dtype=np.float32)  # 10 << 500
        pipeline._umap.transform.return_value = np.zeros((10, 2))

        result = pipeline.batch_project_to_2d(batch)

        # transform should be called exactly once (no chunking)
        assert pipeline._umap.transform.call_count == 1
        assert result.shape == (10, 2)

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.gc')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.UMAP_CHUNK_SIZE', 3)
    def test_large_batch_uses_chunking(self, mock_gc, pipeline):
        """
        Tests: n_vectors > UMAP_CHUNK_SIZE -> process in chunks

        When the batch exceeds UMAP_CHUNK_SIZE, the pipeline must split
        the input into chunks to prevent OOM. With 7 vectors and chunk
        size 3, we expect 3 chunks: [3, 3, 1].
        """
        batch = np.zeros((7, 128), dtype=np.float32)
        # Return matching shapes for each chunk: (3,2), (3,2), (1,2)
        pipeline._umap.transform.side_effect = [
            np.ones((3, 2)),
            np.ones((3, 2)) * 2,
            np.ones((1, 2)) * 3,
        ]

        result = pipeline.batch_project_to_2d(batch)

        # 3 chunks -> 3 transform calls
        assert pipeline._umap.transform.call_count == 3
        assert result.shape == (7, 2)

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.gc')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.UMAP_CHUNK_SIZE', 3)
    def test_gc_collect_called_between_chunks_but_not_after_last(self, mock_gc, pipeline):
        """
        Tests: if end < n_vectors -> gc.collect()

        Garbage collection must run between chunks to free memory, but
        there is also a final gc.collect() after all chunks. For 2 chunks
        (5 vectors, chunk_size=3) we expect gc.collect() to be called
        between chunk 1 and 2 (end < n_vectors) plus 1 final call = 2 total.
        """
        batch = np.zeros((5, 128), dtype=np.float32)
        pipeline._umap.transform.side_effect = [
            np.ones((3, 2)),
            np.ones((2, 2)),
        ]

        pipeline.batch_project_to_2d(batch)

        # 1 call between chunks (end=3 < 5) + 1 final call = 2
        assert mock_gc.collect.call_count == 2

    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.gc')
    @patch('MonaaLisa.src.SemanticPaper.pipeline.embedding_pipeline.UMAP_CHUNK_SIZE', 5)
    def test_exact_chunk_size_batch_skips_chunking(self, mock_gc, pipeline):
        """
        Tests: if n_vectors <= UMAP_CHUNK_SIZE (boundary: n == UMAP_CHUNK_SIZE)

        A batch that is exactly UMAP_CHUNK_SIZE should take the fast path
        (single transform call) since chunking is only needed for larger batches.
        """
        batch = np.zeros((5, 128), dtype=np.float32)  # exactly chunk size
        pipeline._umap.transform.return_value = np.zeros((5, 2))

        result = pipeline.batch_project_to_2d(batch)

        assert pipeline._umap.transform.call_count == 1
        assert result.shape == (5, 2)
