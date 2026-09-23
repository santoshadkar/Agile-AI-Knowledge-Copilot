"""Makes the test suite hermetic: fake credentials so Settings() (required,
no-default fields) constructs successfully whether or not a real .env
exists -- CI has no .env at all, and even locally, tests should never
depend on real API keys or touch real external services.

Must run before anything imports app.config/app.main. pytest loads
conftest.py before collecting test modules, and pydantic-settings gives
explicit os.environ values priority over its .env file, so this reliably
overrides whatever's in backend/.env during a local run too.
"""

import os

os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("VOYAGE_API_KEY", "test-voyage-key")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "test-qdrant-key")
