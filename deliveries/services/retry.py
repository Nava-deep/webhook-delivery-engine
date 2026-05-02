from datetime import timedelta


BACKOFF_SECONDS = [5, 15, 45, 120]


def retry_delay_for_attempt(attempt_count: int) -> timedelta:
    """Return the delay after the given failed attempt count."""
    if attempt_count <= 0:
        return timedelta(seconds=BACKOFF_SECONDS[0])
    index = min(attempt_count - 1, len(BACKOFF_SECONDS) - 1)
    return timedelta(seconds=BACKOFF_SECONDS[index])
