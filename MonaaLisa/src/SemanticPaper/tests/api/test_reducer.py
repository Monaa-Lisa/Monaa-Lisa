import pytest
from unittest.mock import Mock, patch
import numpy as np
import sys

# Mock umap before importing reducer to prevent import errors
sys.modules['umap'] = Mock()

from MonaaLisa.src.SemanticPaper.machine_learning.reducer import UMAPReducer
from MonaaLisa.src.object.embedding import Embedding


@pytest.fixture
def reducer():
    """Creates a UMAPReducer instance with mocked external dependencies."""
    with patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.Logger'), \
         patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.cfg') as mock_cfg, \
         patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.joblib'):
        mock_cfg.get_int.side_effect = lambda section, key, default: default
        reducer = UMAPReducer()
        reducer.logger = Mock()
        reducer.min_fit_samples = 25
        reducer.refit_growth = 200
        return reducer


@pytest.fixture
def mock_embedding():
    """Creates a mock Embedding object."""
    def _create_embedding(paper_id="paper_1", dim=768):
        emb = Mock(spec=Embedding)
        emb.content = np.random.rand(dim).tolist()
        emb.belonging_paper_entry_id = paper_id
        return emb
    return _create_embedding


class TestLoadModelFromDisk:
    """Tests the conditional logic in _load_model_from_disk()."""

    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.joblib.load')
    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.Path.exists')
    def test_handles_exception_during_load_gracefully(self, mock_exists, mock_load, reducer):
        """
        Tests: except Exception as exc: self.logger.warning(...)

        Corrupted model files or loading errors should not crash the application.
        """
        mock_exists.return_value = True
        mock_load.side_effect = Exception("Corrupted file")

        reducer._load_model_from_disk()

        reducer.logger.warning.assert_called_once()
        assert reducer._reducer is None

class TestTransform:
    """Tests conditional logic in transform()."""

    def test_returns_none_when_reducer_is_none(self, reducer, mock_embedding):
        """
        Tests: if reducer is None: return None

        Without this check, calling reducer.transform() would crash with AttributeError.
        """
        reducer._reducer = None
        emb = mock_embedding()

        result = reducer.transform(emb, {emb.belonging_paper_entry_id: emb})

        assert result is None

    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.np.asarray')
    def test_returns_none_when_transform_raises_exception(self, mock_asarray, reducer, mock_embedding):
        """
        Tests: except Exception as exc: self.logger.error(...) return None

        UMAP transform can fail for various reasons (incompatible dimensions, etc.).
        The exception handler prevents crashes.
        """
        mock_reducer = Mock()
        mock_reducer.transform.side_effect = Exception("Transform failed")
        reducer._reducer = mock_reducer

        emb = mock_embedding()
        mock_asarray.return_value = np.random.rand(1, 768)

        result = reducer.transform(emb, {emb.belonging_paper_entry_id: emb})

        assert result is None
        reducer.logger.error.assert_called_once()

    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.np.asarray')
    def test_returns_coordinates_when_transform_succeeds(self, mock_asarray, reducer, mock_embedding):
        """
        Tests successful transform path: return coords[0].tolist()
        """
        mock_reducer = Mock()
        expected_coords = np.array([[1.5, 2.5]])
        mock_reducer.transform.return_value = expected_coords
        reducer._reducer = mock_reducer

        emb = mock_embedding()
        mock_asarray.return_value = np.random.rand(1, 768)

        result = reducer.transform(emb, {emb.belonging_paper_entry_id: emb})

        assert result == [1.5, 2.5]


