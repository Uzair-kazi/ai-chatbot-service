"""
Tests for Cache Protocol

This module tests the cache protocol and no-op implementation.
Full cache implementation will be tested in Phase 2.
"""

import pytest
from agents.cache import CacheProtocol, NoOpCache, default_cache


# ============================================================================
# CacheProtocol Tests
# ============================================================================

def test_cache_protocol_is_abstract():
    """Test that CacheProtocol cannot be instantiated directly."""
    with pytest.raises(TypeError):
        CacheProtocol()


def test_cache_protocol_requires_get_implementation():
    """Test that CacheProtocol requires get() implementation."""
    
    class IncompleteCacheGet(CacheProtocol):
        def set(self, key: str, value, ttl=None):
            pass
        
        def delete(self, key: str):
            pass
        
        def clear(self):
            pass
    
    with pytest.raises(TypeError):
        IncompleteCacheGet()


def test_cache_protocol_requires_set_implementation():
    """Test that CacheProtocol requires set() implementation."""
    
    class IncompleteCacheSet(CacheProtocol):
        def get(self, key: str):
            pass
        
        def delete(self, key: str):
            pass
        
        def clear(self):
            pass
    
    with pytest.raises(TypeError):
        IncompleteCacheSet()


def test_cache_protocol_requires_delete_implementation():
    """Test that CacheProtocol requires delete() implementation."""
    
    class IncompleteCacheDelete(CacheProtocol):
        def get(self, key: str):
            pass
        
        def set(self, key: str, value, ttl=None):
            pass
        
        def clear(self):
            pass
    
    with pytest.raises(TypeError):
        IncompleteCacheDelete()


def test_cache_protocol_requires_clear_implementation():
    """Test that CacheProtocol requires clear() implementation."""
    
    class IncompleteCacheClear(CacheProtocol):
        def get(self, key: str):
            pass
        
        def set(self, key: str, value, ttl=None):
            pass
        
        def delete(self, key: str):
            pass
    
    with pytest.raises(TypeError):
        IncompleteCacheClear()


# ============================================================================
# NoOpCache Tests - Happy Path
# ============================================================================

def test_noop_cache_initialization():
    """Test that NoOpCache can be instantiated."""
    cache = NoOpCache()
    
    assert cache is not None
    assert isinstance(cache, CacheProtocol)


def test_noop_cache_get_returns_none():
    """Test that NoOpCache.get() always returns None."""
    cache = NoOpCache()
    
    result = cache.get("test_key")
    
    assert result is None


def test_noop_cache_set_does_nothing():
    """Test that NoOpCache.set() does nothing."""
    cache = NoOpCache()
    
    # Should not raise exception
    cache.set("test_key", "test_value")
    
    # Verify it doesn't actually cache
    result = cache.get("test_key")
    assert result is None


def test_noop_cache_set_with_ttl_does_nothing():
    """Test that NoOpCache.set() with TTL does nothing."""
    cache = NoOpCache()
    
    # Should not raise exception
    cache.set("test_key", "test_value", ttl=60)
    
    # Verify it doesn't actually cache
    result = cache.get("test_key")
    assert result is None


def test_noop_cache_delete_does_nothing():
    """Test that NoOpCache.delete() does nothing."""
    cache = NoOpCache()
    
    # Should not raise exception
    cache.delete("test_key")


def test_noop_cache_clear_does_nothing():
    """Test that NoOpCache.clear() does nothing."""
    cache = NoOpCache()
    
    # Should not raise exception
    cache.clear()


# ============================================================================
# NoOpCache Tests - Edge Cases
# ============================================================================

def test_noop_cache_get_with_empty_key():
    """Test that NoOpCache.get() handles empty key."""
    cache = NoOpCache()
    
    result = cache.get("")
    
    assert result is None


def test_noop_cache_set_with_none_value():
    """Test that NoOpCache.set() handles None value."""
    cache = NoOpCache()
    
    # Should not raise exception
    cache.set("test_key", None)


def test_noop_cache_set_with_complex_value():
    """Test that NoOpCache.set() handles complex values."""
    cache = NoOpCache()
    
    complex_value = {
        "nested": {
            "data": [1, 2, 3],
            "more": {"deep": "value"}
        }
    }
    
    # Should not raise exception
    cache.set("test_key", complex_value)
    
    # Verify it doesn't actually cache
    result = cache.get("test_key")
    assert result is None


def test_noop_cache_multiple_operations():
    """Test that NoOpCache handles multiple operations."""
    cache = NoOpCache()
    
    # Multiple set operations
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")
    
    # All get operations should return None
    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert cache.get("key3") is None
    
    # Delete and clear should not raise exceptions
    cache.delete("key1")
    cache.clear()


# ============================================================================
# Default Cache Tests
# ============================================================================

def test_default_cache_is_noop():
    """Test that default_cache is a NoOpCache instance."""
    assert isinstance(default_cache, NoOpCache)
    assert isinstance(default_cache, CacheProtocol)


def test_default_cache_get_returns_none():
    """Test that default_cache.get() returns None."""
    result = default_cache.get("test_key")
    
    assert result is None


def test_default_cache_operations_work():
    """Test that default_cache operations work without errors."""
    # Should not raise exceptions
    default_cache.set("test_key", "test_value")
    default_cache.get("test_key")
    default_cache.delete("test_key")
    default_cache.clear()


# ============================================================================
# Integration Tests
# ============================================================================

def test_cache_protocol_interface_consistency():
    """Test that NoOpCache implements all CacheProtocol methods."""
    cache = NoOpCache()
    
    # Verify all methods exist and are callable
    assert callable(cache.get)
    assert callable(cache.set)
    assert callable(cache.delete)
    assert callable(cache.clear)


def test_noop_cache_can_be_used_as_cache_protocol():
    """Test that NoOpCache can be used where CacheProtocol is expected."""
    
    def use_cache(cache: CacheProtocol):
        cache.set("key", "value")
        return cache.get("key")
    
    cache = NoOpCache()
    result = use_cache(cache)
    
    # NoOpCache should return None
    assert result is None


def test_multiple_noop_cache_instances_independent():
    """Test that multiple NoOpCache instances are independent."""
    cache1 = NoOpCache()
    cache2 = NoOpCache()
    
    cache1.set("key", "value1")
    cache2.set("key", "value2")
    
    # Both should return None (no actual caching)
    assert cache1.get("key") is None
    assert cache2.get("key") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
