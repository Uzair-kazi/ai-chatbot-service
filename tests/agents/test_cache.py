"""
Tests for Cache Implementations

This module tests the InMemoryCache implementation including TTL expiration,
LRU eviction, thread safety, and all cache operations.
"""

import pytest
import time
import threading
from agents.cache import InMemoryCache, NoOpCache, CacheProtocol


class TestInMemoryCache:
    """Test suite for InMemoryCache implementation."""
    
    def test_implements_cache_protocol(self):
        """Test that InMemoryCache implements CacheProtocol."""
        cache = InMemoryCache()
        assert isinstance(cache, CacheProtocol)
    
    def test_set_and_get_within_ttl(self):
        """Happy path: Set and get value within TTL."""
        cache = InMemoryCache(default_ttl=10)
        
        cache.set("key1", "value1")
        result = cache.get("key1")
        
        assert result == "value1"
    
    def test_get_nonexistent_key(self):
        """Happy path: Get returns None for non-existent key."""
        cache = InMemoryCache()
        
        result = cache.get("nonexistent")
        
        assert result is None
    
    def test_get_expired_entry(self):
        """Edge case: Get returns None for expired entry."""
        cache = InMemoryCache(default_ttl=1)  # 1 second TTL
        
        cache.set("key1", "value1")
        time.sleep(1.1)  # Wait for expiry
        result = cache.get("key1")
        
        assert result is None
    
    def test_expired_entry_removed_from_cache(self):
        """Edge case: Expired entry is removed from internal storage."""
        cache = InMemoryCache(default_ttl=1)
        
        cache.set("key1", "value1")
        assert cache.size() == 1
        
        time.sleep(1.1)  # Wait for expiry
        cache.get("key1")  # Trigger expiry check
        
        assert cache.size() == 0
    
    def test_lru_eviction_at_max_capacity(self):
        """Edge case: LRU eviction when cache reaches max_size."""
        cache = InMemoryCache(max_size=3, default_ttl=60)
        
        # Fill cache to capacity
        cache.set("key1", "value1")
        time.sleep(0.01)  # Ensure different access times
        cache.set("key2", "value2")
        time.sleep(0.01)
        cache.set("key3", "value3")
        
        # Access key2 to make it more recently used than key1
        time.sleep(0.01)
        cache.get("key2")
        
        # Add new key - should evict key1 (least recently used)
        cache.set("key4", "value4")
        
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"  # Still present
        assert cache.get("key3") == "value3"  # Still present
        assert cache.get("key4") == "value4"  # Newly added
    
    def test_set_with_custom_ttl(self):
        """Edge case: Set with custom TTL overrides default."""
        cache = InMemoryCache(default_ttl=60)
        
        cache.set("key1", "value1", ttl=1)  # Custom 1-second TTL
        time.sleep(1.1)
        result = cache.get("key1")
        
        assert result is None
    
    def test_update_existing_key(self):
        """Happy path: Updating existing key doesn't trigger eviction."""
        cache = InMemoryCache(max_size=2, default_ttl=60)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Update key1 - should not evict key2
        cache.set("key1", "updated_value1")
        
        assert cache.get("key1") == "updated_value1"
        assert cache.get("key2") == "value2"
        assert cache.size() == 2
    
    def test_delete_existing_key(self):
        """Integration: Delete removes entry and access time."""
        cache = InMemoryCache()
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        cache.delete("key1")
        
        assert cache.get("key1") is None
        assert cache.size() == 0
    
    def test_delete_nonexistent_key(self):
        """Edge case: Delete nonexistent key doesn't raise error."""
        cache = InMemoryCache()
        
        # Should not raise exception
        cache.delete("nonexistent")
        
        assert cache.size() == 0
    
    def test_clear_removes_all_entries(self):
        """Integration: Clear removes all entries."""
        cache = InMemoryCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        
        assert cache.size() == 3
        
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None
    
    def test_thread_safety_concurrent_get_set(self):
        """Integration: Cache operations are thread-safe."""
        cache = InMemoryCache(max_size=100, default_ttl=60)
        errors = []
        
        def worker(thread_id):
            try:
                for i in range(10):
                    key = f"key_{thread_id}_{i}"
                    cache.set(key, f"value_{thread_id}_{i}")
                    result = cache.get(key)
                    assert result == f"value_{thread_id}_{i}"
            except Exception as e:
                errors.append(e)
        
        # Run 5 threads concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # No errors should occur
        assert len(errors) == 0
    
    def test_cache_stores_different_types(self):
        """Happy path: Cache can store different value types."""
        cache = InMemoryCache()
        
        cache.set("string", "value")
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"key": "value"})
        cache.set("none", None)
        
        assert cache.get("string") == "value"
        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"key": "value"}
        assert cache.get("none") is None  # Note: None is a valid cached value
    
    def test_access_time_updated_on_get(self):
        """Integration: Access time is updated on get for LRU."""
        cache = InMemoryCache(max_size=2, default_ttl=60)
        
        cache.set("key1", "value1")
        time.sleep(0.01)
        cache.set("key2", "value2")
        
        # Access key1 to make it more recent
        time.sleep(0.01)
        cache.get("key1")
        
        # Add key3 - should evict key2 (least recently used)
        cache.set("key3", "value3")
        
        assert cache.get("key1") == "value1"  # Still present
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"  # Newly added


class TestNoOpCache:
    """Test suite for NoOpCache implementation."""
    
    def test_implements_cache_protocol(self):
        """Test that NoOpCache implements CacheProtocol."""
        cache = NoOpCache()
        assert isinstance(cache, CacheProtocol)
    
    def test_get_always_returns_none(self):
        """Happy path: Get always returns None."""
        cache = NoOpCache()
        
        cache.set("key1", "value1")
        result = cache.get("key1")
        
        assert result is None
    
    def test_set_does_nothing(self):
        """Happy path: Set does nothing."""
        cache = NoOpCache()
        
        # Should not raise exception
        cache.set("key1", "value1")
        cache.set("key2", "value2", ttl=10)
    
    def test_delete_does_nothing(self):
        """Happy path: Delete does nothing."""
        cache = NoOpCache()
        
        # Should not raise exception
        cache.delete("key1")
    
    def test_clear_does_nothing(self):
        """Happy path: Clear does nothing."""
        cache = NoOpCache()
        
        # Should not raise exception
        cache.clear()


class TestCachePerformance:
    """Performance tests for InMemoryCache."""
    
    def test_cache_operations_fast(self):
        """Verification: All cache operations complete in <1ms."""
        cache = InMemoryCache()
        
        # Test set performance
        start = time.time()
        cache.set("key1", "value1")
        set_time = (time.time() - start) * 1000  # Convert to ms
        
        # Test get performance
        start = time.time()
        cache.get("key1")
        get_time = (time.time() - start) * 1000
        
        # Test delete performance
        start = time.time()
        cache.delete("key1")
        delete_time = (time.time() - start) * 1000
        
        assert set_time < 1.0, f"Set took {set_time}ms (expected <1ms)"
        assert get_time < 1.0, f"Get took {get_time}ms (expected <1ms)"
        assert delete_time < 1.0, f"Delete took {delete_time}ms (expected <1ms)"
