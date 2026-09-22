# Agile & AI Knowledge Copilot

A RAG-powered chat assistant over two personal knowledge domains:

1. **Agile coaching** — maturity assessment frameworks, Big Room Planning artefacts, SAFe/Scrum reference material, Jira metrics governance docs.
2. **Claude certification study material** — content for Anthropic's Claude certifications (Associate/Developer/Architect Foundations, Architect Professional).

Every answer cites which source document(s) and domain it drew from. You can ask within a single domain or search across both.

This is a personal learning + portfolio project, not tied to any employer or confidential content — everything in `backend/sample_docs/` is generic, non-proprietary sample material used to prove the pipeline works.

## Architecture

```
frontend/  Next.js (React) — chat UI + admin/upload view          → deployed to Vercel
backend/   FastAPI + LangGraph — agentic RAG graph, ingestion API  → deployed to Render
           ├─ query-analysis/routing node (which domain(s) to search)
           ├─ retrieval node (Qdrant, filtered by domain)
           ├─ generation node (Gemini, produces cited answers)
           └─ check / re-retrieve loop (if first retrieval looks insufficient)
```

- **LLM (generation):** Google Gemini API — originally scoped as Claude, switched because the Anthropic API requires a payment method on file and Gemini's free tier doesn't. Uses a flash + flash-lite failover pair rather than a single model, since Gemini's free tier is tightly rate-limited per model.
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
- [ ] 6. Local end-to-end preview
- [ ] 7. Tests (retrieval/generation nodes + API smoke test)
- [ ] 8. GitHub push
- [ ] 9. Deploy (Render + Vercel)
- [ ] 10. Verify deployed version

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
Returns `503` if both the primary and fallback Gemini models fail.

**`POST /ingest`** (multipart form)
- `file`: the PDF/DOCX/MD to ingest
- `domain`: `"agile-coaching"` | `"claude-certification"`
- `force` (optional, default `false`): ingest anyway if the confidentiality guard flags the file

Returns `422` with `{"reasons": [...]}` if the confidentiality guard trips and `force` wasn't set; `400` for an unsupported file type; `413` over 10MB.

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | backend | Gemini API access for the generation node |
| `VOYAGE_API_KEY` | backend | Voyage AI embeddings for ingestion + retrieval |
| `QDRANT_URL` | backend | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | backend | Qdrant Cloud API key |
| `QDRANT_COLLECTION_NAME` | backend | Collection name (default `agile_ai_knowledge`) |
| `CORS_ORIGINS` | backend | Comma-separated allowed frontend origin(s) — no wildcard in production |
| `NEXT_PUBLIC_API_URL` | frontend | Backend base URL |

No real secrets are ever committed — only `.env.example` / `.env.local.example`.
