# Agile & AI Knowledge Copilot

A RAG-powered chat assistant over two personal knowledge domains:

1. **Agile coaching** — maturity assessment frameworks, Big Room Planning artefacts, SAFe/Scrum reference material, Jira metrics governance docs.
2. **Claude certification study material** — content for Anthropic's Claude certifications (Associate/Developer/Architect Foundations, Architect Professional).

Every answer cites which source document(s) and domain it drew from. You can ask within a single domain or search across both.

This is a personal learning + portfolio project, not tied to any employer or confidential content — everything in `backend/sample_docs/` is generic, non-proprietary sample material used to prove the pipeline works.

## Live

- **App:** https://agile-ai-knowledge-copilot-golden-eagle1.vercel.app
- **API:** https://agile-ai-knowledge-copilot-backend.onrender.com (docs at `/docs`)

Backend is on Render's free tier and spins down after 15 minutes of inactivity — the first request after a quiet period takes roughly a minute to wake it back up.

## Architecture

```
frontend/  Next.js (React) — chat UI + admin/upload view          → deployed to Vercel
backend/   FastAPI + LangGraph — agentic RAG graph, ingestion API  → deployed to Render
           ├─ query-analysis/routing node (which domain(s) to search)
           ├─ retrieval node (Qdrant, filtered by domain)
           ├─ generation node (produces cited answers)
           └─ check / re-retrieve loop (if first retrieval looks insufficient)
```

