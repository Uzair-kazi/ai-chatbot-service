"""
Cache Protocol and Implementations

This module defines the abstract cache protocol and provides implementations
for caching agent data. The cache stores schema information, validation results,
and other frequently accessed data to reduce latency and token usage.

Implementations:
- InMemoryCache: Production cache with TTL and LRU eviction
- NoOpCache: No-op cache for testing or when caching is disabled
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Tuple
import time
import threading


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


class InMemoryCache(CacheProtocol):
    """
    In-memory cache implementation with TTL and LRU eviction.
    
    This cache stores entries with time-to-live (TTL) expiration and uses
    Least Recently Used (LRU) eviction when the cache reaches max capacity.
    Thread-safe for concurrent access.
    
    Attributes:
        max_size: Maximum number of entries (default 1000)
        default_ttl: Default time-to-live in seconds (default 300 = 5 minutes)
        
    Example:
        cache = InMemoryCache(max_size=1000, default_ttl=300)
        cache.set("key1", "value1")
        value = cache.get("key1")  # Returns "value1"
        
        # After TTL expires
        value = cache.get("key1")  # Returns None
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize the in-memory cache.
        
        Args:
            max_size: Maximum number of entries before LRU eviction
            default_ttl: Default time-to-live in seconds
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_times: Dict[str, float] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            value, expiry = self._cache[key]
            
            # Check if expired
            if time.time() > expiry:
                # Remove expired entry
                del self._cache[key]
                del self._access_times[key]
                return None
            
            # Update access time for LRU
            self._access_times[key] = time.time()
            return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional time-to-live in seconds (uses default_ttl if None)
        """
        with self._lock:
            # Evict if at capacity and key is new
            if key not in self._cache and len(self._cache) >= self._max_size:
                self._evict_lru()
            
            # Calculate expiry time
            ttl = ttl if ttl is not None else self._default_ttl
            expiry = time.time() + ttl
            
            # Store entry
            self._cache[key] = (value, expiry)
            self._access_times[key] = time.time()
    
    def delete(self, key: str) -> None:
        """
        Remove value from cache.
        
        Args:
            key: Cache key
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._access_times[key]
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def _evict_lru(self) -> None:
        """
        Evict the least recently used entry.
        
        This method should only be called when holding the lock.
        """
        if not self._access_times:
            return
        
        # Find key with oldest access time
        lru_key = min(self._access_times, key=self._access_times.get)
        
        # Remove from both dictionaries
        del self._cache[lru_key]
        del self._access_times[lru_key]
    
    def size(self) -> int:
        """
        Get current cache size.
        
        Returns:
            Number of entries in cache
        """
        with self._lock:
            return len(self._cache)


# No-op cache implementation for testing or when caching is disabled
class NoOpCache(CacheProtocol):
    """
    No-op cache implementation.
    
    This implementation does nothing and always returns None for get().
    Useful for testing or when caching should be disabled.
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


# Default cache instance (in-memory cache for Phase 2)
default_cache = InMemoryCache()