class TestNotifyDatasetChange:
    """Tests the conditional logic in notify_dataset_change()."""

    def test_returns_early_when_below_min_fit_samples(self, reducer, mock_embedding):
        """
        Tests: if total < self.min_fit_samples: return

        Without this check, UMAP would try to fit on insufficient data and fail.
        """
        # we have 10 embeddings, but min_fit_samples is set to 25, so should return early
        embeddings = {f"paper_{i}": mock_embedding(f"paper_{i}") for i in range(10)}
        reducer.min_fit_samples = 25

        reducer.notify_dataset_change(embeddings)

        # Should return early, no fitting should occur
        assert reducer._reducer is None

    def test_fits_initial_reducer_when_reducer_is_none(self, reducer, mock_embedding):
        """
        Tests: if needs_initial_fit: ... self._fit_reducer(...)

        First time reaching min_fit_samples should trigger initial fit.
        """
        # We have 30 embeddings, which is above the min_fit_samples threshold of 25,
        # and _reducer is None, so should fit initial reducer
        embeddings = {f"paper_{i}": mock_embedding(f"paper_{i}") for i in range(30)}
        reducer.min_fit_samples = 25
        reducer._reducer = None


        with patch.object(reducer, '_fit_reducer') as mock_fit:
            reducer.notify_dataset_change(embeddings)

            mock_fit.assert_called_once()
            assert len(mock_fit.call_args[0][0]) == 30

    def test_does_not_refit_when_growth_threshold_not_reached(self, reducer, mock_embedding):
        """
        Tests: if not needs_growth_refit: return

        Should not refit if we haven't added enough new embeddings.
        """
        embeddings = {f"paper_{i}": mock_embedding(f"paper_{i}") for i in range(50)}
        reducer.min_fit_samples = 25
        reducer.refit_growth = 200
        reducer._reducer = Mock()
        reducer._last_fit_count = 40

        with patch.object(reducer, '_fit_reducer') as mock_fit:
            reducer.notify_dataset_change(embeddings)

            # Only 10 new embeddings, below refit_growth threshold
            mock_fit.assert_not_called()

    def test_starts_refit_thread_when_growth_threshold_reached(self, reducer, mock_embedding):
        """
        Tests: if needs_growth_refit: ... self._refit_thread = threading.Thread(...)

        When enough new embeddings are added, a background refit should start.
        """
        embeddings = {f"paper_{i}": mock_embedding(f"paper_{i}") for i in range(250)}
        reducer.min_fit_samples = 25
        reducer.refit_growth = 200
        reducer._reducer = Mock()
        reducer._last_fit_count = 40

        with patch.object(reducer, '_fit_reducer') as mock_fit:
            reducer.notify_dataset_change(embeddings)

            # 210 new embeddings, above refit_growth threshold
            # Should start a new thread to refit
            assert reducer._refit_thread is not None

    def test_does_not_start_new_refit_thread_if_one_is_alive(self, reducer, mock_embedding):
        """
        Tests: if self._refit_thread and self._refit_thread.is_alive(): return

        Prevents multiple concurrent refit operations.
        """
        embeddings = {f"paper_{i}": mock_embedding(f"paper_{i}") for i in range(250)}
        reducer.min_fit_samples = 25
        reducer.refit_growth = 200
        reducer._reducer = Mock()
        reducer._last_fit_count = 40

        # Mock an alive thread
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        reducer._refit_thread = mock_thread

        with patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.threading.Thread') as mock_thread_class:
            reducer.notify_dataset_change(embeddings)

            # Should not create a new thread
            mock_thread_class.assert_not_called()


class TestEnsureReducer:
    """Tests _ensure_reducer() conditional logic."""

    def test_returns_existing_reducer_if_already_fitted(self, reducer, mock_embedding):
        """
        Tests: if self._reducer is not None: return self._reducer

        Should return immediately if reducer already exists.
        """
        existing_reducer = Mock()
        reducer._reducer = existing_reducer
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]

        result = reducer._ensure_reducer(embeddings)

        assert result == existing_reducer

    def test_returns_none_when_not_enough_embeddings(self, reducer, mock_embedding):
        """
        Tests: if len(embeddings_list) < self.min_fit_samples: return None

        Cannot fit UMAP with insufficient data.
        """
        reducer._reducer = None
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(10)]

        result = reducer._ensure_reducer(embeddings)

        assert result is None
        reducer.logger.debug.assert_called()

    def test_fits_reducer_and_returns_it_when_enough_embeddings(self, reducer, mock_embedding):
        """
        Tests successful fit path: self._fit_reducer(...) return self._reducer
        """
        reducer._reducer = None
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]

        with patch.object(reducer, '_fit_reducer') as mock_fit:
            mock_new_reducer = Mock()

            def set_reducer(*args, **kwargs):
                reducer._reducer = mock_new_reducer

            mock_fit.side_effect = set_reducer

            result = reducer._ensure_reducer(embeddings)

            assert result == mock_new_reducer
            mock_fit.assert_called_once()


