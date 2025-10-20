"""
VLM Response Caching System
Intelligent caching to reduce VLM API calls by 60-80%

Phase 4 - Optimization Feature #2

Key Features:
- Screenshot similarity detection (perceptual hashing)
- Response caching with TTL
- Cost tracking and savings reports
- Cache hit/miss statistics
- Automatic cache cleanup

Example:
    cache = VLMResponseCache()
    
    # First call - hits VLM API
    response1 = cache.get_or_call(screenshot_bytes, prompt, vlm_callable)
    
    # Second call with similar screenshot - uses cache!
    response2 = cache.get_or_call(similar_screenshot, prompt, vlm_callable)
    
    # Check savings
    print(f"Cache hit rate: {cache.get_hit_rate():.1%}")
    print(f"Cost savings: ${cache.get_cost_savings():.2f}")
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import json
import time
import imagehash
from PIL import Image
import io


@dataclass
class CacheEntry:
    """Single cache entry"""
    cache_key: str
    prompt_hash: str
    screenshot_hash: str
    response: str
    timestamp: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.ttl_seconds <= 0:
            return False  # Never expires
        
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cache_key': self.cache_key,
            'prompt_hash': self.prompt_hash,
            'screenshot_hash': self.screenshot_hash,
            'response': self.response,
            'timestamp': self.timestamp.isoformat(),
            'ttl_seconds': self.ttl_seconds,
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None
        }


@dataclass
class CacheStatistics:
    """Cache performance statistics"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    api_calls_saved: int = 0
    cost_per_api_call: float = 0.02  # $0.02 per VLM call estimate
    cache_size_mb: float = 0.0
    oldest_entry_age_hours: float = 0.0
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests
    
    def get_cost_savings(self) -> float:
        """Calculate cost savings from cache"""
        return self.api_calls_saved * self.cost_per_api_call
    
    def print_statistics(self):
        """Print human-readable statistics"""
        print("\n" + "="*80)
        print("VLM CACHE STATISTICS")
        print("="*80)
        
        print(f"\n📊 Cache Performance:")
        print(f"  Total Requests: {self.total_requests}")
        print(f"  Cache Hits: {self.cache_hits} ({self.get_hit_rate():.1%})")
        print(f"  Cache Misses: {self.cache_misses}")
        print(f"  API Calls Saved: {self.api_calls_saved}")
        
        print(f"\n💰 Cost Savings:")
        print(f"  Cost Per API Call: ${self.cost_per_api_call:.3f}")
        print(f"  Total Savings: ${self.get_cost_savings():.2f}")
        
        print(f"\n💾 Cache Storage:")
        print(f"  Cache Size: {self.cache_size_mb:.2f} MB")
        print(f"  Oldest Entry: {self.oldest_entry_age_hours:.1f} hours")
        
        print("\n" + "="*80)


