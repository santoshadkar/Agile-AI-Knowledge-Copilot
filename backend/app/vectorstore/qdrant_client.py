"""Factory for the shared Qdrant vector store, used by both the ingestion
pipeline (writes) and the retrieval node (reads, added in build step 3).

VOYAGE_MODEL / VOYAGE_OUTPUT_DIMENSION live here rather than in Settings
because they're an implementation detail of "how we embed," not something
meant to be reconfigured per-deployment the way API keys are.
"""

from functools import lru_cache

from langchain_qdrant import QdrantVectorStore
from langchain_voyageai import VoyageAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import get_settings

# voyage-4-lite: same 200M free-token allowance as voyage-4 / voyage-4-large,
# lower latency and cost once past the free tier -- a solid default for a
# personal knowledge base at this scale. 1024 dims matches Qdrant's default
# COSINE-friendly size and leaves headroom if we ever need to re-embed with
# voyage-4/voyage-4-large without changing the collection config.
VOYAGE_MODEL = "voyage-4-lite"
VOYAGE_OUTPUT_DIMENSION = 1024


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


@lru_cache
def get_embeddings() -> VoyageAIEmbeddings:
    settings = get_settings()
    return VoyageAIEmbeddings(
        voyage_api_key=settings.voyage_api_key,
        model=VOYAGE_MODEL,
        output_dimension=VOYAGE_OUTPUT_DIMENSION,
    )


def get_vector_store() -> QdrantVectorStore:
    """Returns a QdrantVectorStore bound to the configured collection,
    creating the collection on first use if it doesn't exist yet."""
    settings = get_settings()
    client = get_qdrant_client()

    if not client.collection_exists(settings.qdrant_collection_name):
        client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(
                size=VOYAGE_OUTPUT_DIMENSION,
                distance=Distance.COSINE,
            ),
        )

    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection_name,
        embedding=get_embeddings(),
    )