- **LLM (generation):** a three-model fallback chain via [OpenRouter](https://openrouter.ai) — `qwen/qwen3.8-27b:free` → `liquid/lfm-2.5-2.6b:free` → `nvidia/nemotron-3-super-120b-a12b:free`, three different underlying providers to reduce correlated-failure risk. Originally Claude, then Gemini, then Gemini+Groq — each swap driven by a real problem hit in production, not preference: Claude needs a payment method Anthropic's free tier doesn't; Gemini alone hit both broad intermittent capacity 503s and a hard per-model daily quota (confirmed live via a `429`); a naive retry-count fix then caused a 155-second latency regression (root cause: LangChain's `max_retries` was compounding against a *second*, hidden retry layer inside Google's own SDK). OpenRouter's one API simplified two separate provider SDKs into one, and every tier fails fast (`max_retries=0` — the chain itself is the redundancy, not retrying within a tier). Live-verified on the deployed instance: full requests, including ones that hit real `429`s on the first one or two tiers, consistently complete in **4-10 seconds**.
- **Embeddings:** Voyage AI
- **Vector store:** Qdrant Cloud (free tier) — chosen over Pinecone/pgvector for generous free-tier limits, clean LangChain integration via `langchain-qdrant`, and per-chunk metadata filtering (domain + source filename) without being tied to a single LLM vendor
- **Orchestration:** LangChain (document loading/retrieval primitives) + LangGraph (the actual agentic flow, not a single chain)

Render's free tier has no persistent disk, so nothing about vector storage or uploaded-doc state depends on local disk surviving a redeploy — the vector DB (Qdrant Cloud) lives outside the backend instance entirely.

## Build status

This project is being built incrementally, in commit-sized steps:

- [x] 1. Repo scaffold (backend + frontend skeletons, both verified booting locally)
- [x] 2. Ingestion pipeline + sample docs (verified live: 4 sample docs / 26 chunks embedded and upserted to Qdrant Cloud, cross-domain and domain-filtered retrieval both confirmed working)
- [x] 3. LangGraph RAG graph with citations (route -> retrieve -> retry-loop -> generate; control flow verified via mocked-LLM tests, retrieval verified live against Qdrant; live generation blocked by a Gemini server-side outage during testing -- see graph/nodes.py)
- [x] 4. FastAPI endpoints (POST /chat, POST /ingest, GET /health -- all exercised live via TestClient: validation errors, the confidentiality-guard block-then-force-override path, a real ingest happy path, and the 503 the /chat endpoint returns cleanly when Gemini is down, which it genuinely was during this testing)
- [x] 5. Next.js chat UI wired to backend (chat with domain filter + citations, admin upload page; verified live end-to-end against the real backend, which surfaced and fixed a CORS port bug and a Gemini routing bug -- see the two step-5 commits)
- [x] 6. Local end-to-end preview (both servers run locally and were clicked through together in step 5 -- domain filter, chat error handling, and CORS/routing bugs were caught this way, not by review)
- [x] 7. Tests -- 41 tests, all passing, verified hermetic (pass with zero real credentials present -- deliberately confirmed by removing .env entirely and re-running, not just assumed): chunking (incl. regression coverage for the orphan-chunk bug from step 2), safety guard (incl. the "fundamentals contains nda" false-positive regression), loaders (all 3 formats against the real sample docs), graph nodes with mocked LLM/vector-store calls (incl. regression coverage for the routing "contents are required" bug from step 5), and an API smoke test covering every endpoint's happy and error paths
- [x] 8. GitHub push ([santoshadkar/Agile-AI-Knowledge-Copilot](https://github.com/santoshadkar/Agile-AI-Knowledge-Copilot) -- 15 commits, full history preserved)
- [x] 9. Deploy (Render + Vercel) -- backend on Render (native Python runtime, no Docker; verified with a clean-venv build-and-run simulation before deploying), frontend on Vercel (CLI, non-interactive). CORS locked to the real Vercel origin (not wildcard). Along the way: caught and fixed a broad Gemini capacity issue (bumped retries) and a genuine per-model daily quota exhaustion (added Groq as a third fallback tier) -- both found by actually load-testing the live deployment, not assumed
- [x] 10. Verify deployed version -- confirmed working from the project owner's own device: a real question against the live app returned a correct, accurately-cited answer

**All 10 build steps complete.** The app is live, tested (48 backend tests), documented, and verified end-to-end from a real device -- not just from this development environment.

## Local development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # then fill in real API keys
uvicorn app.main:app --reload --port 8000
```

Health check: http://localhost:8000/health

### Run the tests

```bash
cd backend
pytest
```

No real API keys needed — `tests/conftest.py` sets fake credentials before
anything imports the app, and every test that would otherwise call
OpenRouter/Voyage/Qdrant mocks that call out. Safe to run in CI with no `.env`
at all.

### Ingest the sample docs

```bash
cd backend
python scripts/ingest_sample_docs.py
```

Loads every file under `sample_docs/<domain>/`, chunks it, embeds it with
Voyage AI, and upserts it into Qdrant. Re-running is safe — each file's
existing chunks are deleted before its new ones are inserted, so nothing
duplicates.

**Note:** a Voyage AI account with no payment method on file is capped at
3 requests/minute (the 200M free tokens still apply — this only throttles
request *rate*). The pipeline retries through that with exponential
backoff, so ingestion just runs slower rather than failing; add a payment
method in the [Voyage dashboard](https://dashboard.voyageai.com/) if you
want faster bulk ingestion for a larger corpus later.

### Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local   # then set NEXT_PUBLIC_API_URL
npm run dev -- --port 3018
```

App: http://localhost:3018

## API

Full interactive docs at `/docs` once the backend is running. Summary:

**`GET /health`** → `{"status": "ok"}`

**`POST /chat`**
```json
// request
{"message": "What does flow metrics measure?", "domain_filter": "agile-coaching"}  // domain_filter: "agile-coaching" | "claude-certification" | "both", defaults to "both"

// response
{
  "answer": "Flow metrics track cycle time, throughput, and WIP... [1]",
  "citations": [{"index": 1, "domain": "agile-coaching", "source": "agile-maturity-framework.md", "heading_path": "Agile Maturity Assessment Framework > Dimension: Flow Metrics"}],
  "domains_searched": ["agile-coaching"]
}
```
Returns `503` only if all three OpenRouter models in the generation chain fail.

**`POST /ingest`** (multipart form)
- `file`: the PDF/DOCX/MD to ingest
- `domain`: `"agile-coaching"` | `"claude-certification"`
- `force` (optional, default `false`): ingest anyway if the confidentiality guard flags the file

Returns `422` with `{"reasons": [...]}` if the confidentiality guard trips and `force` wasn't set; `400` for an unsupported file type; `413` over 10MB.

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | backend | OpenRouter access for the 3-model generation fallback chain |
| `VOYAGE_API_KEY` | backend | Voyage AI embeddings for ingestion + retrieval |
| `QDRANT_URL` | backend | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | backend | Qdrant Cloud API key |
| `QDRANT_COLLECTION_NAME` | backend | Collection name (default `agile_ai_knowledge`) |
| `CORS_ORIGINS` | backend | Comma-separated allowed frontend origin(s) — no wildcard in production |
| `NEXT_PUBLIC_API_URL` | frontend | Backend base URL |

No real secrets are ever committed — only `.env.example` / `.env.local.example`.
