# Medical Assistant System 🏥 🤖

An enterprise-grade, agentic AI Medical Assistant that transcends traditional Retrieval-Augmented Generation (RAG). Built on a robust, state-of-the-art Generative AI stack, this system processes multimodal medical documents (PDFs, Images, X-Rays) and executes a highly intelligent, self-correcting workflow to deliver precise, medically accurate answers.

What sets this project apart from a standard RAG application is its **Agentic Workflow**, **Self-Evaluation**, **Explainability Engine**, and **Deep Telemetry Analytics**.

---

## 🌟 What Makes This Stand Out (Advanced GenAI Features)

### 1. Agentic Orchestration (LangGraph)
Unlike linear RAG pipelines, this system operates as an autonomous agent. 
*   **Dynamic Routing:** The agent decides whether a query requires document retrieval or if it's a casual conversation.
*   **Query Reformulation:** The AI rewrites poorly phrased user questions to maximize vector database retrieval success.
*   **Self-Correction (LLM-as-a-Judge):** Before returning an answer, a secondary LLM "Judge" evaluates the generated response for faithfulness and relevance against the retrieved context. If it fails, the agent self-corrects and tries again (up to 3 times).

### 2. Semantic Caching Engine
To optimize cost and latency, the system employs **Semantic Caching** using Redis and Qdrant. If a user asks a question that is semantically similar (but not exact) to a previously answered question, the system retrieves the cached response—bypassing the expensive LLM generation phase entirely and cutting response times from seconds to milliseconds.

### 3. Advanced Retrieval & Re-ranking
We don't just do basic cosine similarity. The retrieval pipeline leverages:
*   Dense vector search via **Qdrant**.
*   **Cross-Encoder Re-ranking** to rigorously re-score and sort the retrieved chunks, ensuring the LLM only receives the most highly relevant context.

### 4. XAI (Explainable AI) Engine
In medical applications, trust is paramount. Every AI response comes with a "Behind the Scenes" explainability card detailing:
*   **Why this answer?** The logical steps the AI took.
*   **Why these documents?** Why the retrieved context was chosen.
*   **Method Used & Confidence:** The AI's self-assessed confidence score and the exact evidence quotes extracted from the documents.

### 5. Asynchronous Multimodal Processing
Document ingestion doesn't block the API. Uploaded PDFs and Medical Images are handed off to a **Celery** background worker queue. 
*   Images undergo OCR processing (via OCR.Space API).
*   Text is chunked, embedded, and stored in Qdrant asynchronously.

### 6. Enterprise Telemetry & Analytics Dashboard
A massive, built-in analytics dashboard tracks every metric of the AI's performance over time:
*   **Token Usage** (Prompt vs. Completion tokens).
*   **Latency Breakdown** (Embedding vs. Retrieval vs. LLM Generation time).
*   **Agent Metrics** (Cache hit rates, Query rewrite success, LLM Judge pass/fail rates, and average faithfulness scores).

---

## 🏗️ Architecture Stack

- **Frontend:** Next.js (React), TailwindCSS, Recharts (for Analytics)
- **Backend API:** FastAPI (Python)
- **AI Orchestration:** LangGraph & LangChain 
- **LLM Provider:** Google Gemini API
- **Databases:** 
  - **PostgreSQL:** Relational data (Users, Sessions, Telemetry Logs, Document Metadata).
  - **Qdrant:** Vector Database for storing document embeddings.
  - **Redis:** Used for both Semantic Caching and as the Celery Message Broker.
- **Background Workers:** Celery (handles heavy OCR and embedding generation asynchronously).

---

## 🚀 How to Run the Project (Local Development)

### Prerequisites
Make sure you have running instances of PostgreSQL, Qdrant (port 6333), and Redis (port 6379). Also, configure your `.env` file with `GEMINI_API_KEY`, OCR API Keys, and your database URIs.

### 1. Start the FastAPI Backend
Open a terminal and run the main application server:
```bash
uvicorn main:app --reload
```
*Note: The API runs on `http://localhost:8000`.*

### 2. Start the Celery Worker
Open a **second terminal** to handle background document processing:
```bash
celery -A services.tasks worker --loglevel=info --pool=solo
```

### 3. Start the Next.js Frontend
Open a **third terminal**, navigate to the frontend directory, and run the client:
```bash
cd frontend
npm run dev
```
*Note: The Frontend runs on `http://localhost:3000`.*

---

## 🐳 Deploying with Docker (Recommended)

You can easily run the entire ecosystem (Databases, Backend, Celery Worker, and Frontend) using Docker. The application image is hosted on Docker Hub for easy distribution.

### 1. Configure Environment
Ensure you have a `.env` file in the root directory with your API keys (e.g., `GEMINI_API_KEY`).

### 2. Run with Docker Compose
Simply download the `docker-compose.yml` file and run:
```bash
docker-compose up -d
```
This command will:
1. Automatically pull the pre-built `nana993/medical-assistant:latest` image from Docker Hub.
2. Spin up isolated instances of **PostgreSQL**, **Qdrant**, **Redis**, and **RabbitMQ**.
3. Connect the application directly to the internal database network.

*Your backend will be accessible at `http://localhost:8000` and the frontend dashboard at `http://localhost:3000`.*