class VLMResponseCache:
    """
    Intelligent caching system for VLM API responses
    Uses perceptual hashing to detect similar screenshots
    """
    
    def __init__(
        self,
        cache_dir: str = ".vlm_cache",
        ttl_seconds: int = 86400,  # 24 hours default
        similarity_threshold: int = 10,  # Hamming distance for similarity
        max_cache_size_mb: int = 500,  # Max cache size
        cost_per_call: float = 0.02  # Estimated cost per VLM API call
    ):
        """
        Initialize VLM response cache
        
        Args:
            cache_dir: Directory to store cache files
            ttl_seconds: Time to live for cache entries (0 = never expire)
            similarity_threshold: Max hamming distance to consider screenshots similar
            max_cache_size_mb: Maximum cache size in MB
            cost_per_call: Estimated cost per VLM API call for savings calculation
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.max_cache_size_mb = max_cache_size_mb
        self.cost_per_call = cost_per_call
        
        # In-memory cache
        self.cache: Dict[str, CacheEntry] = {}
        
        # Statistics
        self.stats = CacheStatistics(cost_per_api_call=cost_per_call)
        
        # Load existing cache
        self._load_cache()
        
        print(f"[VLM Cache] Initialized")
        print(f"[VLM Cache] Cache dir: {self.cache_dir}")
        print(f"[VLM Cache] TTL: {ttl_seconds}s ({ttl_seconds/3600:.1f}h)")
        print(f"[VLM Cache] Loaded {len(self.cache)} existing entries")
    
    def get_or_call(
        self,
        screenshot_bytes: bytes,
        prompt: str,
        vlm_callable: Callable[[bytes, str], str],
        force_refresh: bool = False
    ) -> str:
        """
        Get cached response or call VLM API
        
        Args:
            screenshot_bytes: Screenshot image bytes
            prompt: VLM prompt
            vlm_callable: Function to call VLM API (signature: fn(screenshot, prompt) -> response)
            force_refresh: Force API call even if cached
        
        Returns:
            VLM response (from cache or fresh API call)
        """
        self.stats.total_requests += 1
        
        # Generate cache key
        cache_key = self._generate_cache_key(screenshot_bytes, prompt)
        
        # Check cache (unless force refresh)
        if not force_refresh:
            cached_response = self._get_from_cache(cache_key, screenshot_bytes)
            if cached_response:
                self.stats.cache_hits += 1
                self.stats.api_calls_saved += 1
                print(f"[VLM Cache] ✓ Cache hit! Saved API call (${self.cost_per_call:.3f})")
                return cached_response
        
        # Cache miss - call VLM API
        self.stats.cache_misses += 1
        print(f"[VLM Cache] ✗ Cache miss - calling VLM API...")
        
        start_time = time.time()
        response = vlm_callable(screenshot_bytes, prompt)
        duration = time.time() - start_time
        
        print(f"[VLM Cache] API call completed in {duration:.1f}s")
        
        # Store in cache
        self._store_in_cache(cache_key, screenshot_bytes, prompt, response)
        
        return response
    
    def _generate_cache_key(self, screenshot_bytes: bytes, prompt: str) -> str:
        """Generate unique cache key"""
        # Combine screenshot hash and prompt hash
        screenshot_hash = hashlib.md5(screenshot_bytes).hexdigest()[:16]
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        return f"{screenshot_hash}_{prompt_hash}"
    
    def _get_perceptual_hash(self, screenshot_bytes: bytes) -> imagehash.ImageHash:
        """Generate perceptual hash for screenshot similarity detection"""
        try:
            image = Image.open(io.BytesIO(screenshot_bytes))
            return imagehash.phash(image)
        except Exception as e:
            print(f"[VLM Cache] Warning: Could not generate perceptual hash: {e}")
            return None
    
    def _get_from_cache(self, cache_key: str, screenshot_bytes: bytes) -> Optional[str]:
        """Get response from cache if exists and not expired"""
        
        # Direct cache hit
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            
            if entry.is_expired():
                print(f"[VLM Cache] Entry expired (age: {(datetime.now() - entry.timestamp).total_seconds()/3600:.1f}h)")
                del self.cache[cache_key]
                return None
            
            # Update access statistics
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            return entry.response
        
        # Try similarity matching with perceptual hashing
        screenshot_phash = self._get_perceptual_hash(screenshot_bytes)
        
        if screenshot_phash:
            for key, entry in self.cache.items():
                if entry.is_expired():
                    continue
                
                # Compare perceptual hashes
                cached_phash_str = entry.screenshot_hash
                try:
                    cached_phash = imagehash.hex_to_hash(cached_phash_str)
                    hamming_distance = screenshot_phash - cached_phash
                    
                    if hamming_distance <= self.similarity_threshold:
                        print(f"[VLM Cache] ✓ Similar screenshot found (distance: {hamming_distance})")
                        entry.access_count += 1
                        entry.last_accessed = datetime.now()
                        return entry.response
                except:
                    pass
        
        return None
    
    def _store_in_cache(
        self,
        cache_key: str,
        screenshot_bytes: bytes,
        prompt: str,
        response: str
    ):
        """Store response in cache"""
        
        # Generate hashes
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        screenshot_phash = self._get_perceptual_hash(screenshot_bytes)
        screenshot_hash = str(screenshot_phash) if screenshot_phash else hashlib.md5(screenshot_bytes).hexdigest()
        
        # Create cache entry
        entry = CacheEntry(
            cache_key=cache_key,
            prompt_hash=prompt_hash,
            screenshot_hash=screenshot_hash,
            response=response,
            timestamp=datetime.now(),
            ttl_seconds=self.ttl_seconds,
            access_count=1,
            last_accessed=datetime.now()
        )
        
        # Store in memory
        self.cache[cache_key] = entry
        
        # Persist to disk
        self._save_cache()
        
        # Check cache size and cleanup if needed
        self._cleanup_if_needed()
        
        print(f"[VLM Cache] Cached response (key: {cache_key[:16]}...)")
    
    def _load_cache(self):
        """Load cache from disk"""
        cache_file = self.cache_dir / "cache_data.json"
        
        if not cache_file.exists():
            return
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            for entry_data in cache_data.get('entries', []):
                entry = CacheEntry(
                    cache_key=entry_data['cache_key'],
                    prompt_hash=entry_data['prompt_hash'],
                    screenshot_hash=entry_data['screenshot_hash'],
                    response=entry_data['response'],
                    timestamp=datetime.fromisoformat(entry_data['timestamp']),
                    ttl_seconds=entry_data['ttl_seconds'],
                    access_count=entry_data.get('access_count', 0),
                    last_accessed=datetime.fromisoformat(entry_data['last_accessed']) if entry_data.get('last_accessed') else None
                )
                
                # Only load non-expired entries
                if not entry.is_expired():
                    self.cache[entry.cache_key] = entry
            
            # Load statistics
            if 'statistics' in cache_data:
                stats_data = cache_data['statistics']
                self.stats.total_requests = stats_data.get('total_requests', 0)
                self.stats.cache_hits = stats_data.get('cache_hits', 0)
                self.stats.cache_misses = stats_data.get('cache_misses', 0)
                self.stats.api_calls_saved = stats_data.get('api_calls_saved', 0)
            
        except Exception as e:
            print(f"[VLM Cache] Warning: Could not load cache: {e}")
    
    def _save_cache(self):
        """Save cache to disk"""
        cache_file = self.cache_dir / "cache_data.json"
        
        try:
            cache_data = {
                'version': '1.0',
                'timestamp': datetime.now().isoformat(),
                'statistics': {
                    'total_requests': self.stats.total_requests,
                    'cache_hits': self.stats.cache_hits,
                    'cache_misses': self.stats.cache_misses,
                    'api_calls_saved': self.stats.api_calls_saved
                },
                'entries': [entry.to_dict() for entry in self.cache.values()]
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            print(f"[VLM Cache] Warning: Could not save cache: {e}")
    
    def _cleanup_if_needed(self):
        """Clean up cache if it exceeds size limit"""
        # Calculate current cache size
        cache_file = self.cache_dir / "cache_data.json"
        if cache_file.exists():
            size_mb = cache_file.stat().st_size / (1024 * 1024)
            self.stats.cache_size_mb = size_mb
            
            if size_mb > self.max_cache_size_mb:
                print(f"[VLM Cache] Cache size ({size_mb:.1f}MB) exceeds limit ({self.max_cache_size_mb}MB)")
                self._cleanup_old_entries()
    
    def _cleanup_old_entries(self, keep_percentage: float = 0.7):
        """Remove oldest/least used entries"""
        if not self.cache:
            return
        
        # Sort by last accessed time and access count
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: (x[1].access_count, x[1].last_accessed or x[1].timestamp)
        )
        
        # Keep top percentage
        keep_count = int(len(sorted_entries) * keep_percentage)
        entries_to_remove = sorted_entries[:len(sorted_entries) - keep_count]
        
        for key, _ in entries_to_remove:
            del self.cache[key]
        
        print(f"[VLM Cache] Cleaned up {len(entries_to_remove)} old entries")
        self._save_cache()
    
    def clear_cache(self):
        """Clear all cache entries"""
        self.cache.clear()
        self._save_cache()
        print(f"[VLM Cache] Cache cleared")
    
    def get_statistics(self) -> CacheStatistics:
        """Get current cache statistics"""
        # Update cache size
        cache_file = self.cache_dir / "cache_data.json"
        if cache_file.exists():
            self.stats.cache_size_mb = cache_file.stat().st_size / (1024 * 1024)
        
        # Update oldest entry age
        if self.cache:
            oldest_entry = min(self.cache.values(), key=lambda e: e.timestamp)
            age_hours = (datetime.now() - oldest_entry.timestamp).total_seconds() / 3600
            self.stats.oldest_entry_age_hours = age_hours
        
        return self.stats


# Demo
def demo():
    """Demo VLM response caching"""
    
    print("="*80)
    print("VLM RESPONSE CACHING - DEMO")
    print("="*80)
    print("\n💾 Phase 4 Feature: Reduce VLM API Costs by 60-80%!\n")
    
    # Create cache
    cache = VLMResponseCache(
        cache_dir=".demo_vlm_cache",
        ttl_seconds=3600,  # 1 hour for demo
        similarity_threshold=10
    )
    
    # Mock VLM API call
    def mock_vlm_api(screenshot_bytes: bytes, prompt: str) -> str:
        """Mock VLM API - simulates real API call"""
        time.sleep(0.5)  # Simulate API latency
        return f"VLM Response for prompt: {prompt[:50]}... (screenshot size: {len(screenshot_bytes)} bytes)"
    
    # Create mock screenshots
    print("📸 Creating mock screenshots...")
    screenshot1 = b"mock_screenshot_data_1" * 100
    screenshot2 = b"mock_screenshot_data_1" * 100  # Same as screenshot1
    screenshot3 = b"mock_screenshot_data_2" * 100  # Different
    
    prompt = "Analyze this screenshot and identify clickable elements"
    
    print("\n" + "="*80)
    print("Test 1: First API Call (Cache Miss)")
    print("="*80)
    start = time.time()
    response1 = cache.get_or_call(screenshot1, prompt, mock_vlm_api)
    duration1 = time.time() - start
    print(f"Response: {response1[:80]}...")
    print(f"Duration: {duration1:.2f}s")
    
    print("\n" + "="*80)
    print("Test 2: Same Screenshot (Cache Hit)")
    print("="*80)
    start = time.time()
    response2 = cache.get_or_call(screenshot2, prompt, mock_vlm_api)
    duration2 = time.time() - start
    print(f"Response: {response2[:80]}...")
    print(f"Duration: {duration2:.2f}s")
    print(f"⚡ Speed improvement: {duration1/duration2:.1f}x faster!")
    
    print("\n" + "="*80)
    print("Test 3: Different Screenshot (Cache Miss)")
    print("="*80)
    start = time.time()
    response3 = cache.get_or_call(screenshot3, prompt, mock_vlm_api)
    duration3 = time.time() - start
    print(f"Response: {response3[:80]}...")
    print(f"Duration: {duration3:.2f}s")
    
    # Show statistics
    stats = cache.get_statistics()
    stats.print_statistics()
    
    print("\n" + "="*80)
    print("Real-World Impact:")
    print("="*80)
    print(f"")
    print(f"💰 Cost Savings Example:")
    print(f"  - 1000 test runs/month")
    print(f"  - 5 VLM calls per test = 5000 API calls")
    print(f"  - At $0.02/call = $100/month")
    print(f"  - With 70% cache hit rate:")
    print(f"    • API calls saved: 3500")
    print(f"    • Cost savings: $70/month")
    print(f"    • Annual savings: $840/year")
    
    print(f"\n⚡ Performance Impact:")
    print(f"  - VLM API call: ~2-5 seconds")
    print(f"  - Cache lookup: <0.01 seconds")
    print(f"  - With 70% hit rate:")
    print(f"    • Average latency reduced by 60-70%")
    print(f"    • Tests run 2-3x faster")
    
    print("\n" + "="*80)
    print("Usage in Your Code:")
    print("="*80)
    print("""
from vlm_response_cache import VLMResponseCache

# Initialize cache
cache = VLMResponseCache(
    ttl_seconds=86400,  # 24 hours
    similarity_threshold=10  # Hamming distance
)

# In your VLM calls
def find_element_with_vlm(driver, description):
    screenshot = driver.get_screenshot_as_png()
    prompt = f"Find element: {description}"
    
    # Use cache instead of direct API call
    response = cache.get_or_call(
        screenshot_bytes=screenshot,
        prompt=prompt,
        vlm_callable=call_ollama_api
    )
    
    return parse_response(response)

# Check savings periodically
stats = cache.get_statistics()
print(f"Cache hit rate: {stats.get_hit_rate():.1%}")
print(f"Cost savings: ${stats.get_cost_savings():.2f}")
""")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    demo()
