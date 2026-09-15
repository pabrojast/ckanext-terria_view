"""SLD download caching in SLDProcessor.fetch_sld_content.

Production ran dozens of uWSGI workers, each with its own in-memory cache that
never remembered failures: every worker re-downloaded every style after each
recycle, and a deleted style file was requested again on every render. These
tests pin the two-level cache (per-process with TTL, shared in Redis) and which
failures it remembers. No CKAN, Redis or network is needed.
"""

import pytest

from ckanext.terria_view import sld_processor as sld_module
from ckanext.terria_view.sld_processor import SLDProcessor


STYLE_URL = 'https://ihp-wins.unesco.org/dataset/d/resource/r/download/style.sld'
STYLE = b'<StyledLayerDescriptor/>'


class Clock:
    def __init__(self):
        self.now = 1000000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeRedis:
    """The subset of redis.Redis used by the processor, with expiry."""

    def __init__(self, clock):
        self.clock = clock
        self.data = {}

    def get(self, key):
        item = self.data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and expires <= self.clock.now:
            del self.data[key]
            return None
        return value

    def set(self, key, value, ex=None):
        self.data[key] = (value, self.clock.now + ex if ex else None)

    def incr(self, key):
        value = int(self.get(key) or 0) + 1
        self.data[key] = (str(value).encode(), None)
        return value


class BrokenRedis:
    def get(self, key):
        raise ConnectionError('redis down')

    set = incr = get


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(sld_module.time, 'time', clock)
    return clock


@pytest.fixture
def worker(monkeypatch):
    """Build a processor standing in for one uWSGI worker."""
    def build(redis, responses):
        processor = SLDProcessor()
        calls = []

        def fetch(url):
            calls.append(url)
            return responses[url]

        monkeypatch.setattr(processor, '_redis', lambda: redis)
        monkeypatch.setattr(processor, '_fetch_http_content_with_status', fetch)
        return processor, calls
    return build


def test_download_is_shared_across_workers(clock, worker):
    redis = FakeRedis(clock)
    first, first_calls = worker(redis, {STYLE_URL: (STYLE, 200)})
    second, second_calls = worker(redis, {STYLE_URL: (STYLE, 200)})

    assert first.fetch_sld_content(STYLE_URL) == STYLE
    assert second.fetch_sld_content(STYLE_URL) == STYLE

    assert first_calls == [STYLE_URL]
    assert second_calls == []


def test_without_redis_each_worker_still_caches_in_memory(clock, worker):
    first, first_calls = worker(None, {STYLE_URL: (STYLE, 200)})

    assert first.fetch_sld_content(STYLE_URL) == STYLE
    assert first.fetch_sld_content(STYLE_URL) == STYLE

    assert first_calls == [STYLE_URL]


def test_memory_copy_expires_so_edited_styles_are_picked_up(clock, worker):
    first, calls = worker(None, {STYLE_URL: (STYLE, 200)})

    first.fetch_sld_content(STYLE_URL)
    clock.advance(SLDProcessor.MEMORY_CACHE_TTL + 1)
    first.fetch_sld_content(STYLE_URL)

    assert calls == [STYLE_URL, STYLE_URL]


def test_missing_style_is_remembered_for_the_negative_ttl(clock, worker):
    redis = FakeRedis(clock)
    first, first_calls = worker(redis, {STYLE_URL: (None, 404)})
    second, second_calls = worker(redis, {STYLE_URL: (None, 404)})

    assert first.fetch_sld_content(STYLE_URL) is None
    assert first.fetch_sld_content(STYLE_URL) is None
    assert second.fetch_sld_content(STYLE_URL) is None
    assert first_calls == [STYLE_URL]
    assert second_calls == []

    clock.advance(SLDProcessor.NEGATIVE_CACHE_TTL + 1)
    assert second.fetch_sld_content(STYLE_URL) is None
    assert second_calls == [STYLE_URL]


@pytest.mark.parametrize('status', [429, 500, 503, None])
def test_transient_failures_are_never_remembered(clock, worker, status):
    redis = FakeRedis(clock)
    first, first_calls = worker(redis, {STYLE_URL: (None, status)})
    second, second_calls = worker(redis, {STYLE_URL: (None, status)})

    assert first.fetch_sld_content(STYLE_URL) is None
    assert first.fetch_sld_content(STYLE_URL) is None
    assert second.fetch_sld_content(STYLE_URL) is None

    assert first_calls == [STYLE_URL, STYLE_URL]
    assert second_calls == [STYLE_URL]


def test_clear_caches_reaches_other_workers(clock, worker):
    redis = FakeRedis(clock)
    editor, editor_calls = worker(redis, {STYLE_URL: (STYLE, 200)})
    other, other_calls = worker(redis, {STYLE_URL: (b'<edited/>', 200)})

    editor.fetch_sld_content(STYLE_URL)
    assert other.fetch_sld_content(STYLE_URL) == STYLE

    editor.clear_caches()
    # The other worker's memory copy outlives the bump by at most its TTL.
    clock.advance(SLDProcessor.MEMORY_CACHE_TTL + 1)

    assert other.fetch_sld_content(STYLE_URL) == b'<edited/>'
    assert editor.fetch_sld_content(STYLE_URL) == b'<edited/>'
    assert other_calls == [STYLE_URL]
    assert editor_calls == [STYLE_URL]


def test_oversized_styles_stay_out_of_redis(clock, worker):
    big = b'x' * (SLDProcessor.SHARED_CACHE_MAX_BYTES + 1)
    redis = FakeRedis(clock)
    first, _ = worker(redis, {STYLE_URL: (big, 200)})
    second, second_calls = worker(redis, {STYLE_URL: (big, 200)})

    first.fetch_sld_content(STYLE_URL)
    second.fetch_sld_content(STYLE_URL)

    assert second_calls == [STYLE_URL]


def test_redis_errors_fall_back_to_downloading(clock, worker):
    first, calls = worker(BrokenRedis(), {STYLE_URL: (STYLE, 200)})

    assert first.fetch_sld_content(STYLE_URL) == STYLE
    first.clear_caches()
    assert first.fetch_sld_content(STYLE_URL) == STYLE
    assert calls == [STYLE_URL, STYLE_URL]


def test_result_cache_expires(clock):
    processor = SLDProcessor()
    processor._result_cache_set('shp:' + STYLE_URL, {'styles': []})

    assert processor._result_cache_get('shp:' + STYLE_URL) == {'styles': []}
    clock.advance(SLDProcessor.MEMORY_CACHE_TTL + 1)
    assert processor._result_cache_get('shp:' + STYLE_URL) is None
