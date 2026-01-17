"""
Query result caching for the agent API.
Simple in-memory LRU cache with TTL (Time To Live) support.
"""
import hashlib
import time
from collections import OrderedDict
from typing import Optional, Tuple, Any
import json


class LRUCache:
    """
    Simple LRU cache with TTL support.
    """
    
    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        """
        Args:
            max_size: Maximum number of entries in cache
            default_ttl: Default TTL in seconds (5 minutes)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
    
    def _is_expired(self, expiry_time: float) -> bool:
        """Check if an entry has expired."""
        return time.time() > expiry_time
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from query parameters."""
        # Create a stable string representation
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if not expired."""
        if key not in self.cache:
            return None
        
        value, expiry_time = self.cache[key]
        
        if self._is_expired(expiry_time):
            # Remove expired entry
            del self.cache[key]
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return value
    
    def put(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value in cache with optional TTL."""
        # Remove oldest entry if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            self.cache.popitem(last=False)  # Remove oldest (first) item
        
        expiry_time = time.time() + (ttl or self.default_ttl)
        self.cache[key] = (value, expiry_time)
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


# Global cache instance
_query_cache = LRUCache(max_size=100, default_ttl=300)  # 100 entries, 5 min TTL


def get_cache() -> LRUCache:
    """Get the global query cache instance."""
    return _query_cache


def cache_key_for_nlq(question: str, limit: int) -> str:
    """Generate a cache key for an NLQ query."""
    cache = get_cache()
    return cache._generate_key(question=question, limit=limit)


def cache_key_for_query(
    metrics: list,
    dimensions: Optional[list] = None,
    where: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 200
) -> str:
    """Generate a cache key for a direct MetricFlow query."""
    cache = get_cache()
    return cache._generate_key(
        metrics=sorted(metrics),
        dimensions=sorted(dimensions) if dimensions else None,
        where=where,
        start_time=start_time,
        end_time=end_time,
        limit=limit
    )