class TestFitReducer:
    """Tests _fit_reducer() conditional logic."""

    def test_returns_early_when_embeddings_not_increased(self, reducer, mock_embedding):
        """
        Tests: if self._reducer is not None and len(embeddings) <= self._last_fit_count: return

        Prevents unnecessary refitting when dataset hasn't grown.
        """
        reducer._reducer = Mock()
        reducer._last_fit_count = 50
        # Provide 40 embeddings, which is less than or equal to last_fit_count of 50,
        # so should return early
        embeddings = [mock_embedding(f"paper_{i}") for i in range(40)]

        with patch.object(reducer, '_to_matrix') as mock_to_matrix:
            reducer._fit_reducer(embeddings)

            # Should return early, _to_matrix should not be called
            mock_to_matrix.assert_not_called()

    def test_returns_early_when_to_matrix_returns_none(self, reducer, mock_embedding):
        """
        Tests: if vectors is None: return

        _to_matrix can return None if not enough valid embeddings.
        """
        reducer._reducer = None
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]

        with patch.object(reducer, '_to_matrix', return_value=(None, None)):
            reducer._fit_reducer(embeddings)

            # Should return early without fitting
            assert reducer._reducer is None

    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.umap.UMAP')
    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.joblib.dump')
    def test_fits_unsupervised_umap_when_labels_are_none(self, mock_dump, mock_umap_class, reducer, mock_embedding):
        """
        Tests: if y is not None: reducer.fit(vectors, y=...) else: reducer.fit(vectors)

        Should call fit without labels when y is None.
        """
        reducer._reducer = None
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]
        vectors = np.random.rand(30, 768)

        mock_umap_instance = Mock()
        mock_umap_class.return_value = mock_umap_instance

        with patch.object(reducer, '_to_matrix', return_value=(vectors, None)):
            reducer._fit_reducer(embeddings, labels=None)

            # Should call fit without y parameter
            mock_umap_instance.fit.assert_called_once()
            call_args = mock_umap_instance.fit.call_args
            assert 'y' not in call_args[1] or call_args[1].get('y') is None

    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.umap.UMAP')
    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.joblib.dump')
    def test_fits_supervised_umap_when_labels_provided(self, mock_dump, mock_umap_class, reducer, mock_embedding):
        """
        Tests: if y is not None: reducer.fit(vectors, y=y_encoded)

        Should call fit with encoded labels when y is provided.
        """
        reducer._reducer = None
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]
        vectors = np.random.rand(30, 768)
        y = ["label_a"] * 15 + ["label_b"] * 15

        mock_umap_instance = Mock()
        mock_umap_class.return_value = mock_umap_instance

        with patch.object(reducer, '_to_matrix', return_value=(vectors, y)):
            reducer._fit_reducer(embeddings, labels={"paper_0": "label_a"})

            # Should call fit with y parameter
            mock_umap_instance.fit.assert_called_once()
            call_args = mock_umap_instance.fit.call_args
            assert 'y' in call_args[1]

    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.umap.UMAP')
    @patch('MonaaLisa.src.SemanticPaper.machine_learning.reducer.joblib.dump')
    def test_handles_persist_exception_gracefully(self, mock_dump, mock_umap_class, reducer, mock_embedding):
        """
        Tests: except Exception as exc: self.logger.warning(...)

        Failure to persist model should not crash the application.
        """
        reducer._reducer = None
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]
        vectors = np.random.rand(30, 768)

        mock_umap_instance = Mock()
        mock_umap_class.return_value = mock_umap_instance
        mock_dump.side_effect = Exception("Disk full")

        with patch.object(reducer, '_to_matrix', return_value=(vectors, None)):
            reducer._fit_reducer(embeddings)

            # Should still set the reducer even if persist fails
            assert reducer._reducer == mock_umap_instance
            reducer.logger.warning.assert_called_once()


class TestToMatrix:
    """Tests _to_matrix() conditional logic."""

    def test_returns_none_when_not_enough_labeled_embeddings(self, reducer, mock_embedding):
        """
        Tests: if len(vectors) < self.min_fit_samples: ... return None, None

        Falls back to unsupervised when insufficient labeled samples.
        """
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(10)]
        labels = {f"paper_{i}": "label_a" for i in range(5)}

        result = reducer._to_matrix(embeddings, labels)

        assert result == (None, None)

    def test_falls_back_to_unsupervised_when_labels_insufficient(self, reducer, mock_embedding):
        """
        Tests: if len(vectors) < self.min_fit_samples: ... vectors.clear() ...

        Should collect all embeddings without labels after fallback.
        """
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]
        labels = {f"paper_{i}": "label_a" for i in range(5)}  # Only 5 labeled

        matrix, y = reducer._to_matrix(embeddings, labels)

        # Should have fallen back to unsupervised
        assert matrix is not None
        assert matrix.shape[0] == 30  # All embeddings used
        assert y is None

    def test_skips_embeddings_without_labels_in_supervised_mode(self, reducer, mock_embedding):
        """
        Tests: if label is None: continue

        Embeddings without labels should be skipped in supervised mode.
        """
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]
        labels = {f"paper_{i}": f"label_{i % 2}" for i in range(15)}  # Only first 15 labeled

        matrix, y = reducer._to_matrix(embeddings, labels)

        # Should only use the 15 labeled embeddings, but that's below min_fit_samples
        # So should fall back to unsupervised with all 30
        assert matrix.shape[0] == 30

    def test_skips_embeddings_with_none_content(self, reducer, mock_embedding):
        """
        Tests: if emb.content is None: continue

        Embeddings with None content should be skipped.
        """
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]
        # Set some embeddings to have None content
        for i in range(5):
            embeddings[i].content = None

        matrix, y = reducer._to_matrix(embeddings, labels=None)

        # Should only use the 25 embeddings with valid content
        assert matrix is not None
        assert matrix.shape[0] == 25

    def test_returns_matrix_and_labels_when_supervised_successful(self, reducer, mock_embedding):
        """
        Tests: if labels and y and len(y) == len(vectors): return matrix, y

        Successful supervised path should return both matrix and labels.
        """
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]
        labels = {f"paper_{i}": f"label_{i % 2}" for i in range(30)}  # All labeled

        matrix, y = reducer._to_matrix(embeddings, labels)

        assert matrix is not None
        assert matrix.shape[0] == 30
        assert y is not None
        assert len(y) == 30

    def test_returns_matrix_only_when_unsupervised(self, reducer, mock_embedding):
        """
        Tests: return matrix, None

        Unsupervised path should return matrix with None labels.
        """
        reducer.min_fit_samples = 25
        embeddings = [mock_embedding(f"paper_{i}") for i in range(30)]

        matrix, y = reducer._to_matrix(embeddings, labels=None)

        assert matrix is not None
        assert matrix.shape[0] == 30
        assert y is None