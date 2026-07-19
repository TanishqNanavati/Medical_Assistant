# Pulse AI 🏥 — Autonomous Multimodal Medical Assistant

> A production-grade, agentic RAG system for the medical domain. Upload your medical records, ask questions in plain language, and get hallucination-free, cited, explainable answers — backed by clinical calculators and deep telemetry analytics.

---

## 🔍 What This Is

Pulse AI is **not a standard RAG chatbot**. It is an autonomous, self-correcting AI agent specialized for high-stakes medical document analysis.

**Who it's for:**
- Patients who want to understand their own lab reports, prescriptions, or clinical documents in plain language.
- Clinicians who need to quickly query patient records, calculate risk scores, or check drug interactions.

**What problem it solves:**
LLMs hallucinate. In a medical context, that's dangerous. Pulse AI solves this through a strict **LLM-as-a-Judge self-evaluation loop** — every generated answer is verified against the retrieved source context before it ever reaches the user. Answers that fail the faithfulness threshold are automatically retried. Every response includes explicit citations and a structured explainability card so users always know *why* the AI said what it said.

---

## 🌟 What Makes It Stand Out

### 1. Agentic Orchestration (LangGraph)
Rather than a static pipeline, the system operates as an autonomous agent with dynamic routing:

- **Smart Query Routing** — decides whether to run full RAG retrieval, trigger a clinical calculator, generate a medical timeline, or handle casual conversation.
- **Query Expansion** — rewrites poorly phrased questions before retrieval to maximise vector search accuracy.
- **Self-Correction Loop** — a secondary LLM Judge evaluates each answer for faithfulness. Answers scoring below `0.70` are fed back with structured critique and regenerated (up to 2 retries).

### 2. Hybrid Retrieval + Cross-Encoder Reranking
Retrieval goes beyond basic cosine similarity:

- **Dense search** via Qdrant (embedding vectors).
- **Sparse search** via PostgreSQL BM25 (full-text, keyword-level).
- **Reciprocal Rank Fusion** to merge both result sets.
- **Cross-Encoder Reranking** (`ms-marco-MiniLM`) to score and filter down to the top 15 most relevant chunks.

### 3. Semantic Caching (Redis + Qdrant)
Before hitting the LLM, every query is checked against a semantic cache of previously answered questions (similarity threshold `0.80`). On a cache hit, the answer is returned from Redis — cutting response time from seconds to milliseconds and eliminating redundant API costs.

### 4. Explainable AI (XAI) Engine
Every response includes a structured explainability card:
- **Why this answer?** — logical reasoning steps the agent took.
- **Why these documents?** — justification for why specific chunks were retrieved.
- **Evidence quotes** — exact passages from the source documents.
- **Confidence score** — the Judge's faithfulness assessment.

### 5. Clinical Tools & Calculators
The agent can dynamically invoke medical calculation tools via LLM tool-calling:
- **ASCVD Risk Score** — 10-year cardiovascular risk.
- **eGFR** — kidney function estimation.
- **FIB-4 Index** — liver fibrosis assessment.
- **CHA₂DS₂-VASc** — stroke risk in atrial fibrillation.
- **Drug Interaction Checker** — via the OpenFDA API.

### 6. Async Multimodal Document Processing
Document ingestion is fully non-blocking:
- PDFs → text extracted via **PyMuPDF**, chunked, embedded, dual-indexed into Qdrant + PostgreSQL.
- Images (PNG, JPG, JPEG, X-Rays) → processed via **Gemini Vision** for OCR and content extraction.
- All heavy work is offloaded to **Celery** workers via **RabbitMQ**, keeping the API responsive.

### 7. Telemetry & Analytics Dashboard
Every request is instrumented. The built-in dashboard tracks:
- Token usage (prompt vs. completion).
- Latency breakdown (embedding / retrieval / LLM generation).
- Cache hit rates, query rewrite outcomes, Judge pass/fail rates, and average faithfulness scores.

---

## 🏗️ System Architecture

```
User Request (HTTP/SSE)
        │
        ▼
  Semantic Cache Check (Qdrant + Redis)
        │ miss
        ▼
  LangGraph Agent Router
        │
  ┌─────┴──────────────────────────────────┐
  │                                        │
  ▼                                        ▼
RAG Pipeline                       Clinical Tools
  │                                 (ASCVD / eGFR /
  ├─ Query Expansion                 FIB-4 / OpenFDA)
  ├─ Hybrid Retrieval
  │   ├─ Dense (Qdrant)
  │   ├─ Sparse (Postgres BM25)
  │   └─ Reciprocal Rank Fusion
  ├─ Cross-Encoder Reranking
  ├─ LLM Generation (Gemini)
  ├─ LLM-as-a-Judge (loop ≤ 2x)
  └─ Explainability Engine
        │
        ▼
  Postgres Telemetry Log
        │
        ▼
  SSE Stream → User


Document Upload Flow:
  Upload → FastAPI → Celery Task → RabbitMQ
                                       │
                          ┌────────────┘
                          ▼
                  PDF: PyMuPDF → Chunk → Embed
                  IMG: Gemini Vision → Extract → Chunk → Embed
                          │
                          ▼
               Qdrant (dense) + Postgres (BM25 sparse)
```

**Containerised Services:**
| Service | Port |
|---|---|
| FastAPI Backend | `8000` |
| Next.js Frontend | `3001` |
| PostgreSQL 17 | `5432` |
| Qdrant | `6333` |
| Redis 7 | `6379` |
| RabbitMQ | `5672` |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, TailwindCSS 4, Recharts, Lucide React |
| Backend API | FastAPI (Python) |
| AI Orchestration | LangGraph, LangChain |
| LLM / Embeddings | Google Gemini API |
| Reranking | `ms-marco-MiniLM` (sentence-transformers) |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL 17 (psycopg2, tsvector BM25) |
| Cache | Redis 7 |
| Task Queue | Celery + RabbitMQ |
| PDF Processing | PyMuPDF |
| Image / OCR | Gemini Vision |
| Auth | JWT (OAuth2 Password Bearer, bcrypt) |
| External APIs | OpenFDA (drug interactions) |
| Deployment | Docker, Docker Compose |

---


## 🚀 Getting Started

### Option 1 — Docker Hub (Quickest, No Source Code Needed)

> Best for: trying the project out without cloning anything.

**1.** Create a `.env` file in a new directory with your API keys (see `config.py` for the full list of required variables).

**2.** Grab the `docker-compose.yml` from the repo, replace the `app` service's `build: .` with:
```yaml
image: nana993/medical-assistant:latest
```

**3.** Pull and run:
```bash
docker pull nana993/medical-assistant:latest
docker-compose up -d
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

### Option 2 — Build from Source (Docker Compose)

> Best for: running the full stack locally from the cloned repo.

```bash
git clone https://github.com/TanishqNanavati/Medical_Assistant.git
cd Medical_Assistant

# Add your .env file

docker-compose up -d --build
```

---

### Option 3 — Manual Local Development

> Best for: active development with hot-reload.

**Prerequisites:** Running instances of PostgreSQL, Qdrant (`:6333`), RabbitMQ, and Redis (`:6379`) on your host.

**Terminal 1 — FastAPI Backend:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Terminal 2 — Celery Worker:**
```bash
celery -A services.tasks worker --loglevel=info --pool=solo
```

**Terminal 3 — Next.js Frontend:**
```bash
cd frontend
npm install
npm run dev
```