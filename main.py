from openai import OpenAI
from dotenv import load_dotenv
import os
from fastapi import FastAPI, File, HTTPException, UploadFile, Form
import shutil
from pathlib import Path
from typing import Optional
from models.document_type import DocumentType
from models.query import Query
from services.docs_loader import doc_loader
from services.chunker import chunker
from services.qdrantDB import qdrantDB
from services.postgresDB import postgresDB
from services.hybrid_retriever import hybridRetriever
from services.generation_judge import generationJudge
from services.semantic_cache import semanticCache
from config import settings


load_dotenv()

app = FastAPI(
    title="Medical Assistant RAG",
    version="1.0.0",
)

UPLOAD_DIR = Path("data")
UPLOAD_DIR.mkdir(exist_ok=True)


client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url=os.getenv("GEMINI_BASE_URL"),
)

# -------------------------
# Prompt
# -------------------------
SYSTEM_PROMPT = """
You are an experienced medical assistant.

Explain medical reports in simple language.

Rules:
- Also ONLY answer if context is related to medical as you are a Medical Assistant.
- If Question is not related to Medical then dont answer. Simply say ONLY ask questions related to medical reports.
- Answer ONLY from the provided context.
- Do not hallucinate.
- Mention abnormal values first.
- Explain findings in simple language.
- Mention normal findings briefly.
- Do NOT diagnose diseases.
- Do NOT prescribe medications.
- If the answer is not present in the context, clearly say so.
- End with a short bullet list of important findings.
- ALWAYS include inline citations in your answer using the provided Citation ID (e.g., [1], [2]) immediately after every claim or fact derived from the context.
"""



@app.get("/")
def home():
    return {"message": "Medical RAG API is running."}

@app.post("/upload")
async def upload_file(
    file:UploadFile=File(...),
    document_type:DocumentType=Form(...),
    patient_id:Optional[str]=Form(None),
    report_id:Optional[str]=Form(None),
    ):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    filepath = UPLOAD_DIR/file.filename

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    pages = doc_loader.load(filepath)

    # Attaching meta data
    for page in pages:
        page.metadata["document_type"] = document_type.value
        page.metadata["patient_id"] = patient_id
        page.metadata["report_id"] = report_id

    chunks = chunker.chunk(pages)

    qdrantDB.add_documents(chunks)
    postgresDB.add_documents(chunks)

    print("=" * 50)
    print(chunks[0].metadata)
    print("=" * 50)

    return {
        "message": "PDF uploaded successfully.",
        "filename": file.filename,
        "document_type": document_type,
        "patient_id": patient_id,
        "report_id": report_id,
        "pages": len(pages),
        "chunks": len(chunks),
    }


@app.post("/ask")
async def ask(query:Query):
    # checking cache first

    cached_response = semanticCache.get(query.question)
    if cached_response:
        return cached_response

    # normal retrieval from vector db
    result = hybridRetriever.search(query=query, k=3)
    docs = result["docs"]
    metadata = result["metadata"]

    print("\nRetrieved scores:")
    for doc, score in docs:
        print(score)

    # CrossEncoder scores can be negative logits, so we remove the > 0.01 threshold!
    filtered_results = docs

    if not filtered_results:
        return {
            "question": query.question,
            "answer": "Sorry, I can only answer questions related to the uploaded medical report.",
            "citations": [],
            "retrieval_metadata": metadata,
        }

    context = ""

    citations = []

    for index, (doc,score) in enumerate(filtered_results, start=1):
        
        page = doc.metadata.get("page",0) + 1
        source = doc.metadata.get("source", "Unknown")
        retrieved_from = doc.metadata.get("retrieved_from", "Unknown")

        citations.append({
            "id": f"[{index}]",
            "page": page,
            "source": source,
            "retrieved_from": retrieved_from,
            "score": round(score,3)
        })

        context += f"""
        Citation ID: [{index}]
        Page: {page}
        Source: {source}
        Text: {doc.page_content}
        Similarity Score: {round(score,3)}
        """

    user_prompt = f"""
    Context : {context}

    Question : {query.question}
    """

    final_answer = ""
    eval_history = []

    for eval_round in range(settings.max_rag_rounds):
        
        print(f"\nGenerating Answer (Round {eval_round + 1})...")
        
        response = client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        
        final_answer = response.choices[0].message.content
        
        print("\nEvaluating Generated Answer...")
        eval_result = generationJudge.evaluate(
            question=query.question, 
            context=context, 
            ans=final_answer
        )
        
        decision = eval_result.get("decision", "FAIL").upper()
        faithfulness = float(eval_result.get("faithfulness", 0.0))
        feedback = eval_result.get("feedback", "No feedback provided.")
        
        print(f"Decision: {decision}, Faithfulness: {faithfulness}")
        print(f"Feedback: {feedback}")
        
        eval_history.append({
            "round": eval_round + 1,
            "decision": decision,
            "faithfulness": faithfulness,
            "feedback": feedback
        })

        if decision == "PASS" and faithfulness >= settings.faithfulness_threshold:
            print("Answer passed evaluation.")
            break
            
        print("\nRewriting Answer based on feedback...")
        user_prompt += f"\n\n--- PREVIOUS ATTEMPT FEEDBACK ---\nYour previous answer was rejected (Faithfulness: {faithfulness}). Reason: {feedback}\nPlease rewrite your answer and fix the mistakes."

    metadata["eval_history"] = eval_history

    final_response = {
        "question": query.question,
        "answer": final_answer,
        "citations": citations,
        "retrieval_metadata": metadata,
    }

    if decision == "PASS":
        semanticCache.set(query.question,final_response)

    return final_response



@app.delete("/clear")
async def clear_all_data():
    # 1. Clear PostgreSQL
    postgresDB.clear_data()
    
    # 2. Clear Qdrant
    qdrantDB.clear_data()
    
    # 3. Clear PDF files in data directory
    for item in UPLOAD_DIR.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
            
    return {"message": "All database records and uploaded files cleared successfully."}

