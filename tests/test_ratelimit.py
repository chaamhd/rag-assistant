from app.ratelimit import RateLimiter


def test_blocks_after_the_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)


def test_allows_again_after_the_window():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a", now=0)
    assert not limiter.allow("a", now=59)
    assert limiter.allow("a", now=60)


def test_clients_are_independent():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a", now=0)
    assert limiter.allow("b", now=0)