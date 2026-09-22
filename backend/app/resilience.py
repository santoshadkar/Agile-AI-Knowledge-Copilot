"""Shared retry policy for Voyage AI calls.

Voyage caps accounts with no payment method on file at 3 requests/minute
(the 200M free tokens still apply -- this only throttles request rate).
Used by both the ingestion pipeline (embed + upsert) and query-time
retrieval (embed_query on every chat request) -- retrieval needs this
*more* than ingestion does, since it's on the hot path of every request,
not a one-off batch job.
"""

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from voyageai.error import RateLimitError

voyage_retry = retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
