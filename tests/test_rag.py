"""Tests for RAG (Retrieval-Augmented Generation) functions."""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from translation.rag import cosine_similarity, is_rag_available


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity of 1.0."""
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = cosine_similarity(vec, vec)
        assert abs(result - 1.0) < 1e-6

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity of -1.0."""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([-1.0, 0.0, 0.0], dtype=np.float32)
        result = cosine_similarity(vec1, vec2)
        assert abs(result - (-1.0)) < 1e-6

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity of 0.0."""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        result = cosine_similarity(vec1, vec2)
        assert abs(result) < 1e-6

    def test_similar_vectors(self):
        """Similar vectors should have high positive similarity."""
        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.array([1.1, 2.1, 3.1], dtype=np.float32)
        result = cosine_similarity(vec1, vec2)
        assert result > 0.99  # Very similar

    def test_empty_vectors(self):
        """Empty vectors should return 0.0."""
        vec1 = np.array([], dtype=np.float32)
        vec2 = np.array([1.0, 2.0], dtype=np.float32)
        result = cosine_similarity(vec1, vec2)
        assert result == 0.0

    def test_zero_vector(self):
        """Zero vector should return near-zero (due to epsilon)."""
        vec1 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = cosine_similarity(vec1, vec2)
        assert abs(result) < 1e-6

    def test_high_dimensional(self):
        """Should work with high-dimensional vectors (like embeddings)."""
        # Typical embedding dimension
        dim = 1536
        vec1 = np.random.randn(dim).astype(np.float32)
        vec2 = np.random.randn(dim).astype(np.float32)
        result = cosine_similarity(vec1, vec2)
        assert -1.0 <= result <= 1.0

    def test_returns_float(self):
        """Should return a Python float, not numpy type."""
        vec1 = np.array([1.0, 2.0], dtype=np.float32)
        vec2 = np.array([3.0, 4.0], dtype=np.float32)
        result = cosine_similarity(vec1, vec2)
        assert isinstance(result, float)


class TestRagAvailability:
    """Tests for RAG availability checking."""

    def test_is_rag_available_returns_bool(self):
        """is_rag_available should return a boolean."""
        result = is_rag_available()
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
