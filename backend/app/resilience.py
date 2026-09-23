"""Shared retry policy for Voyage AI calls.

Voyage caps accounts with no payment method on file at 3 requests/minute
(the 200M free tokens still apply -- this only throttles request rate).
Used by both the ingestion pipeline (embed + upsert) and query-time
retrieval (embed_query on every chat request).

Originally retried aggressively -- 6 attempts, backoff up to 60s each,
~195s worst case -- to ride out the rate limit at (almost) any cost. That
caused a real incident: a background ingestion task (see app/api/ingest.py
-- embedding now runs as a background task, not inline in the request) got
rate-limited and sat in that long backoff on Render's free tier, which
only allocates 0.1 CPU to the whole instance. The repeated retry attempts
(each a real network+TLS call, not just idle sleeping) starved the single
worker process badly enough that UNRELATED requests -- other uploads,
even /health -- started failing with 502s for minutes, until the stuck
task finally exhausted its attempts.

Two things wrong with the old policy, not just "too slow":
1. Voyage's limit is a per-MINUTE window. Retrying for 3+ minutes doesn't
   improve the odds much past the first ~15-20s -- either the window has
   cleared by then or it hasn't, and waiting longer within the same
   request just holds resources without meaningfully raising success
   odds.
2. The background /ingest path doesn't need to "succeed eventually" at
   any cost -- the HTTP response is long since sent. A background embed
   that fails should fail fast and log clearly (see commit_ingestion's
   try/except), not hold a thread hostage for minutes on the hope Voyage
   frees up.

Bounded to 3 attempts, backoff capped at 10s -- worst case a few tens of
seconds total, not minutes, whether it's the synchronous chat-query path
or a background ingestion commit.
"""

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from voyageai.error import RateLimitError

voyage_retry = retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
