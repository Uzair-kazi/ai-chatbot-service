"""
Cache Protocol (Stub for Phase 2)

This module defines the abstract cache protocol that will be implemented in Phase 2.
The cache will store schema information, validation results, and other frequently
accessed data to reduce latency and token usage.

Phase 2 will implement:
- Schema caching with TTL
- Validation result caching
- Query pattern caching
- LRU eviction policy
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class CacheProtocol(ABC):
    """
    Abstract cache protocol for agent data.
    
    This protocol defines the interface for caching. Implementation will be
    added in Phase 2 when Schema Intelligence agent is introduced.
    
    Methods:
        get: Retrieve value from cache
        set: Store value in cache with optional TTL
        delete: Remove value from cache
        clear: Clear all cache entries
    """
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        raise NotImplementedError("Cache implementation deferred to Phase 2")
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional time-to-live in seconds
        """
        raise NotImplementedError("Cache implementation deferred to Phase 2")
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Remove value from cache.
        
        Args:
            key: Cache key
        """
        raise NotImplementedError("Cache implementation deferred to Phase 2")
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        raise NotImplementedError("Cache implementation deferred to Phase 2")


# Stub implementation for Phase 1 (no-op cache)
class NoOpCache(CacheProtocol):
    """
    No-op cache implementation for Phase 1.
    
    This implementation does nothing and always returns None for get().
    It allows the agent framework to be cache-aware without requiring
    a full cache implementation in Phase 1.
    """
    
    def get(self, key: str) -> Optional[Any]:
        """Always returns None (no caching)."""
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Does nothing (no caching)."""
        pass
    
    def delete(self, key: str) -> None:
        """Does nothing (no caching)."""
        pass
    
    def clear(self) -> None:
        """Does nothing (no caching)."""
        pass


# Default cache instance (no-op for Phase 1)
default_cache = NoOpCache()
