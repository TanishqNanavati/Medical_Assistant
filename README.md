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

## 🚀 How to Run the Project

You can run this project in three different ways depending on your preference. For all methods, ensure you have a `.env` file in the root directory containing your `GEMINI_API_KEY` and other necessary configurations.

### Option 1: The Quickest Way (Pre-Built Docker Image)
If you just want to run the application without dealing with source code or local environments, use the pre-built image from Docker Hub.

1. Create a `docker-compose.yml` file and paste the configuration (ensuring the app service uses `image: nana993/medical-assistant:latest` and does not contain `build: .`).
2. Run the following commands in the directory where you saved the file:
```bash
# Pull the latest image
docker pull nana993/medical-assistant:latest

# Start all containers in the background
docker-compose up -d
```
*Your backend will be accessible at `http://localhost:8000` and the frontend dashboard at `http://localhost:3001` (mapped to 3001 to avoid Windows port conflicts).*

---

### Option 2: Build from Source (Docker Compose)
If you've cloned the GitHub repository and want to build the Docker image locally from the source code:

1. Clone the repository and navigate into it:
```bash
git clone https://github.com/yourusername/medical-assistant.git
cd medical-assistant
```
2. Run Docker Compose with the build flag. (Make sure your `docker-compose.yml` includes `build: .` under the `app` service):
```bash
docker-compose up -d --build
```

---

### Option 3: Manual Local Development (No Docker for the App)
If you want to run the FastAPI backend, Celery worker, and Next.js frontend manually on your host machine for active development:

**Prerequisites:** 
You must have running instances of PostgreSQL, Qdrant (port 6333), RabbitMQ, and Redis (port 6379) accessible to your host.

**1. Start the FastAPI Backend**
```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload
```
*The API will run on `http://localhost:8000`.*

**2. Start the Celery Worker**
Open a **second terminal** (ensure virtual environment is activated):
```bash
celery -A services.tasks worker --loglevel=info --pool=solo
```

**3. Start the Next.js Frontend**
Open a **third terminal**, navigate to the frontend directory:
```bash
cd frontend
npm install
npm run dev
```
*The Frontend will run on `http://localhost:3000`.*
