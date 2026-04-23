"""
Embeddings Utility for Semantic Similarity

This module provides embedding-based semantic similarity for entity matching.
Uses sentence-transformers with caching for performance.

Key features:
- Lightweight all-MiniLM-L6-v2 model (fast, good quality)
- LRU cache for embeddings (table/column names don't change often)
- Graceful fallback when model unavailable
- Cosine similarity for semantic matching
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from config.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingMatcher:
    """
    Embedding-based semantic similarity matcher.
    
    Uses sentence-transformers for generating embeddings and cosine similarity
    for matching. Includes caching for performance.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding matcher.
        
        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """
        Load the sentence-transformers model.
        
        Gracefully handles model loading failures.
        """
        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded embedding model: {self.model_name}")
        except Exception as e:
            logger.warning(f"Failed to load embedding model {self.model_name}: {e}")
            self.model = None
    
    def is_available(self) -> bool:
        """
        Check if the embedding model is available.
        
        Returns:
            True if model is loaded and ready to use
        """
        return self.model is not None
    
    @lru_cache(maxsize=1000)
    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Get embedding for a text string with caching.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if model unavailable
        """
        if not self.model:
            return None
        
        try:
            # Normalize text for consistent caching
            normalized_text = text.lower().strip()
            embedding = self.model.encode([normalized_text])
            return embedding[0]
        except Exception as e:
            logger.warning(f"Failed to generate embedding for '{text}': {e}")
            return None
    
    def calculate_similarity(self, text1: str, text2: str) -> Optional[float]:
        """
        Calculate cosine similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0.0-1.0) or None if embeddings unavailable
        """
        embedding1 = self._get_embedding(text1)
        embedding2 = self._get_embedding(text2)
        
        if embedding1 is None or embedding2 is None:
            return None
        
        try:
            # Reshape for cosine_similarity function
            embedding1 = embedding1.reshape(1, -1)
            embedding2 = embedding2.reshape(1, -1)
            
            similarity = cosine_similarity(embedding1, embedding2)[0][0]
            return float(similarity)
        except Exception as e:
            logger.warning(f"Failed to calculate similarity between '{text1}' and '{text2}': {e}")
            return None
    
    def find_best_matches(
        self, 
        query: str, 
        candidates: List[str], 
        threshold: float = 0.7,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Find best matching candidates for a query using embeddings.
        
        Args:
            query: Query text to match
            candidates: List of candidate texts
            threshold: Minimum similarity threshold
            top_k: Maximum number of matches to return
            
        Returns:
            List of (candidate, similarity_score) tuples, sorted by similarity
        """
        if not self.is_available():
            return []
        
        matches = []
        
        for candidate in candidates:
            similarity = self.calculate_similarity(query, candidate)
            if similarity is not None and similarity >= threshold:
                matches.append((candidate, similarity))
        
        # Sort by similarity (descending) and return top_k
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_k]
    
    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._get_embedding.cache_clear()
        logger.info("Cleared embedding cache")


# Global instance for easy import
_embedding_matcher: Optional[EmbeddingMatcher] = None


def get_embedding_matcher() -> EmbeddingMatcher:
    """
    Get the global embedding matcher instance.
    
    Creates the instance on first call and reuses it for subsequent calls.
    
    Returns:
        EmbeddingMatcher instance
    """
    global _embedding_matcher
    
    if _embedding_matcher is None:
        _embedding_matcher = EmbeddingMatcher()
    
    return _embedding_matcher


def calculate_embedding_similarity(text1: str, text2: str) -> Optional[float]:
    """
    Convenience function to calculate embedding similarity.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score (0.0-1.0) or None if embeddings unavailable
    """
    matcher = get_embedding_matcher()
    return matcher.calculate_similarity(text1, text2)