import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def isolate_the_cache_shared_by_the_rate_limits_and_the_email_cooldowns():
    cache.clear()
    yield
    cache.clear()
